from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt     import Bcrypt
from flask_migrate    import Migrate
import os
from flask_jwt_extended import get_jwt_identity

db      = SQLAlchemy()
bcrypt  = Bcrypt()
migrate = Migrate()


csrf = CSRFProtect()
def _rate_limit_key():
    """
    Prefer the JWT identity if present (without forcing auth here),
    else fall back to client IP. Keeps limits user-scoped for logged-in users.
    """
    try:
        ident = get_jwt_identity()
        if ident is not None and str(ident).strip():
            return f"user:{ident}"
    except Exception:
        pass
    return get_remote_address()

limiter = Limiter(
    key_func=_rate_limit_key,
    # remove the in-memory warning by pointing limiter to Redis
    storage_uri=os.environ.get("RATE_LIMIT_REDIS_URL")
                 or os.environ.get("REDIS_URL")
                 or "memory://",
    default_limits=["300 per 5 minutes"],  # safe default; tune later
)

