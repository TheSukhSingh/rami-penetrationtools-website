from extensions import db
from tools.models import ToolScanHistory

def repo_resolve_download_path(user_id: int, scan_id: int):
    # If you store absolute path in filename_by_be, return it. Otherwise, return None.
    row = (
        db.session.query(ToolScanHistory)
        .filter(ToolScanHistory.id == scan_id, ToolScanHistory.user_id == user_id)
        .first()
    )
    if not row or not row.filename_by_be:
        return None
    return row.filename_by_be
