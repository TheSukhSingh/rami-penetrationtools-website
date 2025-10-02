import re, uuid
from datetime import datetime, timezone, timedelta
from .passwords import COMMON_PASSWORDS
from hashlib import sha256
from sqlalchemy import Table, Column, Integer, ForeignKey, String, UniqueConstraint, CheckConstraint, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from extensions import db, bcrypt
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import exists, select, and_, or_, not_

utcnow = lambda: datetime.now(timezone.utc)

RESERVED_USERNAMES = {
    'admin','administrator','root','system','support',
    'null','none','user','username','test','info','sys'
}

class TimestampMixin:
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False
    )

user_roles = Table(
    'user_roles',
    db.Model.metadata,
    Column('user_id',   Integer, ForeignKey('users.id',   ondelete='CASCADE'), primary_key=True),
    Column('role_id',   Integer, ForeignKey('roles.id',   ondelete='CASCADE'), primary_key=True),
    UniqueConstraint('user_id', 'role_id', name='uq_user_role')
)


# --- RBAC --------------------------------------------------------------------

class Role(db.Model, TimestampMixin):
    """
    Minimal RBAC role with fine-grained scopes stored as JSON.

    Example scopes:
      ["users.read","users.write","scans.read","tools.read","tools.write","settings.write","audit.read"]
    """
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))
    scopes = db.Column(db.JSON, nullable=False, default=list)  # array of strings

    users = relationship('User', secondary=user_roles, back_populates='roles')

    def __repr__(self):
        return f"<Role {self.name}>"
    
ADMIN_PREFIX = "admin_"
MASTER_ROLE_NAMES = ("admin_owner",)  

class User(TimestampMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        # enforce length and no-spaces at the DB level
        CheckConstraint("length(username) >= 4", name="username_min_len"),
        CheckConstraint("length(username) <= 15", name="username_max_len"),
        CheckConstraint("username NOT LIKE '% %'", name="username_no_spaces"),
    )

    id             = db.Column(db.Integer, primary_key=True)
    email          = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username       = db.Column(db.String(15), unique=True, nullable=False, index=True, doc="4-15 chars, letters/numbers/underscore only")
    name           = db.Column(db.String(255), nullable=True)

    is_blocked     = db.Column(db.Boolean, default=False, nullable=False)
    is_deactivated = db.Column(db.Boolean, default=False, nullable=False)
    is_protected   = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # relationships
    local_auth      = relationship('LocalAuth',       back_populates='user', uselist=False ,  cascade='all, delete-orphan')
    oauth_accounts  = relationship('OAuthAccount',    back_populates='user',                  cascade='all, delete-orphan')
    mfa_setting     = relationship('MFASetting',      back_populates='user', uselist=False ,  cascade='all, delete-orphan')
    reset_tokens    = relationship('PasswordReset',   back_populates='user',                  cascade='all, delete-orphan')
    login_events    = relationship('LoginEvent',      back_populates='user',                  cascade='all, delete-orphan')
    refresh_tokens  = relationship('RefreshToken',    back_populates='user',                  cascade='all, delete-orphan')
    roles           = relationship('Role',            back_populates='users', secondary=user_roles)
    scan_history    = relationship('ToolScanHistory', back_populates='user', lazy="dynamic")
    ip_logs = relationship('UserIPLog',back_populates='user',cascade='all, delete-orphan')
    grants = relationship(
        "UserScopeGrant",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="UserScopeGrant.user_id",
    )

    denies = relationship(
        "UserScopeDeny",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="UserScopeDeny.user_id",
    )

    role_audits = relationship(
        "UserRoleAudit",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="UserRoleAudit.user_id",
    )
    refresh_tokens = db.relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @staticmethod
    def _validate_username(u: str):
        """Raise ValueError if invalid."""
        if not (4 <= len(u) <= 15):
            raise ValueError("Username must be 4-15 characters long.")
        if not re.match(r'^[A-Za-z0-9_]+$', u):
            raise ValueError("Username may only contain letters, numbers, and underscores.")
        if u.lower() in RESERVED_USERNAMES:
            raise ValueError("That username is reserved; please choose another.")
    
    @property
    def is_verified(self) -> bool:
        # 1) direct flag (if you added one)
        if hasattr(self, "email_verified") and bool(getattr(self, "email_verified")):
            return True
        # 2) LocalAuth flag
        la = getattr(self, "local_auth", None)
        if la and getattr(la, "email_verified", False):
            return True
        # 3) any linked OAuth account => provider-verified email
        oas = getattr(self, "oauth_accounts", None)
        return bool(oas and len(oas) > 0)

    def get_full_name(self):
        return self.name or self.username or self.email

    def get_short_name(self):
        full = self.get_full_name()
        return full.split(" ")[0] if " " in full else full
    
    def has_role(self, name: str) -> bool:
        return any(r.name == name for r in self.roles)
    
    @property
    def is_local(self) -> bool:
        return bool(self.local_auth and self.local_auth.password_hash)

    @property
    def is_oauth(self) -> bool:
        return bool(self.oauth_accounts)
    
    @hybrid_property
    def is_master_user(self) -> bool:
        return self.is_protected or any(r.name in MASTER_ROLE_NAMES for r in self.roles)


    @hybrid_property
    def is_admin_user(self) -> bool:
        # any admin_* role, but NOT a master
        return any((r.name or "").startswith(ADMIN_PREFIX) for r in self.roles) and not self.is_master_user

    @is_master_user.expression
    def is_master_user(cls):
        r = Role.__table__.alias("r_master")
        return or_(
            cls.is_protected,
            exists(
                select(1).where(
                    and_(
                        user_roles.c.user_id == cls.id,
                        user_roles.c.role_id == r.c.id,
                        r.c.name.in_(MASTER_ROLE_NAMES),
                    )
                )
            ),
        )

    @is_admin_user.expression
    def is_admin_user(cls):
        r = Role.__table__.alias("r_admin")
        return and_(
            exists(
                select(1).where(
                    and_(
                        user_roles.c.user_id == cls.id,
                        user_roles.c.role_id == r.c.id,
                        # see note #2:
                        r.c.name.like("admin\\_%", escape="\\"),
                    )
                )
            ),
            not_(cls.is_master_user),
        )
    
    def role_scopes(self) -> set[str]:
        s = set()
        for r in self.roles:
            if r.scopes:
                s.update(r.scopes)   # Role.scopes is a JSON/ARRAY column
        return s

    def extra_granted_scopes(self) -> set[str]:
        return {g.scope for g in self.grants}

    def extra_revoked_scopes(self) -> set[str]:
        return {d.scope for d in self.denies}

    def effective_scopes(self) -> set[str]:
        return self.role_scopes().union(self.extra_granted_scopes()) - self.extra_revoked_scopes()

    def has_scope(self, scope: str) -> bool:
        return scope in self.effective_scopes()
    
class UserRoleAudit(db.Model, TimestampMixin):
    __tablename__ = "user_role_audits"
    __table_args__ = (Index('ix_user_role_audit_user', 'user_id', 'created_at'),)
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role_id   = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    action    = db.Column(db.Enum('assign', 'remove', name='role_action_enum'), nullable=False)
    acted_by  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    note      = db.Column(db.String(255))

    user      = relationship('User', foreign_keys=[user_id], back_populates='role_audits')
    role      = relationship('Role')
    actor     = relationship('User', foreign_keys=[acted_by])

    def __repr__(self): return f"<RoleAudit user={self.user_id} role={self.role_id} {self.action}>"

# --- User activity/IP history -------------------------------------------------

class UserIPLog(db.Model):
    """
    Event-agnostic trail of where a user acted from (login, scans, admin UI, etc.).
    """
    __tablename__ = "user_ip_logs"
    __table_args__ = (
        Index("ix_user_ip_logs_user_created", "user_id", "created_at"),
        Index("ix_user_ip_logs_ip", "ip"),
    )

    id          = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    ip          = db.Column(db.String(64), nullable=False)
    user_agent  = db.Column(db.String(255))
    device      = db.Column(db.String(128))              # parsed UA if you store it
    geo_city    = db.Column(db.String(128))
    geo_country = db.Column(db.String(128))
    created_at  = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship('User', back_populates='ip_logs')

    def __repr__(self):
        return f"<UserIPLog user={self.user_id} ip={self.ip} at={self.created_at:%Y-%m-%d %H:%M:%S}>"

class UserScopeGrant(db.Model, TimestampMixin):
    __tablename__ = "user_scope_grants"
    __table_args__ = (
        UniqueConstraint('user_id', 'scope', name='uq_user_scope_grant'),
        Index('ix_user_scope_grant_user', 'user_id'),
        Index('ix_user_scope_grant_scope', 'scope'),
    )
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    scope    = db.Column(db.String(100), nullable=False)
    acted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    note     = db.Column(db.String(255))

    user         = relationship('User', foreign_keys=[user_id], back_populates='grants')
    acted_by_user= relationship('User', foreign_keys=[acted_by])
    def __repr__(self): return f"<Grant user={self.user_id} {self.scope}>"

class UserScopeDeny(db.Model, TimestampMixin):
    __tablename__ = "user_scope_denies"
    __table_args__ = (
        UniqueConstraint('user_id', 'scope', name='uq_user_scope_deny'),
        Index('ix_user_scope_deny_user', 'user_id'),
        Index('ix_user_scope_deny_scope', 'scope'),
    )
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    scope    = db.Column(db.String(100), nullable=False)
    acted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    note     = db.Column(db.String(255))

    user         = relationship('User', foreign_keys=[user_id], back_populates='denies')
    acted_by_user= relationship('User', foreign_keys=[acted_by])
    def __repr__(self): return f"<Deny user={self.user_id} {self.scope}>"

class LocalAuth(db.Model):
    __tablename__ = 'local_auth'
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    password_hash = db.Column(db.String(128), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    last_failed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at  = db.Column(db.DateTime(timezone=True), nullable=True)
    password_changed_at = db.Column(db.DateTime(timezone=True))
    
    user = db.relationship('User', back_populates='local_auth')

    def _validate_password(self, raw: str):
        pw = raw or ""
        if len(pw) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if re.search(r'(.)\1\1', pw):
            raise ValueError("No character may repeat three times in a row.")
        if not re.search(r'[A-Z]', pw):
            raise ValueError("Must include at least one uppercase letter.")
        if not re.search(r'\d', pw):
            raise ValueError("Must include at least one digit.")
        if not re.search(r'[^A-Za-z0-9]', pw):
            raise ValueError("Must include at least one special character.")
        lower = pw.lower()
        if lower in COMMON_PASSWORDS:
            raise ValueError("That password is too common; please choose a stronger one.")
        user = self.user or User.query.get(self.user_id)
        if user:
            # don’t allow name, username or email fragments
            if user.name and user.name.lower() in lower:
                raise ValueError("Password must not contain your name.")
            if user.username and user.username.lower() in lower:
                raise ValueError("Password must not contain your username.")
            if user.email and user.email.lower() in lower:
                raise ValueError("Password must not contain your email address.")
    
    def set_password(self, raw: str) -> None:
        self._validate_password(raw)
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')
        self.password_changed_at = datetime.now(timezone.utc)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)

class OAuthAccount(db.Model):
    __tablename__ = 'oauth_accounts'
    __table_args__ = (
        UniqueConstraint('provider', 'provider_id', name='uq_oauth_provider_id'),
    )
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    provider      = db.Column(db.Enum('google','github', name='provider_enum'), nullable=False)
    provider_id   = db.Column(db.String(255), nullable=False)

    user = db.relationship('User', back_populates='oauth_accounts')

class MFASetting(db.Model):
    __tablename__ = 'mfa_settings'
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    secret     = db.Column(db.String(32), nullable=False)
    enabled    = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', back_populates='mfa_setting')

class PasswordReset(db.Model):
    __tablename__ = 'password_resets'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash   = db.Column(db.String(64), nullable=False, unique=True)
    expires_at   = db.Column(db.DateTime(timezone=True), nullable=False)
    used         = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', back_populates='reset_tokens')

    def generate_reset_token(self, expires_in: int = 600) -> str:
        PasswordReset.query.filter_by(user_id=self.user_id, used=False).update({'used': True}, synchronize_session=False)
        token = str(uuid.uuid4())
        self.token_hash = sha256(token.encode()).hexdigest()
        self.expires_at = utcnow() + timedelta(seconds=expires_in)
        self.used = False    
        db.session.add(self)
        db.session.commit()
        return token
    
    @staticmethod
    def get_valid_record(token: str):
        """Return the PasswordReset row without consuming it."""
        h = sha256(token.encode()).hexdigest()
        return PasswordReset.query.filter(
            PasswordReset.token_hash == h,
            PasswordReset.used == False,
            PasswordReset.expires_at > utcnow()
        ).first()

    def consume(self):
        """Mark this reset token as used (single-use)."""
        self.used = True
        db.session.commit()

class LoginEvent(db.Model):
    __tablename__ = 'login_events'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    occurred_at  = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    ip_address   = db.Column(db.String(45))
    successful   = db.Column(db.Boolean, nullable=False)

    user = db.relationship('User', back_populates='login_events')

class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash  = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at  = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at  = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked     = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # NEW: match what routes/utils already use
    ip          = db.Column(db.String(45))         # IPv4/IPv6
    user_agent  = db.Column(db.String(255))
    last_used_at= db.Column(db.DateTime(timezone=True))
    device_label= db.Column(db.String(128))

    user = db.relationship("User", back_populates="refresh_tokens")

    def revoke(self):
        self.revoked = True
        db.session.commit()

class RecoveryCode(db.Model):
    __tablename__ = 'recovery_codes'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    code_hash  = db.Column(db.String(64), unique=True, nullable=False) 
    used       = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

class TrustedDevice(db.Model):
    __tablename__ = "trusted_devices"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash  = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at  = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at= db.Column(db.DateTime(timezone=True))
    expires_at  = db.Column(db.DateTime(timezone=True), nullable=False)

    # NEW: used by routes
    label       = db.Column(db.String(128))
    ip          = db.Column(db.String(45))
    user_agent  = db.Column(db.String(255))

    user = db.relationship("User", backref=db.backref("trusted_devices", lazy="dynamic", cascade="all, delete-orphan"))


class SecurityEvent(db.Model):
    __tablename__ = "security_events"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    event_type  = db.Column(db.String(50), nullable=False)  # e.g., 'PASSWORD_RESET_REQUESTED', 'PASSWORD_RESET_SUCCESS'
    ip_address  = db.Column(db.String(45))
    user_agent  = db.Column(db.String(255))
    meta        = db.Column(db.JSON, nullable=True)

    user = db.relationship('User', backref=db.backref('security_events', cascade='all, delete-orphan'))

# --- NEW: per-429 record (observability) ---
class RateLimitEvent(db.Model):
    __tablename__ = "rate_limit_events"
    id          = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    ip_address  = db.Column(db.String(45))
    method      = db.Column(db.String(8))
    path        = db.Column(db.String(255), index=True)
    endpoint    = db.Column(db.String(128), index=True)
    key         = db.Column(db.String(128))     # limiter key (ip/email/etc.)
    limit       = db.Column(db.String(64))      # e.g. "5 per 15 minutes"
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user        = db.relationship('User', backref=db.backref('rate_limit_events', lazy='dynamic'))

# --- NEW: daily rollup for auth metrics ---
class AuthDailyStats(db.Model):
    __tablename__ = "auth_daily_stats"
    # Use day as PK to upsert per day
    day                       = db.Column(db.Date, primary_key=True)

    # Core counts
    dau                       = db.Column(db.Integer, nullable=False, default=0)   # distinct users with successful login this day
    mau_30                    = db.Column(db.Integer, nullable=False, default=0)   # distinct users over prior 30 days (including day)
    signups                   = db.Column(db.Integer, nullable=False, default=0)   # users created that day
    verifications             = db.Column(db.Integer, nullable=False, default=0)   # email verified that day

    # MFA funnel (emit events below)
    mfa_required              = db.Column(db.Integer, nullable=False, default=0)
    mfa_success               = db.Column(db.Integer, nullable=False, default=0)
    mfa_fail                  = db.Column(db.Integer, nullable=False, default=0)

    # Recovery & abuse signals
    password_resets_requested = db.Column(db.Integer, nullable=False, default=0)
    password_resets_success   = db.Column(db.Integer, nullable=False, default=0)
    rate_limit_hits           = db.Column(db.Integer, nullable=False, default=0)

    created_at                = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at                = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)