from datetime import datetime
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from extensions import db

# db = SQLAlchemy()

class ToolScanHistory(db.Model):
    """
    Persist a record of every tool execution initiated by a user.
    Captures which user ran which tool, the exact command executed,
    the raw output captured from the tool, and a timestamp.
    """
    __tablename__ = 'tool_scan_history'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    tool_name   = db.Column(db.String(50), nullable=False, index=True)
    parameters = db.Column(db.JSON, nullable=False)
    command     = db.Column(db.Text, nullable=False)
    raw_output  = db.Column(db.Text, nullable=False)
    scanned_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    scan_success_state = db.Column(db.Boolean, nullable=False, default=False)

    user = relationship('User', back_populates='scan_history', passive_deletes=True)

