from functools import wraps
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from hashlib import sha256

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app, flash, redirect, request, url_for, jsonify

from flask_mail import Mail, Message
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt, get_jwt_identity, decode_token, verify_jwt_in_request
)
from .models import LoginEvent, RefreshToken, db, User, LocalAuth, OAuthAccount
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
            return redirect(url_for('auth.login_page', next=request.url))
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
        raw_jti  = jwt_payload.get("jti")
        hashed_jti = sha256(raw_jti.encode('utf-8')).hexdigest()
        token_type = jwt_payload.get("type")
        # Only refresh tokens are stored/persisted
        if token_type == "refresh":
            token = RefreshToken.query.filter_by(token_hash=hashed_jti).first()
            return token is None or token.revoked
        # Access tokens are stateless; treat as not revoked
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
    # reset failure counters if present
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

    tokens = jwt_login(user)
    return tokens, None

def login_oauth(provider: str, provider_id: str, profile_info: dict) -> Dict[str, str]:
    """
    Handle OAuth sign‑in/up. Finds or creates the OAuthAccount + User, then issues tokens.
    profile_info should contain at least 'email' and optionally 'name'.
    """
    oauth = OAuthAccount.query.filter_by(
        provider=provider, provider_id=provider_id
    ).first()

    if oauth:
        user = oauth.user
    else:
        # create new user
        email = profile_info.get("email")
        name = profile_info.get("name")
        username = generate_username_from_email(email)
        user = User(email=email, username=username, name=name)
        db.session.add(user)
        db.session.commit()

        oauth = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_id=provider_id
        )
        db.session.add(oauth)
        db.session.commit()

    return jwt_login(user)

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
