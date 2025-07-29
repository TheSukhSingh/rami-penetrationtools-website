import re
import uuid
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import CheckConstraint
from .passwords import COMMON_PASSWORDS
from hashlib import sha256

db = SQLAlchemy()
bcrypt = Bcrypt()

# forbidden usernames
RESERVED_USERNAMES = {
    'admin','administrator','root','system','support',
    'null','none','user','username','test','info','sys'
}

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        # enforce length and no-spaces at the DB level
        CheckConstraint("length(username) >= 5", name="username_min_len"),
        CheckConstraint("length(username) <= 15", name="username_max_len"),
        CheckConstraint("username NOT LIKE '% %'", name="username_no_spaces"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(
        db.String(15),
        unique=True,
        nullable=False,
        index=True,
        doc="5-15 chars, letters/numbers/underscore only"
    )
    name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)

    provider = db.Column(
        db.Enum('local', 'google', 'github', name='provider_enum'),
        nullable=False,
        default='local'
    )
    provider_id = db.Column(db.String(255), nullable=True)

    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(
                        db.DateTime,
                        default=datetime.utcnow,
                        onupdate=datetime.utcnow,
                        nullable=False
                    )
    last_login_at = db.Column(db.DateTime, nullable=True)

    failed_logins     = db.Column(db.Integer, default=0, nullable=False)
    last_failed_login_at = db.Column(db.DateTime, nullable=True)
    reset_token       = db.Column(db.String(36), nullable=True)
    reset_token_expiry= db.Column(db.DateTime, nullable=True)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret  = db.Column(db.String(32), nullable=True)


    @staticmethod
    def _validate_username(u: str):
        """Raise ValueError if invalid."""
        if not (5 <= len(u) <= 15):
            raise ValueError("Username must be 5–15 characters long.")
        if not re.match(r'^[A-Za-z0-9_]+$', u):
            raise ValueError("Username may only contain letters, numbers, and underscores.")
        if u.lower() in RESERVED_USERNAMES:
            raise ValueError("That username is reserved; please choose another.")

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
        if self.name and self.name.lower() in lower:
            raise ValueError("Password must not contain your name.")
        if self.email and self.email.lower() in lower:
            raise ValueError("Password must not contain your email address.")

    def set_password(self, raw: str) -> None:
        if self.provider == 'local':
            self._validate_password(raw)
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)

    def generate_reset_token(self, expires_in: int = 600) -> str:
        token = str(uuid.uuid4())
        self.reset_token = sha256(token.encode()).hexdigest()
        self.reset_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        db.session.add(self)
        db.session.commit()
        return token
    
    def get_full_name(self):
        return self.name or self.username or self.email

    def get_short_name(self):
        full = self.get_full_name()
        return full.split(" ")[0] if " " in full else full

    @staticmethod
    def verify_reset_token(token: str) -> 'User | None':
        hashed = sha256(token.encode()).hexdigest()
        user = User.query.filter_by(reset_token=hashed).first()
        if user and user.reset_token_expiry and user.reset_token_expiry > datetime.utcnow():
            return user
        return None

    def __repr__(self) -> str:
        return f'<User email={self.email!r} id={self.id}>'
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.email_verified  
    
    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


