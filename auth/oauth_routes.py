from flask import flash, request, session, render_template, redirect, jsonify, url_for
from flask_jwt_extended import jwt_required, set_access_cookies, set_refresh_cookies, unset_jwt_cookies
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import os, secrets, requests

from auth.models import User

from . import auth_bp
from .utils import (
    login_required,
    login_oauth, 
    jwt_logout
)
from flask_limiter.util import get_remote_address
from extensions import limiter

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
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

# Optional: Google One-Tap / JS ID token -> POST to this endpoint
@auth_bp.route("/token-signin", methods=["POST"])
def google_token_signin():
    try:
        id_tok = (request.json or {}).get("credential") or request.form.get("credential")
        payload = id_token.verify_oauth2_token(id_tok, grequests.Request(), GOOGLE_CLIENT_ID)
        sub   = payload.get("sub")
        email = payload.get("email")
        name  = payload.get("name")

        try:
            user, tokens = login_oauth("google", sub, {"email": email, "name": name})
            if tokens is None:
                session['mfa_user'] = user.id
                return jsonify({"mfa_required": True, "verify_url": url_for('auth.verify_mfa')}), 202
        except PermissionError:
            return jsonify({"msg": "Account is inactive"}), 403
        resp = jsonify({"msg": "Login successful"})
        set_access_cookies(resp, tokens["access_token"])
        set_refresh_cookies(resp, tokens["refresh_token"])
        return resp, 200
    except Exception:
        return jsonify({"msg": "Google token invalid"}), 400

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
@jwt_required(refresh=True)
@limiter.limit("20 per hour", key_func=get_remote_address)
def logout():
    # Revoke server-side + clear cookies for the client
    jwt_logout()
    resp = jsonify({"msg": "Logout successful"})
    unset_jwt_cookies(resp)
    return resp, 200





# @auth_bp.route('/token-signin', methods=['POST'])
# def token_signin():
#     token = request.json.get('id_token')
#     if not token:
#         return jsonify({'status':'error','message':'Missing id_token'}), 400
#     try:
#         idinfo = id_token.verify_oauth2_token(token, grequests.Request(), GOOGLE_CLIENT_ID)

#         existing = User.query.filter_by(email=idinfo['email']).first()
#         if existing and not any(o.provider=='google' for o in existing.oauth_accounts):
#             return jsonify({
#                 'status': 'error',
#                 'message': f"Already registered via {existing.oauth_accounts[0].provider}"
#             }), 400
        
#         tokens = login_oauth(
#             provider='google',
#             provider_id=idinfo['sub'],
#             profile_info={
#                 'email':         idinfo['email'],
#                 'name':          idinfo.get('name'),
#             }
#         )
#         return jsonify({'status':'ok', **tokens})

#     except Exception as e:
#         print("Login Error: ", e)
#         return jsonify({'status': 'error', 'message': str(e)}), 400

# @auth_bp.route('/signin',  methods=['GET'])
# def login_page():
#     return render_template(
#         'auth/login.html',
#         google_client_id=GOOGLE_CLIENT_ID,
#         github_login_url=url_for('auth.github_login')
#     )

# @auth_bp.route('/google-login')
# def google_login():
#     state = secrets.token_urlsafe(16)
#     session['oauth_state_google'] = state

#     redirect_uri = url_for('auth.google_callback', _external=True)
#     params = {
#         "client_id":     GOOGLE_CLIENT_ID,
#         "redirect_uri":  redirect_uri,
#         "response_type": "code",
#         "scope":         "openid email profile",
#         "state":         state,
#         "access_type":   "offline",
#         "prompt":        "consent"
#     }

#     return redirect(
#         "https://accounts.google.com/o/oauth2/v2/auth?" + requests.compat.urlencode(params)
#     )

# @auth_bp.route('/google/callback')
# def google_callback():
#     # 1) verify state
#     if request.args.get('state') != session.pop('oauth_state', None):
#         return "Invalid state", 400

#     # 2) grab the code
#     code = request.args.get('code')
#     if not code:
#         return "Missing code", 400

#     # 3) exchange code for tokens
#     token_resp = requests.post(
#         "https://oauth2.googleapis.com/token",
#         data = {
#             "code":          code,
#             "client_id":     GOOGLE_CLIENT_ID,
#             "client_secret": GOOGLE_CLIENT_SECRET,
#             "redirect_uri":  url_for('auth.google_callback', _external=True),
#             "grant_type":    "authorization_code"
#         }
#     ).json()

#     idt = token_resp.get("id_token")
#     if not idt:
#         return "Token exchange failed", 400

#     # 4) verify & pull user info from the ID token
#     idinfo = id_token.verify_oauth2_token(idt, grequests.Request(), GOOGLE_CLIENT_ID)

#     # 5) issue our JWTs
#     tokens = login_oauth(
#         provider='google',
#         provider_id=idinfo['sub'],
#         profile_info={
#             'email':         idinfo['email'],
#             'name':          idinfo.get('name'),
#         }
#     )

#     # 6) return JSON (or set cookies and redirect)
#     return jsonify(tokens), 200

# @auth_bp.route('/logout', methods=['POST'])
# @jwt_required(refresh=True)
# def logout():
#     msg, status = jwt_logout()
#     resp = jsonify({"msg":"Logout successful"})
#     unset_jwt_cookies(resp)

#     return resp, 200

# @auth_bp.route('/github-login')
# def github_login():
#     state = secrets.token_urlsafe(16)
#     session['oauth_state'] = state
#     params = {
#         "client_id":     GITHUB_CLIENT_ID,
#         "redirect_uri":  url_for('auth.github_callback', _external=True),
#         "scope":         "read:user user:email",
#         "state":         state
#     }
#     return redirect(
#         "https://github.com/login/oauth/authorize?"
#         + requests.compat.urlencode(params)
#     )

# @auth_bp.route('/github/callback')
# def github_callback():
    # if request.args.get('state') != session.pop('oauth_state', None):
    #     return "Invalid state", 400

    # code = request.args.get('code')
    # if not code:
    #     return "Missing code", 400

    # token_resp = requests.post(
    #     "https://github.com/login/oauth/access_token",
    #     headers={"Accept": "application/json"},
    #     data={
    #         "client_id":     GITHUB_CLIENT_ID,
    #         "client_secret": GITHUB_CLIENT_SECRET,
    #         "code":          code,
    #         "redirect_uri":  url_for('auth.github_callback', _external=True),
    #     }
    # ).json()

    # access_token = token_resp.get("access_token")
    # if not access_token:
    #     return jsonify(token_resp), 400

    # headers = {
    #   "Authorization": f"token {access_token}",
    #   "Accept": "application/vnd.github.v3+json"
    # }
    # # 1) Get basic profile
    # user_resp = requests.get("https://api.github.com/user", headers=headers).json()
    # email = user_resp.get("email")

    # # 2) If no public email, fetch the list of emails
    # if not email:
    #     emails = requests.get("https://api.github.com/user/emails", headers=headers)
    #     if emails.ok:
    #         for e in emails.json():
    #             # pick the primary & verified one
    #             if e.get("primary") and e.get("verified"):
    #                 email = e["email"]
    #                 break
    # if not email:
    #     flash("Could not retrieve a verified email from GitHub.", "warning")
    #     return redirect(url_for('auth.login_page'))

    # existing = User.query.filter_by(email=email).first()
    # if existing and not any(o.provider=='github' for o in existing.oauth_accounts):
    #     flash(
    #         f"Already registered via {existing.oauth_accounts[0].provider.title()}.",
    #         "warning"
    #     )
    #     return redirect(url_for('auth.login_page'))

    # tokens = login_oauth(
    #     provider='github',
    #     provider_id=user_resp["id"],
    #     profile_info={
    #         'email':         email,
    #         'name':          user_resp.get("name") or user_resp.get("login"),
    #     }
    # )

    # return jsonify(tokens), 200