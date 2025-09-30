from functools import wraps
from flask import abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from auth.models import User  # your existing User model

# ── Solo-mode "admin" test ────────────────────────────────────────────────
def _user_is_admin(user: "User") -> bool:
    """
    Treat any user with a role named 'admin' or 'admin_owner' as admin.
    Also allow via scopes that start with 'admin.' if your model exposes them.
    This lets you keep using your existing roles while presenting a 2-role world.
    """
    try:
        role_names = {r.name for r in (user.roles or [])}
        if "admin" in role_names or "admin_owner" in role_names:
            return True

        # Fallback: flatten scopes from roles if available
        scopes = set()
        for r in (user.roles or []):
            if getattr(r, "scopes", None):
                scopes.update(r.scopes)
        if any(s.startswith("admin.") for s in scopes):
            return True
    except Exception:
        pass
    return False


def current_user_and_admin():
    """
    Returns (user, is_admin). Requires valid JWT.
    """
    ident = get_jwt_identity()
    user = None
    if ident is not None:
        user = User.query.filter_by(id=ident).first()
    return user, (bool(user) and _user_is_admin(user))


def admin_required(fn):
    """
    Decorator for admin-only endpoints in Solo Support Mode.
    """
    @jwt_required()
    @wraps(fn)
    def _wrapped(*args, **kwargs):
        user, is_admin = current_user_and_admin()
        if not is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return _wrapped


def auth_required(fn):
    """
    Decorator for authenticated endpoints (user or admin).
    """
    @jwt_required()
    @wraps(fn)
    def _wrapped(*args, **kwargs):
        return fn(*args, **kwargs)
    return _wrapped
