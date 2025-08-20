from functools import wraps
import re
from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional, Dict, Tuple
from hashlib import sha256, sha1
import os, time
from extensions import db
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app, flash, redirect, request, url_for, jsonify

from flask_mail import Mail, Message
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt, get_jwt_identity, decode_token, verify_jwt_in_request
)
import requests
from .models import LoginEvent, RefreshToken, User, LocalAuth, OAuthAccount, RecoveryCode, TrustedDevice
from .passwords import COMMON_PASSWORDS

mail = Mail()
utcnow = lambda: datetime.now(timezone.utc)

def init_mail(app):
    mail.init_app(app)

def generate_confirmation_token(email: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    salt = current_app.config.get('SECURITY_PASSWORD_SALT','email-confirm-salt')
    return serializer.dumps(email, salt=salt)

def confirm_token(token: str, expiration: int = 3600*24)  -> Optional[str]:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    salt = current_app.config.get('SECURITY_PASSWORD_SALT','email-confirm-salt')
    try:
        return serializer.loads(token, salt=salt, max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None

def send_email(to: str, subject: str, html_body: str) -> None:
    msg = Message(
        subject,
        recipients=[to],
        html=html_body,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Email send failed - {e}")

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # this will raise if no valid JWT
            verify_jwt_in_request()
        except Exception:
            flash("Please log in first.", "warning")
            # preserve the URL they wanted
            return jsonify({"msg": "Please log in first"}), 401
        return func(*args, **kwargs)
    return wrapper

def init_jwt_manager(app, jwt):
    """
    Register callbacks on the JWTManager instance to check and handle revoked/expired tokens.
    Call this in your factory after you init JWTManager:
        init_jwt_manager(app, jwt)
    """
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        raw_jti   = jwt_payload.get("jti")
        token_type= jwt_payload.get("type") or jwt_payload.get("typ")
        if token_type != "refresh":
            return False

        hashed_jti = sha256(raw_jti.encode("utf-8")).hexdigest()
        token = RefreshToken.query.filter_by(token_hash=hashed_jti).first()

        if token is None or token.revoked or (token.expires_at and token.expires_at <= utcnow()):
            try:
                uid = int(jwt_payload.get("sub"))
                RefreshToken.query.filter_by(user_id=uid, revoked=False).update({"revoked": True})
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True

        return False


    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"msg": "Token has been revoked"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"msg": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err):
        return jsonify({"msg": f"Invalid token"}), 422

    @jwt.unauthorized_loader
    def missing_token_callback(err):
        return jsonify({"msg": "Authorization required"}), 401
    
def jwt_login(user: User) -> Dict[str, str]:
    """
    Issue JWT access and refresh tokens, store refresh JTI in DB, and return both tokens.
    """
    # 🔒 Block inactive accounts (works for local + OAuth + anything else)
    if getattr(user, "is_blocked", False) or getattr(user, "is_deactivated", False):
        # Raise (don’t return) so callers must handle it explicitly
        raise PermissionError("Account is inactive")

    if user.local_auth:
        user.local_auth.failed_logins = 0
        user.local_auth.last_login_at = utcnow()
        db.session.add(user.local_auth)

    str_id        = str(user.id)
    access_token  = create_access_token(identity=str_id)
    refresh_token = create_refresh_token(identity=str_id)

    # decode JTI & expiry from the refresh token
    data       = decode_token(refresh_token)
    raw_jti    = data['jti']
    hashed_jti = sha256(raw_jti.encode('utf-8')).hexdigest()

    rt = RefreshToken(
        user_id    = user.id,
        token_hash = hashed_jti,
        expires_at = datetime.fromtimestamp(data['exp'], tz=timezone.utc)
    )
    db.session.add(rt)
    db.session.commit()

    return {'access_token': access_token, 'refresh_token': refresh_token}

@jwt_required(refresh=True)
def jwt_logout():
    """
    Revoke the current refresh token. Requires @jwt_required(refresh=True) context.
    """
    jti = get_jwt()['jti']
    hashed_jti = sha256(jti.encode('utf-8')).hexdigest()
    token_row = RefreshToken.query.filter_by(token_hash=hashed_jti).first()
    if token_row:
        token_row.revoked = True
        db.session.commit()
    return jsonify({"msg": "Refresh token revoked"}), 200

def login_local(email: str, password: str) -> tuple[dict, str]:
    """
    Attempt to authenticate a user by email+password.
    On success returns (tokens, None), on failure returns (None, error_msg).
    """
    user = User.query.filter_by(email=email.strip().lower()).first()
    la = user.local_auth if user else None

    if not user or not user.local_auth or not user.local_auth.check_password(password):
        # record failed attempt
        if user and user.local_auth:
            user.local_auth.failed_logins += 1
            user.local_auth.last_failed_at = utcnow()
            db.session.commit()
        return None, "Invalid credentials"
    if user.is_blocked or user.is_deactivated:
        return None, "Account is inactive"
    
    if la.failed_logins >= 3:
        lock_expires = (la.last_failed_at or utcnow()) + timedelta(minutes=15)
        if utcnow() < lock_expires:
            return None, "Account locked. Try again later."
        la.failed_logins = 0

    if not la.email_verified:
        return None, "Please verify your email first."

    la.failed_logins = 0
    la.last_login_at = utcnow()
    db.session.add(LoginEvent(
        user_id    = user.id,
        ip_address = request.remote_addr,
        successful = True
    ))

    db.session.commit()

    if user.mfa_setting and user.mfa_setting.enabled and not _is_trusted_device(user.id):
        return None, "MFA_REQUIRED"
    
    tokens = jwt_login(user)
    return tokens, None

# def login_oauth(provider: str, provider_id: str, profile_info: dict) -> Dict[str, str]:
#     """
#     Handle OAuth sign-in/up. Finds or creates the OAuthAccount + User, then issues tokens.
#     profile_info must contain at least 'email'; may include 'name'.
#     """
#     # 1) If we've seen this exact account before → use that user
#     oauth = OAuthAccount.query.filter_by(provider=provider, provider_id=provider_id).first()
#     if oauth:
#         user = oauth.user
#         # return jwt_login(user)
#         return (user, jwt_login(user)) 

#     email = (profile_info.get("email") or "").strip().lower()
#     name  = profile_info.get("name")

#     # 2) If a user already exists with this email → link this provider to that user
#     user = User.query.filter_by(email=email).first()
#     if user:
#         oa = OAuthAccount(provider=provider, provider_id=provider_id, user_id=user.id)
#         db.session.add(oa)
#         db.session.commit()
#         # return jwt_login(user)
#         return (user, jwt_login(user)) 

#     # 3) Otherwise create a new user and link the provider
#     username = generate_username_from_email(email)
#     user = User(email=email, username=username, name=name)
#     db.session.add(user)
#     db.session.flush()  # get user.id

#     oa = OAuthAccount(provider=provider, provider_id=provider_id, user_id=user.id)
#     db.session.add(oa)
#     db.session.commit()

#     # return jwt_login(user)
#     return (user, jwt_login(user)) 


def login_oauth(provider: str, provider_id: str, profile_info: dict) -> tuple[User, dict | None]:
    """
    Handle OAuth sign-in/up. Returns (user, tokens_or_None).
    If MFA is required and device not trusted -> returns (user, None) so the route can redirect to verify.
    """
    # 1) If exact OAuth account exists → use that user
    oauth = OAuthAccount.query.filter_by(provider=provider, provider_id=provider_id).first()
    if oauth:
        user = oauth.user
    else:
        email = (profile_info.get("email") or "").strip().lower()
        name  = profile_info.get("name")

        # 2) If a user already exists with this email → link this provider
        user = User.query.filter_by(email=email).first()
        if user:
            oa = OAuthAccount(provider=provider, provider_id=provider_id, user_id=user.id)
            db.session.add(oa)
            db.session.commit()
        else:
            # 3) Otherwise create a new user and link the provider
            username = generate_username_from_email(email)
            user = User(email=email, username=username, name=name)
            db.session.add(user)
            db.session.flush()  # get user.id

            oa = OAuthAccount(provider=provider, provider_id=provider_id, user_id=user.id)
            db.session.add(oa)
            db.session.commit()

    # ---- Common gate (same spirit as local login) ----
    if getattr(user, "is_blocked", False) or getattr(user, "is_deactivated", False):
        # mirror local: don't issue tokens for inactive accounts
        raise PermissionError("Account is inactive")

    # If MFA is enabled and device isn't trusted → don't mint/set tokens yet
    if user.mfa_setting and user.mfa_setting.enabled and not _is_trusted_device(user.id):
        return user, None

    # Otherwise issue tokens now (route will set cookies)
    return user, jwt_login(user)


def get_current_user() -> Optional[User]:
    """
    Return the User object for the current valid JWT, or None if no token/invalid.
    Use inside @jwt_required‑protected endpoints.
    """
    raw_id = get_jwt_identity()
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    return User.query.get(user_id)

def validate_and_set_password(user, password, confirm, commit=True):
    """
    Validates the two password fields, applies any extra rules, 
    calls user.set_password, and (optionally) commits.
    Returns True on success, False on failure (and flashes a message).
    """
    # 1) Both fields present
    if not password or not confirm:
        flash('Both password fields are required.', 'warning')
        return False

    # 2) Match?
    if password != confirm:
        flash('Passwords do not match.', 'warning')
        return False

    # 3) Minimum length
    if len(password) < 8:
        flash('Password must be at least 8 characters long.', 'warning')
        return False

    # 4) No triple repeats (aaa, 111, $$$, etc)
    if re.search(r'(.)\1\1', password):
        flash('Password must not contain any character repeated three times in a row.', 'warning')
        return False

    # 5) Upper, digit, special
    if not re.search(r'[A-Z]', password):
        flash('Password must include at least one uppercase letter.', 'warning')
        return False
    if not re.search(r'\d', password):
        flash('Password must include at least one digit.', 'warning')
        return False
    if not re.search(r'[^A-Za-z0-9]', password):
        flash('Password must include at least one special character.', 'warning')
        return False

    # 6) No username or email fragments
    lower_pw = password.lower()
    for fragment in (user.username.lower(), user.email.lower(), (user.name or '').lower()):
        if fragment and fragment in lower_pw:
            flash('Password must not contain your username or email.', 'warning')
            return False

    # 7) Not a common/simple password
    if lower_pw in COMMON_PASSWORDS:
        flash('That password is too common. Please choose a stronger one.', 'warning')
        return False
    
    # 7.1) HIBP (API-only): if API says it's breached (>0), block; if API fails, silently allow
    cnt = hibp_count_for_password(password)
    if cnt is not None and cnt > 0 and current_app.config.get("HIBP_BLOCK_ANY", True):
        flash("This password has appeared in known data breaches. Please choose a different one.", "warning")
        return False

    # # 7.5) HIBP k-anonymity check (API-first, offline fallback)
    # count = hibp_count_for_password(password)
    # # Determine if the user is privileged (tighten policy)
    # is_admin = False
    # try:
    #     # If roles relationship exists, treat any 'admin'/'superadmin' as privileged
    #     is_admin = any(getattr(r, "name", "").lower() in {"admin", "superadmin"} for r in getattr(user, "roles", []))
    # except Exception:
    #     pass

    # # Decide per policy
    # admin_block_any   = bool(current_app.config.get("HIBP_ADMIN_BLOCK_ANY", True))
    # block_threshold   = int(current_app.config.get("HIBP_BLOCK_COUNT", 100))

    # if count is not None:
    #     if (is_admin and admin_block_any and count >= 1) or (not is_admin and count >= block_threshold):
    #         flash("This password has appeared in known data breaches. Please choose a different one.", "warning")
    #         return False
    #     # else: allow; optionally you could flash a soft warning if 1–99 for regular users
    # else:
    #     # Graceful degrade: API down & no offline mirror → proceed using local checks only
    #     # (Optional) flash a low-priority note in debug environments
    #     pass
    

    # OK: hash & store it
    # try:
    #     la = user.local_auth or LocalAuth(user_id=user.id)
    #     la.set_password(password)
    # except ValueError as ve:
    #     flash(str(ve), 'warning')
    #     return False

    try:
        la = user.local_auth or LocalAuth(user_id=user.id)
        # **attach it to the user relationship so `user.local_auth` is never None**
        user.local_auth = la
        la.set_password(password)
    except ValueError as ve:
        flash(str(ve), 'warning')
        return False
    
    if commit:
        db.session.add(la)
        db.session.commit()

    return True

def generate_username_from_email(email: str) -> str:
    """Derive a valid, unique username from the email local-part."""
    base = re.sub(r'[^A-Za-z0-9_]', '_', email.split('@')[0])
    base = (base + '_'*5)[:15]  # pad+trim to 5–15
    i = 0
    candidate = base
    while User.query.filter_by(username=candidate).first():
        i += 1
        suffix = str(i)
        candidate = f"{base[:15 - len(suffix)]}{suffix}"
    return candidate

def verify_turnstile(token: str, remote_ip: str | None = None) -> tuple[bool, str | None]:
    """
    Validate a Cloudflare Turnstile token. Returns (ok, error_message_or_None).
    If no secret configured, treat as pass (useful for dev).
    """
    if not token:
        return False, "Missing captcha token"

    secret = current_app.config.get('TURNSTILE_SECRET_KEY')
    if not secret:
        # In dev, you might intentionally skip
        return True, None

    try:
        r = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
            timeout=6,
        )
        data = r.json()
        if data.get("success"):
            return True, None
        return False, ", ".join(data.get("error-codes", []) or [])
    except Exception as e:
        return False, f"captcha-verify-failed: {e}"
    
    
# ---------- HIBP k-anonymity helpers (API-first, offline fallback) ----------

# In-memory prefix cache: { "ABCDE": (fetched_at_epoch, {"SUFFIX": count, ...}) }
_HIBP_CACHE: dict[str, tuple[float, dict[str, int]]] = {}

def _hibp_load_offline_prefix(prefix: str) -> dict[str, int] | None:
    """Load suffixes for a prefix from a local per-prefix file 'PREFIX.txt'."""
    base = current_app.config.get("HIBP_OFFLINE_PREFIX_DIR")
    if not base:
        return None
    path = os.path.join(base, f"{prefix}.txt")
    if not os.path.exists(path):
        return None
    result: dict[str, int] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                suf, cnt = line.split(":", 1)
                if len(suf) == 35:
                    try:
                        result[suf.upper()] = int(cnt)
                    except ValueError:
                        pass
        return result
    except Exception:
        return None

def _hibp_fetch_prefix(prefix: str) -> dict[str, int] | None:
    """Fetch suffix:count map for prefix from API or offline fallback."""
    # 1) Cache hit?
    ttl = int(current_app.config.get("HIBP_CACHE_TTL_SECONDS", 7*24*3600))
    now = time.time()
    cached = _HIBP_CACHE.get(prefix)
    if cached and (now - cached[0]) < ttl:
        return cached[1]

    # 2) API call
    ua = current_app.config.get("HIBP_USER_AGENT", "hibp-check/1.0")
    try:
        r = requests.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"User-Agent": ua, "Add-Padding": "true"},
            timeout=float(current_app.config.get("HIBP_API_TIMEOUT", 2.0)),
        )
        if r.status_code == 200:
            mapping: dict[str, int] = {}
            for line in r.text.splitlines():
                if ":" not in line:
                    continue
                suf, cnt = line.split(":", 1)
                if len(suf) == 35:
                    try:
                        mapping[suf.upper()] = int(cnt)
                    except ValueError:
                        pass
            _HIBP_CACHE[prefix] = (now, mapping)
            return mapping
    except Exception:
        pass  # fall through to offline

    # 3) Offline fallback (optional)
    offline = _hibp_load_offline_prefix(prefix)
    if offline is not None:
        _HIBP_CACHE[prefix] = (now, offline)
        return offline

    return None  # no data available

def hibp_count_for_password(password: str) -> int | None:
    """
    API-only HIBP k-anonymity check.
    Returns count (>=0) if the check worked; returns None if API failed.
    """
    if not current_app.config.get("HIBP_ENABLE", True):
        return 0
    try:
        h = sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = h[:5], h[5:]
        r = requests.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"User-Agent": current_app.config.get("HIBP_USER_AGENT", "hibp-check/1.0"),
                     "Add-Padding": "true"},
            timeout=float(current_app.config.get("HIBP_API_TIMEOUT", 2.0)),
        )
        if r.status_code != 200:
            return None
        for line in r.text.splitlines():
            if ":" not in line:
                continue
            suf, cnt = line.split(":", 1)
            if suf.strip().upper() == suffix:
                try:
                    return int(cnt)
                except ValueError:
                    return None
        return 0
    except Exception:
        return None

# --------- MFA

def _sha(s: str) -> str:
    return sha256(s.encode('utf-8')).hexdigest()

def _is_trusted_device(user_id: int) -> bool:
    """Return True if a non-expired trusted-device cookie maps to this user."""
    td_cookie = request.cookies.get(current_app.config.get("TRUSTED_DEVICE_COOKIE_NAME", "tdid"))
    if not td_cookie:
        return False
    row = TrustedDevice.query.filter_by(token_hash=_sha(td_cookie), user_id=user_id).first()
    if not row or row.expires_at <= utcnow():
        return False
    row.last_used_at = utcnow()
    db.session.commit()
    return True

def _remember_device(user_id: int, user_agent: str) -> tuple[str, datetime]:
    """Create a trusted device row and return (raw_cookie_token, expires_at)."""
    raw = secrets.token_urlsafe(48)
    expires = utcnow() + timedelta(days=int(current_app.config.get("TRUSTED_DEVICE_DAYS", 30)))
    db.session.add(TrustedDevice(
        user_id=user_id,
        token_hash=_sha(raw),
        user_agent=(user_agent or "")[:255],
        created_at=utcnow(),
        expires_at=expires,
    ))
    db.session.commit()
    return raw, expires

def generate_recovery_codes(user_id: int, count: int = 10) -> list[str]:
    """
    Create one-time recovery codes and return the **plaintext** list for display once.
    We store only hashes. Existing unused codes are kept; call a cleanup if you prefer.
    """
    out = []
    for _ in range(count):
        # 10 chars grouped (e.g., XXXXXX-XXXX); adjust length/format as you like
        code = secrets.token_hex(5).upper()
        out.append(code)
        db.session.add(RecoveryCode(
            user_id=user_id,
            code_hash=_sha(code),
            used=False,
            created_at=utcnow(),
        ))
    db.session.commit()
    return out