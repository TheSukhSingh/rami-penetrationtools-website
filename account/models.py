from extensions import db
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, ForeignKey
from datetime import datetime, timezone

utcnow = lambda: datetime.now(timezone.utc)

class AccountProfile(db.Model):
    """
    Optional per-user profile data that doesn't belong on auth tables.
    """
    __tablename__ = "account_profiles"
    user_id   = db.Column(db.Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone  = db.Column(db.String(64), default="UTC", nullable=False)
    locale    = db.Column(db.String(16), default="en", nullable=False)
    avatar_url= db.Column(db.String(512))
    bio       = db.Column(db.String(280))
    updated_at= db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user      = relationship("User", backref=db.backref("account_profile", uselist=False, cascade="all, delete-orphan"))

class AccountNotificationPrefs(db.Model):
    __tablename__ = "account_notification_prefs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_account_notif_user"),)
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_updates = db.Column(db.Boolean, default=True, nullable=False)
    marketing_emails= db.Column(db.Boolean, default=False, nullable=False)
    security_alerts = db.Column(db.Boolean, default=True, nullable=False)
