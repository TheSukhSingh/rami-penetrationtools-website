from datetime import datetime
from sqlalchemy import CheckConstraint, Index, ForeignKey
from sqlalchemy.orm import relationship
from extensions import db

# ─────────────────────────────────────────────────────────────────────────────
# Enumerations via CHECK constraints (portable for SQLite/Postgres)
# ─────────────────────────────────────────────────────────────────────────────
STATUS_VALUES = ("new", "open", "pending_user", "on_hold", "solved", "closed")
PRIORITY_VALUES = ("low", "normal", "high", "urgent")
VISIBILITY_VALUES = ("public", "internal")
SCAN_STATUS_VALUES = ("pending", "clean", "infected", "failed")

class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # Adjust the FK target if your users table name differs from "users"
    requester_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=False, index=True)

    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="new")
    priority = db.Column(db.String(20), nullable=False, default="normal")

    # In Solo Mode, this will typically be your admin_owner user id
    assignee_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Optional metadata/context (tool name, last_scan_id, browser/os, plan, etc.)
    meta = db.Column(db.JSON, nullable=True)

    # Optional tags array (store as JSON list for portability)
    tags = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    solved_at  = db.Column(db.DateTime, nullable=True)
    closed_at  = db.Column(db.DateTime, nullable=True)

    # Relationships
    messages = relationship("SupportMessage", back_populates="ticket", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            f"status IN {STATUS_VALUES}", name="ck_support_tickets_status"
        ),
        CheckConstraint(
            f"priority IN {PRIORITY_VALUES}", name="ck_support_tickets_priority"
        ),
        Index("ix_support_tickets_requester_created", "requester_user_id", "created_at"),
        Index("ix_support_tickets_status_priority", "status", "priority"),
    )

class SupportMessage(db.Model):
    __tablename__ = "support_messages"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.BigInteger, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)

    # author_user_id may be null for system messages (auto-reminders, auto-close)
    author_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True, index=True)

    visibility = db.Column(db.String(20), nullable=False, default="public")
    body = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    attachments = relationship("SupportAttachment", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            f"visibility IN {VISIBILITY_VALUES}", name="ck_support_messages_visibility"
        ),
        Index("ix_support_messages_ticket_created", "ticket_id", "created_at"),
    )

class SupportAttachment(db.Model):
    __tablename__ = "support_attachments"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    message_id = db.Column(db.BigInteger, ForeignKey("support_messages.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    mime = db.Column(db.String(100), nullable=False)

    # Pointer to storage (e.g., local path, S3 key, etc.)
    storage_url = db.Column(db.Text, nullable=False)
    checksum = db.Column(db.String(128), nullable=True)

    scan_status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    message = relationship("SupportMessage", back_populates="attachments")

    __table_args__ = (
        CheckConstraint(
            f"scan_status IN {SCAN_STATUS_VALUES}", name="ck_support_attachments_scan_status"
        ),
    )

# ─────────────────────────────────────────────────────────────────────────────
# Snippets (tiny canned responses for solo mode)
# ─────────────────────────────────────────────────────────────────────────────
class SupportSnippet(db.Model):
    __tablename__ = "support_snippets"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title = db.Column(db.String(80), nullable=False)
    body = db.Column(db.Text, nullable=False)  # keep small-ish; UX will paginate list
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

# ─────────────────────────────────────────────────────────────────────────────
# Audit log for sensitive/support actions
# ─────────────────────────────────────────────────────────────────────────────
class SupportAudit(db.Model):
    __tablename__ = "support_audits"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False)              # e.g., status_set, priority_set, assign, upload, download
    resource_type = db.Column(db.String(32), nullable=False)       # ticket|message|attachment|settings
    resource_id = db.Column(db.BigInteger, nullable=False, index=True)
    before = db.Column(db.JSON, nullable=True)
    after = db.Column(db.JSON, nullable=True)
    reason = db.Column(db.String(255), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# ─────────────────────────────────────────────────────────────────────────────
# Admin-editable settings (DB overrides runtime defaults)
# ─────────────────────────────────────────────────────────────────────────────
class SupportSetting(db.Model):
    __tablename__ = "support_settings"

    key = db.Column(db.String(64), primary_key=True)   # e.g., SUPPORT_AUTO_CLOSE_DAYS
    value = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
