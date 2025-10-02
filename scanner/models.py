from __future__ import annotations
from datetime import datetime
from extensions import db

class ScanResult(db.Model):
    __tablename__ = "scan_results"

    id         = db.Column(db.Integer, primary_key=True)
    sha256     = db.Column(db.String(64), unique=True, index=True, nullable=False)
    filename   = db.Column(db.String(255))
    size       = db.Column(db.BigInteger)
    mime       = db.Column(db.String(128))
    engine     = db.Column(db.String(64))        # e.g., 'clamav' / 'hybrid'
    verdict    = db.Column(db.String(16))        # 'clean' | 'infected' | 'failed' | 'pending'
    signature  = db.Column(db.String(255))       # matched signature name if any
    details    = db.Column(db.JSON)               # engine raw payload, timings, etc.
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
