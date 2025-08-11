from contextlib import contextmanager
from typing import Any, Dict, Optional
from flask import request
from flask_jwt_extended import get_jwt_identity
from extensions import db
from admin.errors import AdminError
from admin.models import AdminAuditLog  

def record_admin_action(
    *,
    action: str,
    subject_type: str,
    subject_id: Optional[int],
    success: bool = True,
    meta: Optional[Dict[str, Any]] = None,
    actor_id: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    actor_id = actor_id or get_jwt_identity()
    ip = ip or request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = user_agent or request.headers.get("User-Agent")
    log = AdminAuditLog(
        actor_id=actor_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        success=success,
        ip=ip,
        user_agent=user_agent,
        meta=meta or {},
    )
    db.session.add(log)
    # don't raise if audit write fails; best-effort
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

@contextmanager
def audit_context(*, action: str, subject_type: str, subject_id: Optional[int], meta: Optional[Dict[str, Any]] = None):
    """
    Usage:
      with audit_context(action="users.update", subject_type="user", subject_id=user_id, meta={"before": before}) as meta:
          ... do work ...
          meta["after"] = after
    """
    _meta = dict(meta or {})
    try:
        yield _meta
        record_admin_action(action=action, subject_type=subject_type, subject_id=subject_id, success=True, meta=_meta)
    except AdminError:
        record_admin_action(action=action, subject_type=subject_type, subject_id=subject_id, success=False, meta=_meta)
        raise
    except Exception:
        record_admin_action(action=action, subject_type=subject_type, subject_id=subject_id, success=False, meta=_meta)
        raise
