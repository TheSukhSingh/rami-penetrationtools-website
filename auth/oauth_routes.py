from flask import flash, request, session, render_template, redirect, jsonify, url_for
from flask_jwt_extended import jwt_required, set_access_cookies, set_refresh_cookies, unset_jwt_cookies, verify_jwt_in_request
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import os, secrets, requests
from auth.models import User
from flask_wtf.csrf import CSRFError 
from . import auth_bp
from .utils import (
    login_required,
    login_oauth, 
    jwt_logout
)
from flask_limiter.util import get_remote_address
from extensions import limiter, csrf

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

DEFAULT_AFTER_LOGIN = "/"

def _after_login_url():
    return session.pop("oauth_next", None) or request.args.get("next") or DEFAULT_AFTER_LOGIN

# ---------- Helper: return provider URLs to the SPA ----------
@auth_bp.route("/providers", methods=["GET"])
def oauth_providers():
    """Return login URLs so the SPA can render 'Continue with ...' buttons."""
    nxt = request.args.get("next")
    return jsonify({
        "google": url_for("auth.google_login", next=nxt, _external=False),
        "github": url_for("auth.github_login", next=nxt, _external=False),
        "google_client_id": GOOGLE_CLIENT_ID,
    }), 200

# =========================
# GOOGLE: Authorization Code
# =========================
@auth_bp.route("/google-login", methods=["GET"])
def google_login():
    state = secrets.token_urlsafe(32)
    session["oauth_state_google"] = state
    if request.args.get("next"):
        session["oauth_next"] = request.args.get("next")

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        "?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={url_for('auth.google_callback', _external=True)}"
        "&scope=openid%20email%20profile"
        "&access_type=offline&include_granted_scopes=true&prompt=consent"
        f"&state={state}"
    )
    return redirect(auth_url)

@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    # CSRF check
    state = request.args.get("state", "")
    if not state or state != session.pop("oauth_state_google", None):
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=state")

    code = request.args.get("code")
    if not code:
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=missing_code")

    # Exchange code -> tokens
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": url_for("auth.google_callback", _external=True),
            "grant_type": "authorization_code",
        },
        timeout=15,
    ).json()

    id_tok = token_resp.get("id_token")
    if not id_tok:
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=google_exchange")

    # Verify ID token
    payload = id_token.verify_oauth2_token(id_tok, grequests.Request(), GOOGLE_CLIENT_ID)
    sub   = payload.get("sub")
    email = payload.get("email")
    name  = payload.get("name")
    if not (sub and email):
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=google_identity")

    try:
        user, tokens = login_oauth("google", sub, {"email": email, "name": name})
        if tokens is None:
            # Stage MFA like local flow
            session['mfa_user'] = user.id
            return redirect(url_for('auth.verify_mfa'))

    except PermissionError:
        return redirect(f"{_after_login_url()}?auth_error=inactive")
    # Mirror local login: set cookies → redirect back to app
    resp = redirect(_after_login_url())
    set_access_cookies(resp, tokens["access_token"])
    set_refresh_cookies(resp, tokens["refresh_token"])
    return resp

@auth_bp.route("/token-signin", methods=["POST"])
@csrf.exempt             # login entry: not carrying our CSRF token
@limiter.limit("10 per minute")
def google_one_tap_signin():
    """
    Google One-Tap: client POSTs { "credential": "<google_id_token>" }.
    Returns:
      - 200 with cookies set on success,
      - 202 with {mfa_required:true} if MFA step-up is required,
      - 4xx with a stable 'code' on errors.
    """
    data = request.get_json(silent=True) or {}
    raw_token = data.get("credential") or data.get("id_token")
    if not raw_token:
        return jsonify(code="BAD_REQUEST", message="Missing credential"), 400

    if not GOOGLE_CLIENT_ID:
        return jsonify(code="SERVER_MISCONFIG", message="Google client id not configured"), 500

    try:
        idinfo = id_token.verify_oauth2_token(raw_token, grequests.Request(), GOOGLE_CLIENT_ID)
    except Exception:
        return jsonify(code="TOKEN_INVALID", message="Could not verify Google ID token"), 401

    iss = idinfo.get("iss", "")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        return jsonify(code="TOKEN_ISSUER_INVALID", message="Invalid token issuer"), 401

    email = (idinfo.get("email") or "").strip().lower()
    email_verified = bool(idinfo.get("email_verified"))
    sub = idinfo.get("sub")  # Google stable user id
    display_name = idinfo.get("name") or idinfo.get("given_name") or ""

    # Require verified Google email for One-Tap create/link
    if not email or not email_verified:
        return jsonify(code="EMAIL_UNVERIFIED", message="Google email must be verified"), 409

    try:
        user, tokens = login_oauth(
            provider="google",
            provider_id=sub,
            profile_info={
                "email": email,
                "name": display_name,
            },
        )
    except PermissionError as pe:
        # e.g., local account is deactivated/blocked OR local email unverified (see utils change below)
        return jsonify(code="FORBIDDEN", message=str(pe)), 403
    except ValueError as ve:
        # e.g., explicit linking conflict
        return jsonify(code="CONFLICT", message=str(ve)), 409

    if tokens is None:
        # MFA required: same contract as your normal OAuth/login path
        session["mfa_user"] = user.id
        return jsonify(mfa_required=True, verify_url=url_for("auth.verify_mfa")), 202

    # Success → set cookies and return ok
    resp = jsonify(ok=True)
    set_access_cookies(resp, tokens["access_token"])
    set_refresh_cookies(resp, tokens["refresh_token"])
    return resp, 200

# =========================
# GITHUB: Authorization Code
# =========================
@auth_bp.route("/github-login", methods=["GET"])
def github_login():
    state = secrets.token_urlsafe(32)
    session["oauth_state_github"] = state
    if request.args.get("next"):
        session["oauth_next"] = request.args.get("next")

    auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        "&scope=user:email"
        f"&redirect_uri={url_for('auth.github_callback', _external=True)}"
        f"&state={state}"
    )
    return redirect(auth_url)

@auth_bp.route("/github/callback", methods=["GET"])
def github_callback():
    state = request.args.get("state", "")
    if not state or state != session.pop("oauth_state_github", None):
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=state")

    code = request.args.get("code")
    if not code:
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=missing_code")

    # Exchange code -> GitHub access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": url_for("auth.github_callback", _external=True),
        },
        timeout=15,
    ).json()

    gh_token = token_resp.get("access_token")
    if not gh_token:
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=github_exchange")

    # Pull user + primary verified email
    u = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {gh_token}"},
        timeout=15,
    ).json()
    emails = requests.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"Bearer {gh_token}"},
        timeout=15,
    ).json()

    email = None
    if isinstance(emails, list):
        primary = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
        email = primary or next((e["email"] for e in emails if e.get("verified")), None)

    if not (u.get("id") and email):
        return redirect(f"{DEFAULT_AFTER_LOGIN}?auth_error=github_identity")

    try:
        user, tokens = login_oauth("github", str(u["id"]), {"email": email, "name": u.get("name") or u.get("login")})
        if tokens is None:
            session['mfa_user'] = user.id
            return redirect(url_for('auth.verify_mfa'))
    except PermissionError:
        return redirect(f"{_after_login_url()}?auth_error=inactive")
    resp = redirect(_after_login_url())
    set_access_cookies(resp, tokens["access_token"])
    set_refresh_cookies(resp, tokens["refresh_token"])
    return resp

# =========================
# Logout (refresh required)
# =========================
@auth_bp.route("/logout", methods=["POST"])
@csrf.exempt  
@limiter.limit("20 per hour", key_func=get_remote_address)
def logout():
    """
    Idempotent logout:
    - Try to verify a refresh JWT (this will also enforce JWT CSRF if cookie is present)
    - If verified, call your server-side revocation (jwt_logout)
    - Always clear access+refresh cookies for the client
    - Always return 200
    """
    try:
        # If your FJWE version supports optional=True:
        verify_jwt_in_request(optional=True, refresh=True)
        try:
            jwt_logout()  # your helper that revokes the refresh token in DB
        except Exception:
            pass
    except Exception:
        # No/invalid refresh cookie (or CSRF mismatch) — that's fine; still clear cookies
        pass

    resp = jsonify({"msg": "Logout successful"})
    unset_jwt_cookies(resp)  # clears both access + refresh cookies
    return resp, 200

