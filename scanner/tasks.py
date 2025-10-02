# scanner/tasks.py
from __future__ import annotations
import os
from datetime import datetime
from celery_app import celery
from extensions import db
from scanner.models import ScanResult
from scanner.engine_clamav import scan_path_with_clamav

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

@celery.task(name="scanner.scan_file_task", acks_late=True)
def scan_file_task(scan_result_id: int, path: str, filename: str = None, mime: str = None, size: int = None):
    sr = db.session.get(ScanResult, scan_result_id)
    if not sr:
        return {"ok": False, "reason": "scan_result_missing"}

    if not os.path.exists(path):
        sr.verdict = "failed"
        sr.details = {"error": "path not found"}
        sr.scanned_at = datetime.utcnow()
        db.session.commit()
        return {"ok": False, "reason": "path_missing"}

    # Try clamd first
    verdict, signature, raw = ("failed", None, {"error": "no_engine"})
    res = scan_path_with_clamav(path)
    if res:
        verdict, signature, raw = res
    else:
        # Fallback EICAR dev check
        try:
            with open(path, "rb") as f:
                head = f.read(1024 * 1024)
                if EICAR in head:
                    verdict, signature, raw = ("infected", "EICAR-Test-File", {"engine": "fallback-eicar"})
                else:
                    verdict, signature, raw = ("clean", None, {"engine": "fallback-default"})
        except Exception as e:
            verdict, signature, raw = ("failed", None, {"error": str(e)})

    # Write back
    sr.verdict   = verdict
    sr.signature = signature
    sr.filename  = (filename or sr.filename)
    sr.mime      = mime or sr.mime
    sr.size      = size or sr.size
    sr.engine    = "clamav" if (raw and not raw.get("engine") == "fallback-eicar") else (raw.get("engine") or "clamav")
    sr.details   = raw
    sr.scanned_at = datetime.utcnow()
    db.session.commit()
    return {"ok": True, "verdict": verdict}
