from datetime import datetime
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from extensions import db
import enum
# db = SQLAlchemy()

class ToolScanHistory(db.Model):
    """
    Persist a record of every tool execution initiated by a user.
    Captures which user ran which tool, the exact command executed,
    the raw output captured from the tool, and a timestamp.
    """
    __tablename__ = 'tool_scan_history'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    tool_name          = db.Column(db.String(50), nullable=False, index=True)
    parameters         = db.Column(db.JSON, nullable=False)
    command            = db.Column(db.Text, nullable=False)
    raw_output         = db.Column(db.Text, nullable=False)
    scanned_at         = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    scan_success_state = db.Column(db.Boolean, nullable=False, default=False)
    filename           = db.Column(db.String(255), nullable=True)
    input_path         = db.Column(db.String(512), nullable=True)
    output_path        = db.Column(db.String(512), nullable=True)

    user = relationship('User', back_populates='scan_history', passive_deletes=True)

    scan_diagnostics = db.relationship(
        'ScanDiagnostics',
        back_populates='tool_scan_history',
        uselist=False,
    )


class ScanStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class ErrorReason(enum.Enum):
    NOT_LOGGED_IN       = "NOT_LOGGED_IN"
    FILE_TOO_LARGE      = "FILE_TOO_LARGE"
    INVALID_PARAMS      = "INVALID_PARAMS"
    TOO_MANY_DOMAINS    = "TOO_MANY_DOMAINS"
    TIMEOUT             = "TIMEOUT"
    OTHER               = "OTHER"

class ScanDiagnostics(db.Model):
    """
    A record for each scan, whether it crashed or returned successfully.
    Listing out the reasons for scan crash/failure, so better analysis,
    and easy to target on the point to improve our program on.
    """
    __tablename__ = 'scan_diagnostics'
    id               = db.Column(
                        db.Integer,
                        primary_key=True
                        )
    scan_id          = db.Column(
                        db.Integer, 
                        db.ForeignKey('tool_scan_history.id', ondelete='SET NULL'), 
                        nullable=True, 
                        index=True
                        )
    status           = db.Column(
                          db.Enum(ScanStatus, name="scan_status_enum"),
                          nullable=False
                       )
    domain_count     = db.Column(db.Integer, nullable=False)
    file_size_b      = db.Column(db.Integer, nullable=True)
    execution_ms     = db.Column(db.Integer, nullable=False)
    error_reason     = db.Column(
                          db.Enum(ErrorReason, name="error_reason_enum"),
                          nullable=True
                       )
    error_detail     = db.Column(db.Text, nullable=True)
    created_at       = db.Column(
                          db.DateTime,
                          default=datetime.utcnow,
                          nullable=False,
                          index=True
                       )

    tool_scan_history = relationship('ToolScanHistory', back_populates='scan_diagnostics', passive_deletes=True, uselist=False)




