import os
from flask import current_app
from tools.models import ToolScanHistory  # ← adjust path if needed


def repo_resolve_download_path(user_id: int, scan_id: int):
    row = ToolScanHistory.query.filter_by(id=scan_id, user_id=user_id).first()
    if not row:
        return None

    candidate = row.filename_by_be or row.filename_by_user
    if not candidate:
        return None

    # absolute path?
    if os.path.isabs(candidate) and os.path.exists(candidate):
        return candidate

    base = (
        current_app.config.get("DOWNLOAD_DIR")
        or os.path.join(current_app.instance_path, "downloads")
    )
    path = os.path.join(base, candidate)
    return path if os.path.exists(path) else None
