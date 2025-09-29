import os
import uuid
from pathlib import Path
from typing import Tuple
from flask import current_app
from werkzeug.utils import secure_filename

CHUNK = 1024 * 1024  # 1 MB

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def _cfg(key, default=None):
    return current_app.config.get(key, default)

def _upload_root() -> Path:
    return Path(_cfg("SUPPORT_UPLOAD_DIR", "./var/support_uploads")).resolve()

def _max_bytes() -> int:
    return int(_cfg("SUPPORT_MAX_UPLOAD_MB", 15)) * 1024 * 1024

def _allowed_mime() -> set:
    return set(_cfg("SUPPORT_ALLOWED_MIME", []))

def _allowed_ext() -> set:
    return {e.lower().lstrip(".") for e in _cfg("SUPPORT_ALLOWED_EXT", [])}

def validate_file(file_storage) -> Tuple[bool, str]:
    """
    Lightweight validation: extension + (best-effort) MIME check.
    """
    filename = file_storage.filename or ""
    if not filename:
        return False, "missing filename"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _allowed_ext():
        return False, f"file type not allowed: .{ext or 'unknown'}"
    # Note: client-supplied mimetype is not authoritative, but still useful.
    mimetype = (file_storage.mimetype or "").lower()
    if _allowed_mime() and mimetype and mimetype not in _allowed_mime():
        return False, f"mimetype not allowed: {mimetype}"
    return True, ""

def save_upload(ticket_id: int, message_id: int, file_storage) -> Tuple[str, int, str, str]:
    """
    Streams upload to disk with size guard. Returns (storage_url, size, mime, final_name).
    - storage_url: absolute path on disk (for now)
    """
    ok, err = validate_file(file_storage)
    if not ok:
        raise ValueError(err)

    root = _upload_root()
    subdir = root / str(ticket_id) / str(message_id)
    _ensure_dir(subdir)

    original = secure_filename(file_storage.filename or f"upload-{uuid.uuid4().hex}")
    unique = f"{uuid.uuid4().hex}_{original}"
    dst = subdir / unique

    max_bytes = _max_bytes()
    total = 0

    # Stream to disk
    with open(dst, "wb") as f:
        while True:
            chunk = file_storage.stream.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                try:
                    f.close()
                    dst.unlink(missing_ok=True)
                finally:
                    pass
                raise ValueError(f"file too large (>{max_bytes} bytes)")
            f.write(chunk)

    mime = (file_storage.mimetype or "").lower()
    return (str(dst), total, mime, original)

def scan_file(path: str) -> str:
    """
    Placeholder AV scan. Return 'clean' | 'infected' | 'failed'.
    Integrate ClamAV/Cloud AV here later; keep it synchronous for now.
    """
    try:
        # TODO: integrate real AV. For now, mark clean.
        return "clean"
    except Exception:
        return "failed"
