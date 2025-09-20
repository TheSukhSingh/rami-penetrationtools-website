# account/email_tokens.py
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

_SALT = "account-email-change"

def _ser():
    # Uses your app SECRET_KEY (already configured) for signing
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)

def make_email_change_token(user_id: int, new_email: str) -> str:
    """Create a signed, time-limited token carrying user_id + new_email."""
    return _ser().dumps({"uid": user_id, "new": new_email})

def parse_email_change_token(token: str, max_age: int = 3600):
    """
    Verify and unpack the token.
    Returns (uid, new_email) on success, or 'expired' / 'bad' on failure.
    This matches the check in routes: `if not isinstance(uid_new, tuple): ...`
    """
    try:
        data = _ser().loads(token, max_age=max_age)
        return (data["uid"], data["new"])
    except SignatureExpired:
        return "expired"
    except BadSignature:
        return "bad"
