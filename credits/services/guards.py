from __future__ import annotations
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from credits.services.entitlements import has_feature

def feature_required(feature: str):
    """
    Decorator: require an active entitlement feature for the current user.
    Use together with @jwt_required() on the route.
    Returns 402 JSON if missing.
    """
    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            user_id = get_jwt_identity()
            if not has_feature(user_id, feature):
                return jsonify({"ok": False, "error": "FEATURE_REQUIRED", "feature": feature}), 402
            return fn(*args, **kwargs)
        return _wrapped
    return _decorator
