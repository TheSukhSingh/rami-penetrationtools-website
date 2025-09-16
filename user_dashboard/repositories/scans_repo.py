from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_, and_, distinct
from extensions import db
# Adjust imports if your models live elsewhere:
from tools.models import ToolScanHistory, ScanDiagnostics, Tool

def _status_filter(q, status):
    if not status:
        return q
    status = status.upper()
    if status in {"SUCCESS", "FAILURE"}:
        return q.filter(ScanDiagnostics.status == status)
    return q

def _tool_filter(q, tool_slug):
    if not tool_slug:
        return q
    return q.filter(Tool.slug == tool_slug)

def _date_filter(q, date_from, date_to):
    if date_from:
        q = q.filter(ToolScanHistory.scanned_at >= date_from)
    if date_to:
        q = q.filter(ToolScanHistory.scanned_at <= date_to)
    return q

def _search_filter(q, qtext):
    if not qtext:
        return q
    like = f"%{qtext}%"
    return q.filter(or_(
        ToolScanHistory.filename_by_user.ilike(like),
        ToolScanHistory.command.ilike(like),
        Tool.name.ilike(like),
        Tool.slug.ilike(like),
    ))

def _scan_to_dict(r):
    # r is (history, diag, tool)
    h, d, t = r
    return {
        "id": h.id,
        "tool": {"id": t.id, "slug": t.slug, "name": t.name},
        "scanned_at": h.scanned_at.isoformat() if h.scanned_at else None,
        "status": getattr(d, "status", None),
        "duration_ms": getattr(d, "duration_ms", None),
        "filename_by_user": h.filename_by_user,
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
    base = (
        db.session.query(ToolScanHistory, ScanDiagnostics, Tool)
        .join(Tool, Tool.id == ToolScanHistory.tool_id)
        .outerjoin(ScanDiagnostics, ScanDiagnostics.scan_id == ToolScanHistory.id)
        .filter(ToolScanHistory.user_id == user_id)
    )

    # tool filter (accepts slug)
    if tool:
        base = base.filter(Tool.slug == tool)

    # status filter (matches diagnostics if present)
    if status:
        base = base.filter(ScanDiagnostics.status == status)

    # date range filters
    if date_from:
        base = base.filter(ToolScanHistory.scanned_at >= date_from)
    if date_to:
        base = base.filter(ToolScanHistory.scanned_at <= date_to)

    # free-text search in filename or command/parameters (if provided)
    if q:
        like = f"%{q}%"
        base = base.filter(
            (ToolScanHistory.filename_by_user.ilike(like)) |
            (ToolScanHistory.filename_by_be.ilike(like)) |
            (ToolScanHistory.command.ilike(like))
        )

    total = base.with_entities(func.count(ToolScanHistory.id)).scalar() or 0

    rows = (
        base.order_by(desc(ToolScanHistory.scanned_at))
            .limit(per_page)
            .offset((page - 1) * per_page)
            .all()
    )

    items = []
    for h, d, t in rows:
        items.append({
            "id": h.id,
            "tool": {"id": t.id, "slug": t.slug, "name": t.name},
            "status": d.status if d else None,
            "scanned_at": h.scanned_at.isoformat() if h.scanned_at else None,
            "filename": h.filename_by_be or h.filename_by_user,
        })

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": int(total),
    }


def repo_get_scan_detail(user_id: int, scan_id: int):
    row = (
        db.session.query(ToolScanHistory, ScanDiagnostics, Tool)
        .join(Tool, Tool.id == ToolScanHistory.tool_id)
        .outerjoin(ScanDiagnostics, ScanDiagnostics.tool_scan_history_id == ToolScanHistory.id)
        .filter(ToolScanHistory.id == scan_id, ToolScanHistory.user_id == user_id)
        .first()
    )
    if not row:
        return {"id": scan_id, "not_found": True}

    h, d, t = row
    raw = h.raw_output or ""
    preview = raw[:5000]  # avoid huge payloads
    return {
        "id": h.id,
        "tool": {"id": t.id, "slug": t.slug, "name": t.name},
        "parameters": h.parameters or {},
        "command": h.command,
        "scanned_at": h.scanned_at.isoformat() if h.scanned_at else None,
        "status": getattr(d, "status", None),
        "duration_ms": getattr(d, "duration_ms", None),
        "error_detail": getattr(d, "error_detail", None),
        "raw_output_preview": preview,
        "raw_output_truncated": len(raw) > len(preview),
        "download_available": bool(h.filename_by_be),
        "filename_by_user": h.filename_by_user,
    }

def repo_get_overview(user_id: int, days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)

    # total scans (for this user in window)
    total = (
        db.session.query(func.count(ToolScanHistory.id))
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
        )
        .scalar()
        or 0
    )

    # success / failed using OUTER JOIN to diagnostics and DISTINCT on scan id
    success = (
        db.session.query(func.count(distinct(ToolScanHistory.id)))
        .outerjoin(ScanDiagnostics, ScanDiagnostics.scan_id == ToolScanHistory.id)
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
            ScanDiagnostics.status == "SUCCESS",
        )
        .scalar()
        or 0
    )

    failed = (
        db.session.query(func.count(distinct(ToolScanHistory.id)))
        .outerjoin(ScanDiagnostics, ScanDiagnostics.scan_id == ToolScanHistory.id)
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
            ScanDiagnostics.status == "FAILED",
        )
        .scalar()
        or 0
    )

    # top tools for the user in the window
    by_tool_rows = (
        db.session.query(
            Tool.slug,
            Tool.name,
            func.count(ToolScanHistory.id).label("runs"),
        )
        .join(Tool, Tool.id == ToolScanHistory.tool_id)
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
        )
        .group_by(Tool.slug, Tool.name)
        .order_by(desc("runs"))
        .limit(10)
        .all()
    )
    by_tool = [{"slug": slug, "name": name, "runs": int(runs)} for slug, name, runs in by_tool_rows]

    return {
        "summary": {
            "total": int(total),
            "success": int(success),
            "failed": int(failed),
            "days": days,
        },
        "by_tool": by_tool,
    }
