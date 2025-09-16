
from datetime import datetime, timedelta
from sqlalchemy import func
from tools.models import ToolScanHistory  # ← adjust path if needed
from app import db  # ← adjust if needed


def repo_get_analytics(user_id: int, days: int = 30, tool=None):
    since = datetime.utcnow() - timedelta(days=days)

    base = db.session.query(ToolScanHistory).filter(
        ToolScanHistory.user_id == user_id,
        ToolScanHistory.scanned_at >= since,
    )
    if tool:
        # allow int id or fuzzy tool mention inside command/parameters
        if str(tool).isdigit():
            base = base.filter(ToolScanHistory.tool_id == int(tool))
        else:
            like = f"%{tool}%"
            base = base.filter(
                (ToolScanHistory.command.ilike(like))
                | (ToolScanHistory.parameters.ilike(like))
            )

    totals_runs = base.count()

    # series by day (UTC)
    series_rows = (
        db.session.query(
            func.date(ToolScanHistory.scanned_at).label("day"),
            func.count().label("runs"),
        )
        .filter(
            ToolScanHistory.user_id == user_id,
            ToolScanHistory.scanned_at >= since,
        )
        .group_by(func.date(ToolScanHistory.scanned_at))
        .order_by(func.date(ToolScanHistory.scanned_at))
        .all()
    )
    series = [{"day": str(day), "runs": int(runs)} for day, runs in series_rows]

    # unique users in your own scope is always 1 (this user), but keep the field
    unique_users = 1

    return {"totals": {"runs": int(totals_runs or 0), "unique_users": unique_users}, "series": series}
