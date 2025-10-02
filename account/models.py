from extensions import db
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, ForeignKey
from datetime import datetime, timezone
import enum
from datetime import datetime, timezone, timedelta
utcnow = lambda: datetime.now(timezone.utc)

class AccountProfile(db.Model):
    """
    Optional per-user profile data that doesn't belong on auth tables.
    """
    __tablename__ = "account_profiles"
    user_id     = db.Column(db.Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone    = db.Column(db.String(64), default="UTC", nullable=False)
    bio         = db.Column(db.String(1024))
    updated_at  = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", backref=db.backref("account_profile", uselist=False, cascade="all, delete-orphan"))

class AccountNotificationPrefs(db.Model):
    __tablename__ = "account_notification_prefs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)

    # GROUP FLAGS (keep for backward compatibility / grouping in UI)
    product_updates  = db.Column(db.Boolean, nullable=False, default=True)
    marketing_emails = db.Column(db.Boolean, nullable=False, default=False)
    security_alerts  = db.Column(db.Boolean, nullable=False, default=True)

    # NEW GRANULAR FLAGS (persist each UI toggle)
    # Security
    login_alerts             = db.Column(db.Boolean, nullable=False, default=True)
    password_change_alerts   = db.Column(db.Boolean, nullable=False, default=True)
    tfa_change_alerts        = db.Column(db.Boolean, nullable=False, default=True)

    # Product
    new_tools_updates        = db.Column(db.Boolean, nullable=False, default=True)
    feature_updates          = db.Column(db.Boolean, nullable=False, default=True)

    # Marketing
    promotions               = db.Column(db.Boolean, nullable=False, default=False)
    newsletter               = db.Column(db.Boolean, nullable=False, default=False)

    # In-app (optional, now persisted too)
    scan_completion          = db.Column(db.Boolean, nullable=False, default=True)
    weekly_summary           = db.Column(db.Boolean, nullable=False, default=False)

    # (optional) helper to recompute group flags from granular toggles
    def recompute_groups(self):
        self.security_alerts  = bool(self.login_alerts or self.password_change_alerts or self.tfa_change_alerts)
        self.product_updates  = bool(self.new_tools_updates or self.feature_updates)
        self.marketing_emails = bool(self.promotions or self.newsletter)

class DataExportStatus(str, enum.Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"

class DataExportJob(db.Model):
    __tablename__ = "account_data_exports"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status          = db.Column(db.String(16), nullable=False, default=DataExportStatus.QUEUED.value)
    requested_at    = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    started_at      = db.Column(db.DateTime(timezone=True))
    finished_at     = db.Column(db.DateTime(timezone=True))
    download_url    = db.Column(db.String(512))
    byte_size       = db.Column(db.BigInteger)
    error           = db.Column(db.String(255))

    user = relationship("User")
    __table_args__ = (db.Index("ix_export_user_requested", "user_id", "requested_at"),)

class DeletionRequestStatus(str, enum.Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    CANCELED  = "canceled"
    EXECUTED  = "executed"

class AccountDeletionRequest(db.Model):
    __tablename__ = "account_deletion_requests"
    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status               = db.Column(db.String(16), nullable=False, default=DeletionRequestStatus.PENDING.value)
    requested_at         = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    scheduled_delete_at  = db.Column(db.DateTime(timezone=True))
    confirmed_at         = db.Column(db.DateTime(timezone=True))
    executed_at          = db.Column(db.DateTime(timezone=True))
    canceled_at          = db.Column(db.DateTime(timezone=True))
    reason               = db.Column(db.String(255))
    created_ip           = db.Column(db.String(45))
    user_agent           = db.Column(db.String(255))

    user = relationship("User")
    __table_args__ = (db.Index("ix_delreq_user_status", "user_id", "status"),)
