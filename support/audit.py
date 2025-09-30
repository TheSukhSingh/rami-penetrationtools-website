import json
from flask import request
from extensions import db
from support.models import SupportAudit

def log_action(actor_user_id, action: str, resource_type: str, resource_id: int, before=None, after=None, reason: str | None = None):
    """
    Add an audit log row. DOES NOT commit — caller's transaction controls atomicity.
    """
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) if request else None
    except Exception:
        ip = None
    entry = SupportAudit(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        reason=reason,
        ip=ip,
    )
    db.session.add(entry)
    return entry
