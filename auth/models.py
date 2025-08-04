import re, uuid
from datetime import datetime, timedelta
from .passwords import COMMON_PASSWORDS
from hashlib import sha256
from sqlalchemy import Table, Column, Integer, ForeignKey, String, UniqueConstraint, CheckConstraint, Boolean, DateTime
from sqlalchemy.orm import relationship
from extensions import db, bcrypt


RESERVED_USERNAMES = {
    'admin','administrator','root','system','support',
    'null','none','user','username','test','info','sys'
}

class TimestampMixin:
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

user_roles = Table(
    'user_roles',
    db.Model.metadata,
    Column('user_id',   Integer, ForeignKey('users.id',   ondelete='CASCADE'), primary_key=True),
    Column('role_id',   Integer, ForeignKey('roles.id',   ondelete='CASCADE'), primary_key=True),
    UniqueConstraint('user_id', 'role_id', name='uq_user_role')
)

class Role(db.Model):
    __tablename__ = 'roles'
    id   = Column(Integer, primary_key=True)

    name = Column(String(50), unique=True, nullable=False, index=True) 
    description = Column(String(255), nullable=True)
    users = relationship('User', secondary=user_roles, back_populates='roles')

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

    # relationships
    local_auth    = relationship('LocalAuth', uselist=False , back_populates='user', cascade='all, delete-orphan')
    oauth_accounts = relationship('OAuthAccount', back_populates='user', cascade='all, delete-orphan')
    mfa_setting   = relationship('MFASetting', uselist=False , back_populates='user', cascade='all, delete-orphan')
    reset_tokens  = relationship('PasswordReset', back_populates='user', cascade='all, delete-orphan')
    login_events  = relationship('LoginEvent', back_populates='user', cascade='all, delete-orphan')
    refresh_tokens = relationship('RefreshToken', back_populates='user', cascade='all, delete-orphan')
    roles = relationship('Role', secondary=user_roles, back_populates='users', cascade='all')
    scan_history = relationship('ToolScanHistory', back_populates='user', lazy="dynamic")

    @staticmethod
    def _validate_username(u: str):
        """Raise ValueError if invalid."""
        if not (4 <= len(u) <= 15):
            raise ValueError("Username must be 4-15 characters long.")
        if not re.match(r'^[A-Za-z0-9_]+$', u):
            raise ValueError("Username may only contain letters, numbers, and underscores.")
        if u.lower() in RESERVED_USERNAMES:
            raise ValueError("That username is reserved; please choose another.")
    
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


class LocalAuth(db.Model):
    __tablename__ = 'local_auth'
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    password_hash = db.Column(db.String(128), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    last_failed_at = db.Column(db.DateTime, nullable=True)
    last_login_at  = db.Column(db.DateTime, nullable=True)

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

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)



class OAuthAccount(db.Model):
    __tablename__ = 'oauth_accounts'
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
    expires_at   = db.Column(db.DateTime, nullable=False)
    used         = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', back_populates='reset_tokens')

    def generate_reset_token(self, expires_in: int = 600) -> str:
        PasswordReset.query.filter_by(user_id=self.user_id, used=False).update({'used': True})
        token = str(uuid.uuid4())
        self.token_hash = sha256(token.encode()).hexdigest()
        self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.used = False    
        db.session.add(self)
        db.session.commit()
        return token
    
    @staticmethod
    def verify_reset_token(token: str) -> 'User | None':
        hashed = sha256(token.encode()).hexdigest()
        # 1) Find an unused, unexpired reset record
        pr = PasswordReset.query.filter(
               PasswordReset.token_hash == hashed,
               PasswordReset.used      == False,
               PasswordReset.expires_at > datetime.utcnow()
             ).first()

        if not pr:
            return None

        # 2) Mark it used immediately (atomic enough for most apps)
        pr.used = True
        db.session.commit()

        # 3) Return the associated user
        return pr.user

class LoginEvent(db.Model):
    __tablename__ = 'login_events'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    occurred_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address   = db.Column(db.String(45))
    successful   = db.Column(db.Boolean, nullable=False)

    user = db.relationship('User', back_populates='login_events')

class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    token_hash   = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at   = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at   = db.Column(DateTime, nullable=False)
    revoked      = db.Column(Boolean, default=False, nullable=False)

    # backref to user
    user = relationship('User', back_populates='refresh_tokens')

    def revoke(self):
        self.revoked = True
        db.session.commit()
