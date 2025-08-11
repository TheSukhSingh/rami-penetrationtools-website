 # RBAC decorators & helpers (admin:view, admin:edit, etc.)

from functools import wraps
from typing import Iterable, Set
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from admin.errors import Forbidden, Unauthorized

def _collect_scopes(user) -> Set[str]:
    """
    Your Role model stores JSON scopes. Union them for the user.
    """
    scopes = set()
    for role in getattr(user, "roles", []):
        payload = getattr(role, "scopes", None) or {}
        # payload can be list or dict of {scope: true}
        if isinstance(payload, dict):
            scopes |= {k for k, v in payload.items() if v}
        elif isinstance(payload, (list, tuple, set)):
            scopes |= set(payload)
    return scopes

def require_scopes(*required_scopes: str):
    """
    Decorator for API routes. Ensures JWT + required scopes.
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()  # ensures we have an identity
        def wrapper(*args, **kwargs):
            from models import User  # local import to avoid circulars
            user_id = get_jwt_identity()
            if not user_id:
                raise Unauthorized("Missing identity")
            user = db.session.get(User, int(user_id))
            if not user:
                raise Unauthorized("User not found")
            have = _collect_scopes(user)
            missing = [s for s in required_scopes if s not in have]
            if missing:
                raise Forbidden("Insufficient permissions", details={"required": required_scopes, "missing": missing})
            # make user available to the view if you like:
            kwargs["_current_admin_user"] = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
