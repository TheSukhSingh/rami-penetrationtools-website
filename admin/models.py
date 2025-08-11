from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from extensions import db


class AdminAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, index=True)
    action = db.Column(db.String(64), nullable=False)
    subject_type = db.Column(db.String(32), nullable=False)
    subject_id = db.Column(db.Integer)
    success = db.Column(db.Boolean, default=True, nullable=False)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    meta = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)