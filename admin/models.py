from datetime import datetime, timezone
from sqlalchemy import Index
from extensions import db
from sqlalchemy.orm import relationship

utcnow = lambda: datetime.now(timezone.utc)

class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

class Setting(db.Model, TimestampMixin):
    """
    Key-value store for admin-editable configuration.
    """
    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.JSON, nullable=False) 
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True) 

    updated_by_user = relationship(
        'User',
        primaryjoin="User.id==Setting.updated_by",
        foreign_keys=[updated_by]
    ) 

    def __repr__(self):
        return f"<Setting {self.key}>"

class AdminAuditLog(db.Model):
    """
    Immutable audit of admin actions across the system.
    """
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_admin_audit_logs_subject", "subject_type", "subject_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, index=True)                 # admin user id
    action = db.Column(db.String(64), nullable=False)            # e.g. "users.deactivate", "tools.update"
    subject_type = db.Column(db.String(32), nullable=False)      # e.g. "user", "tool", "setting"
    subject_id = db.Column(db.Integer)                           # target primary key
    success = db.Column(db.Boolean, default=True, nullable=False, index=True)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    meta = db.Column(db.JSON)                                    # {"before": {...}, "after": {...}} or free-form
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self):
        return f"<AdminAuditLog action={self.action} subject={self.subject_type}:{self.subject_id}>"

