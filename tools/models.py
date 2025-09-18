from datetime import datetime, timezone, date
import enum
from sqlalchemy import UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import relationship
from extensions import db
from mixin import PrettyIdMixin

utcnow = lambda: datetime.now(timezone.utc)

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow,
                           onupdate=utcnow, nullable=False)

class ToolScanHistory(db.Model, PrettyIdMixin):
    """
    Persist a record of every tool execution initiated by a user.
    Captures which user ran which tool, the exact command executed,
    the raw output captured from the tool, and a timestamp.
    """
    __tablename__ = 'tool_scan_history'
    _pretty_prefix = "SC"
    _pretty_date_attr = "scanned_at"
    
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    tool_id            = db.Column(db.Integer, db.ForeignKey('tools.id', ondelete='SET NULL'), nullable=True, index=True)
    parameters         = db.Column(db.JSON, nullable=False, default=dict)
    command            = db.Column(db.Text, nullable=False)
    raw_output         = db.Column(db.Text, nullable=False, default="")
    scanned_at         = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    scan_success_state = db.Column(db.Boolean, nullable=True)
    filename_by_user   = db.Column(db.String(255), nullable=True)
    filename_by_be     = db.Column(db.String(255), nullable=True)
    
    user = relationship('User', back_populates='scan_history', passive_deletes=True)
    tool = relationship('Tool', back_populates='scan_history', passive_deletes=True)

    scan_diagnostics = db.relationship(
        'ScanDiagnostics',
        back_populates='tool_scan_history',
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index('ix_tool_scan_history_user_scanned', 'user_id', 'scanned_at'),
        db.Index('ix_tool_scan_history_tool_scanned', 'tool_id', 'scanned_at'),
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
                        db.ForeignKey('tool_scan_history.id', ondelete='CASCADE'), 
                        nullable=False, 
                        index=True,
                        unique=True
                        )
    status           = db.Column(
                          db.Enum(ScanStatus, name="scan_status_enum"),
                          nullable=False
                       )
    total_domain_count       = db.Column(db.Integer, nullable=True)
    valid_domain_count       = db.Column(db.Integer, nullable=True)
    invalid_domain_count     = db.Column(db.Integer, nullable=True)
    duplicate_domain_count   = db.Column(db.Integer, nullable=True)
    
    file_size_b      = db.Column(db.Integer, nullable=True)
    execution_ms     = db.Column(db.Integer, nullable=False)
    error_reason     = db.Column(
                          db.Enum(ErrorReason, name="error_reason_enum"),
                          nullable=True
                       )
    error_detail     = db.Column(db.Text, nullable=True)
    value_entered    = db.Column(db.Integer, nullable=True)
    created_at       = db.Column(
                          db.DateTime(timezone=True),
                          default=utcnow,
                          nullable=False,
                          index=True
                       )

    tool_scan_history = relationship('ToolScanHistory', back_populates='scan_diagnostics', passive_deletes=True, uselist=False)


# --- Tools catalog & analytics -----------------------------------------------

class ToolCategory(db.Model, TimestampMixin):
    """
    Admin-manageable headings/groups (e.g., Reconnaissance, Exploitation).
    Shows on the Tools page; tools can belong to multiple categories.
    """
    __tablename__ = "tool_categories"

    id          = db.Column(db.Integer, primary_key=True)
    slug        = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name        = db.Column(db.String(128), nullable=False, index=True)
    description = db.Column(db.String(255))
    enabled     = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order  = db.Column(db.Integer, default=100, nullable=False, index=True)
    icon        = db.Column(db.String(128))   # optional: name or SVG key
    color       = db.Column(db.String(32))    # optional: tailwind-like token

    # Links to tools (association rows)
    tool_links = relationship(
        "ToolCategoryLink",
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<ToolCategory {self.slug} enabled={self.enabled}>"


class ToolCategoryLink(db.Model, TimestampMixin):
    """
    Association table (many-to-many) Tool <-> ToolCategory with per-category ordering.
    """
    __tablename__ = "tool_category_link"
    __table_args__ = (
        UniqueConstraint("category_id", "tool_id", name="uq_tool_category_link"),
        Index("ix_tool_category_order", "category_id", "sort_order"),
        Index("ix_tool_category_tool", "tool_id", "category_id"),
    )

    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        ForeignKey("tool_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id     = db.Column(
        db.Integer,
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order  = db.Column(db.Integer, default=100, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Relationships
    category = relationship("ToolCategory", back_populates="tool_links", passive_deletes=True)
    tool     = relationship("Tool", back_populates="category_links", passive_deletes=True)

    def __repr__(self):
        return f"<ToolCategoryLink cat={self.category_id} tool={self.tool_id} order={self.sort_order}>"

class Tool(db.Model, TimestampMixin):
    """
    Canonical list of tools that your app exposes.
    """
    __tablename__ = "tools"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False, index=True)
    version = db.Column(db.String(64))
    repo_url = db.Column(db.String(255))
    last_update_at = db.Column(db.DateTime(timezone=True))
    usage_count = db.Column(db.Integer, default=0, nullable=False)  # denormalized total
    meta_info = db.Column(db.JSON)  # free-form config, defaults, flags

    # backrefs
    daily_usage = relationship("ToolUsageDaily", back_populates="tool", cascade="all, delete-orphan")
    scan_history = relationship("ToolScanHistory", back_populates="tool") 
    category_links = relationship(
        "ToolCategoryLink",
        back_populates="tool",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Tool {self.slug} enabled={self.enabled}>"


class ToolUsageDaily(db.Model):
    """
    Pre-aggregated daily usage to power fast charts.
    One row per (tool_id, day).
    """
    __tablename__ = "tool_usage_daily"
    __table_args__ = (
        UniqueConstraint("tool_id", "day", name="uq_tool_usage_daily_tool_day"),
        Index("ix_tool_usage_daily_day", "day"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tool_id = db.Column(db.Integer, ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True)
    day = db.Column(db.Date, default=date.today, nullable=False)
    runs = db.Column(db.Integer, default=0, nullable=False)
    unique_users = db.Column(db.Integer, default=0, nullable=False)

    tool = relationship("Tool", back_populates="daily_usage")

    def __repr__(self):
        return f"<ToolUsageDaily tool={self.tool_id} day={self.day} runs={self.runs}>"

class WorkflowDefinition(db.Model, TimestampMixin, PrettyIdMixin):
    """
    A reusable workflow ("preset") that captures the canvas graph and per-node config.
    Stores the full graph as JSON for v1; we can normalize later if needed.
    """
    __tablename__ = "workflow_definitions"
    _pretty_prefix = "WF"

    id            = db.Column(db.Integer, primary_key=True)
    owner_id      = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    title         = db.Column(db.String(150), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    version       = db.Column(db.Integer, nullable=False, default=1)
    is_shared     = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_archived   = db.Column(db.Boolean, nullable=False, default=False, index=True)
    forked_from_id= db.Column(db.Integer, db.ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True)
    graph_json    = db.Column(db.JSON, nullable=False, default=dict)  # { nodes: [...], edges: [...] }

    runs          = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True)
    fork_children = relationship("WorkflowDefinition", remote_side=[id])

    __table_args__ = (
        Index("ix_workflow_def_owner_updated", "owner_id", "updated_at"),
        Index("ix_workflow_def_shared", "is_shared", "updated_at"),
    )

class WorkflowRunStatus(enum.Enum):
    QUEUED    = "QUEUED"
    RUNNING   = "RUNNING"
    PAUSED    = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    CANCELED  = "CANCELED"

class WorkflowRun(db.Model, TimestampMixin, PrettyIdMixin):
    __tablename__ = "workflow_runs"
    _pretty_prefix = "WR"

    id                  = db.Column(db.Integer, primary_key=True)
    workflow_id         = db.Column(db.Integer, db.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status              = db.Column(db.Enum(WorkflowRunStatus, name="workflow_run_status_enum"), nullable=False, default=WorkflowRunStatus.QUEUED)
    current_step_index  = db.Column(db.Integer, nullable=False, default=0)
    total_steps         = db.Column(db.Integer, nullable=False, default=0)
    progress_pct        = db.Column(db.Float,   nullable=False, default=0.0)
    started_at          = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    finished_at         = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    summary_json        = db.Column(db.JSON, nullable=True)

    workflow            = relationship("WorkflowDefinition", back_populates="runs")
    steps               = relationship("WorkflowRunStep", back_populates="run",
                                       order_by="WorkflowRunStep.step_index",
                                       cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("ix_workflow_run_status_updated", "status", "updated_at"),
        Index("ix_workflow_run_user_updated", "user_id", "updated_at"),
    )

class WorkflowStepStatus(enum.Enum):
    QUEUED    = "QUEUED"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    SKIPPED   = "SKIPPED"
    CANCELED  = "CANCELED"

class WorkflowRunStep(db.Model, TimestampMixin):
    __tablename__ = "workflow_run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_workflow_run_step_index"),
        Index("ix_workflow_run_steps_run", "run_id", "step_index"),
    )

    id                   = db.Column(db.Integer, primary_key=True)
    run_id               = db.Column(db.Integer, db.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index           = db.Column(db.Integer, nullable=False)  # 0-based
    tool_id              = db.Column(db.Integer, db.ForeignKey("tools.id", ondelete="SET NULL"), nullable=True, index=True)
    status               = db.Column(db.Enum(WorkflowStepStatus, name="workflow_step_status_enum"), nullable=False, default=WorkflowStepStatus.QUEUED)
    started_at           = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at          = db.Column(db.DateTime(timezone=True), nullable=True)

    input_manifest       = db.Column(db.JSON, nullable=True)
    output_manifest      = db.Column(db.JSON, nullable=True)

    tool_scan_history_id = db.Column(db.Integer, db.ForeignKey("tool_scan_history.id", ondelete="SET NULL"), nullable=True, index=True)
    celery_task_id       = db.Column(db.String(50), nullable=True, index=True)
    
    run                  = relationship("WorkflowRun", back_populates="steps")
    tool                 = relationship("Tool", passive_deletes=True)
    tool_scan_history    = relationship("ToolScanHistory", passive_deletes=True)