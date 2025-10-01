# scanner/facade.py
from __future__ import annotations
import hashlib, os, time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app
from extensions import db
from scanner.models import ScanResult
from scanner.engine_clamav import scan_path_with_clamav

# Optional Celery
try:
    from scanner.tasks import scan_file_task  # noqa
    HAS_CELERY = True
except Exception:
    HAS_CELERY = False

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

def _sha256_of_path(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _cache_ttl_days() -> int:
    return int(current_app.config.get("SCANNER_CACHE_TTL_DAYS", 30))

def _cache_fresh(sr: ScanResult) -> bool:
    if not sr or not sr.scanned_at:
        return False
    return (datetime.utcnow() - sr.scanned_at) <= timedelta(days=_cache_ttl_days())

def _inline_fast_scan(path: str):
    # 1) ClamAV if available
    res = scan_path_with_clamav(path)
    if res:  # engine available
        verdict, signature, raw = res
        return verdict, signature, raw

    # 2) Fallback EICAR detector (dev convenience)
    try:
        with open(path, "rb") as f:
            head = f.read(1024 * 1024)
            if EICAR in head:
                return "infected", "EICAR-Test-File", {"engine": "fallback-eicar"}
    except Exception as e:
        return "failed", None, {"error": str(e)}

    # 3) Default
    return "clean", None, {"engine": "fallback-default"}

def scan_file(path: str, *, mode: str = "sync", timeout_ms: int = 1200,
              filename: Optional[str] = None, mime: Optional[str] = None, size: Optional[int] = None,
              context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main entrypoint.
    Returns: {"verdict": "clean|infected|failed|pending", "scan_id": int|None, "sha256": "..."}
    """
    assert os.path.exists(path), f"path not found: {path}"
    sha = _sha256_of_path(path)

    # Cache
    sr = ScanResult.query.filter_by(sha256=sha).first()
    if sr and _cache_fresh(sr) and sr.verdict in ("clean", "infected"):
        return {"verdict": sr.verdict, "scan_id": sr.id, "sha256": sha}

    # (Re)create cache row as pending
    if not sr:
        sr = ScanResult(sha256=sha, filename=(filename or os.path.basename(path))[:255],
                        size=size, mime=mime, engine=None, verdict="pending", signature=None,
                        details=None, scanned_at=datetime.utcnow())
        db.session.add(sr)
        db.session.commit()
    else:
        sr.verdict = "pending"
        sr.scanned_at = datetime.utcnow()
        db.session.commit()

    # sync fast-path
    if mode == "sync":
        deadline = time.time() + (timeout_ms / 1000.0)
        verdict, signature, raw = _inline_fast_scan(path)
        if time.time() <= deadline:
            # write result
            sr.verdict   = verdict
            sr.signature = signature
            sr.engine    = "clamav" if (raw and not raw.get("engine") == "fallback-eicar") else (raw.get("engine") or "clamav")
            sr.details   = raw
            sr.scanned_at = datetime.utcnow()
            db.session.commit()
            return {"verdict": verdict, "scan_id": sr.id, "sha256": sha}
        # past deadline → fallthrough to async

    # async (or forced) path via Celery
    if HAS_CELERY:
        # enqueue once; idempotent by sha
        scan_file_task.delay(scan_result_id=sr.id, path=path,
                             filename=(filename or os.path.basename(path))[:255],
                             mime=mime, size=size)
        return {"verdict": "pending", "scan_id": sr.id, "sha256": sha}

    # if no Celery, return the sync verdict we computed (or failed) to avoid pending
    verdict, signature, raw = _inline_fast_scan(path)
    sr.verdict   = verdict
    sr.signature = signature
    sr.engine    = "clamav" if (raw and not raw.get("engine") == "fallback-eicar") else (raw.get("engine") or "clamav")
    sr.details   = raw
    sr.scanned_at = datetime.utcnow()
    db.session.commit()
    return {"verdict": verdict, "scan_id": sr.id, "sha256": sha}

def get_scan_result(scan_id: int) -> Optional[Dict[str, Any]]:
    sr = ScanResult.query.filter_by(id=scan_id).first()
    if not sr:
        return None
    return {
        "scan_id": sr.id,
        "sha256": sr.sha256,
        "verdict": sr.verdict,
        "signature": sr.signature,
        "engine": sr.engine,
        "scanned_at": (sr.scanned_at.isoformat() if sr.scanned_at else None),
        "details": sr.details,
    }
