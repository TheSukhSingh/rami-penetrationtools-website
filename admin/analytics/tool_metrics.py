from tools.models import ScanJob, ScanResult
from datetime import datetime, timedelta


def scans_per_tool(days=7):
    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=days)
    results = (
        ScanResult.query
        .filter(ScanResult.created_at >= cutoff)
        .with_entities(ScanResult.tool_name, db.func.count())
        .group_by(ScanResult.tool_name)
        .all()
    )
    return {tool: count for tool, count in results}