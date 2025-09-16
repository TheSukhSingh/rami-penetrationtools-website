from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_
from flask import current_app
import os

# Adjust these imports to your models module if needed
from tools.models import ToolScanHistory, ScanDiagnostics  # ← change path if your models live elsewhere
from app import db  # ← change if your db comes from a different place


def _parse_dates(date_from, date_to):
    """Accept 'YYYY-MM-DD' strings or None; return (dt_from, dt_to_exclusive)."""
    dt_from = None
    dt_to = None
    if date_from:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d")
    if date_to:
        # make 'to' exclusive by pushing to end of day
        dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    return dt_from, dt_to


def repo_get_overview(user_id: int, days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)

    base = db.session.query(ToolScanHistory).filter(
        ToolScanHistory.user_id == user_id,
        ToolScanHistory.scanned_at >= since,
    )

    total = base.count()
    success = base.filter(ToolScanHistory.scan_success_state.is_(True)).count()
    failure = base.filter(ToolScanHistory.scan_success_state.is_(False)).count()

    last_scan = (
        db.session.query(func.max(ToolScanHistory.scanned_at))
        .filter(ToolScanHistory.user_id == user_id)
        .scalar()
    )

    top_rows = (
        db.session.query(
            ToolScanHistory.tool_id,
            func.count().label("runs"),
        )
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
        )
        .group_by(ToolScanHistory.tool_id)
        .order_by(desc("runs"))
        .limit(5)
        .all()
    )
    top_tools = [{"tool_id": tid, "runs": runs} for tid, runs in top_rows]

    return {
        "total_scans": int(total or 0),
        "success_count": int(success or 0),
        "failure_count": int(failure or 0),
        "last_scan_at": last_scan.isoformat() if last_scan else None,
        "top_tools": top_tools,
    }


def repo_list_scans(
    user_id: int,
    tool=None,
    status=None,
    q=None,
    page: int = 1,
    per_page: int = 20,
    date_from=None,
    date_to=None,
):
    dt_from, dt_to = _parse_dates(date_from, date_to)

    qry = (
        db.session.query(ToolScanHistory, ScanDiagnostics)
        .outerjoin(ScanDiagnostics, ScanDiagnostics.scan_id == ToolScanHistory.id)
        .filter(ToolScanHistory.user_id == user_id)
    )

    if tool:
        # allow tool id (int) or slug/name you pass as string id
        if str(tool).isdigit():
            qry = qry.filter(ToolScanHistory.tool_id == int(tool))
        else:
            # if you store tool slug/name in ToolScanHistory.command/parameters, match loosely
            like = f"%{tool}%"
            qry = qry.filter(
                or_(
                    ToolScanHistory.command.ilike(like),
                    ToolScanHistory.parameters.ilike(like),
                )
            )

    if status:
        s = status.upper()
        if s == "SUCCESS":
            qry = qry.filter(ToolScanHistory.scan_success_state.is_(True))
        elif s in ("FAIL", "FAILED", "FAILURE", "ERROR"):
            qry = qry.filter(ToolScanHistory.scan_success_state.is_(False))

    if dt_from:
        qry = qry.filter(ToolScanHistory.scanned_at >= dt_from)
    if dt_to:
        qry = qry.filter(ToolScanHistory.scanned_at < dt_to)

    if q:
        like = f"%{q}%"
        qry = qry.filter(
            or_(
                ToolScanHistory.parameters.ilike(like),
                ToolScanHistory.command.ilike(like),
                ScanDiagnostics.error_detail.ilike(like),
                ScanDiagnostics.value_entered.ilike(like),
            )
        )

    total = qry.count()
    rows = (
        qry.order_by(ToolScanHistory.scanned_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for tsh, diag in rows:
        items.append(
            {
                "id": tsh.id,
                "tool_id": tsh.tool_id,
                "user_id": tsh.user_id,
                "status": (
                    "SUCCESS" if tsh.scan_success_state is True
                    else ("FAILURE" if tsh.scan_success_state is False else None)
                ),
                "scanned_at": (tsh.scanned_at.isoformat() if tsh.scanned_at else None),
                "parameters": tsh.parameters,
                "command": tsh.command,
                "filename_by_user": tsh.filename_by_user,
                "filename_by_be": tsh.filename_by_be,
                "diagnostics": None
                if not diag
                else {
                    "status": (diag.status.value if diag and diag.status else None),
                    "total_domain_count": diag.total_domain_count,
                    "valid_domain_count": diag.valid_domain_count,
                    "invalid_domain_count": diag.invalid_domain_count,
                    "duplicate_domain_count": diag.duplicate_domain_count,
                    "file_size_b": diag.file_size_b,
                    "execution_ms": diag.execution_ms,
                    "error_reason": diag.error_reason,
                    "error_detail": diag.error_detail,
                    "value_entered": diag.value_entered,
                },
            }
        )

    return {"items": items, "page": page, "per_page": per_page, "total": int(total or 0)}


def repo_get_scan_detail(user_id: int, scan_id: int):
    row = (
        db.session.query(ToolScanHistory, ScanDiagnostics)
        .outerjoin(ScanDiagnostics, ScanDiagnostics.scan_id == ToolScanHistory.id)
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.id == scan_id,
        )
        .first()
    )
    if not row:
        return None

    tsh, diag = row
    return {
        "id": tsh.id,
        "tool_id": tsh.tool_id,
        "user_id": tsh.user_id,
        "status": (
            "SUCCESS" if tsh.scan_success_state is True
            else ("FAILURE" if tsh.scan_success_state is False else None)
        ),
        "scanned_at": tsh.scanned_at.isoformat() if tsh.scanned_at else None,
        "parameters": tsh.parameters,
        "command": tsh.command,
        "filename_by_user": tsh.filename_by_user,
        "filename_by_be": tsh.filename_by_be,
        "raw_output": tsh.raw_output,
        "diagnostics": None
        if not diag
        else {
            "status": (diag.status.value if diag and diag.status else None),
            "total_domain_count": diag.total_domain_count,
            "valid_domain_count": diag.valid_domain_count,
            "invalid_domain_count": diag.invalid_domain_count,
            "duplicate_domain_count": diag.duplicate_domain_count,
            "file_size_b": diag.file_size_b,
            "execution_ms": diag.execution_ms,
            "error_reason": diag.error_reason,
            "error_detail": diag.error_detail,
            "value_entered": diag.value_entered,
        },

