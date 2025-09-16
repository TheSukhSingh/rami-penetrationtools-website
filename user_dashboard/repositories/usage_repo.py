# user_dashboard/repositories/usage_repo.py
from datetime import datetime, timedelta
from sqlalchemy import func, asc
from extensions import db
from tools.models import ToolScanHistory, Tool  # models live at project root

def repo_get_analytics(user_id: int, days: int = 30, tool=None):
    """
    Per-user analytics for the last `days` (inclusive of today).
    Optionally filter by tool slug.
    Returns a daily series and totals.
    """
    since_dt = datetime.utcnow() - timedelta(days=days - 1)

    q = (
        db.session.query(
            func.date(ToolScanHistory.scanned_at).label("day"),
            func.count(ToolScanHistory.id).label("runs"),
        )
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since_dt,
        )
    )

    if tool:
        # filter by tool slug if provided
        q = (
            q.join(Tool, Tool.id == ToolScanHistory.tool_id)
             .filter(Tool.slug == tool)
        )

    q = q.group_by("day").order_by(asc("day"))
    rows = q.all()

    series = [{"day": str(d), "runs": int(r)} for d, r in rows]
    total_runs = sum(item["runs"] for item in series)

    return {
        "series": series,
        "total_runs": total_runs,
        "days": days,
        "tool": tool,
    }
