from flask import flash, request, session, render_template, redirect, jsonify, url_for
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import os, secrets, requests
from . import auth_bp
from .models import db, User
from .utils import login_required, login_user, generate_username_from_email

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GITHUB_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

def login_or_create_user(email, name, provider, provider_id, email_verified=False):
    """
    Find a User by (provider, provider_id). If none exists, create one.
    """
    user = User.query.filter_by(
        provider=provider,
        provider_id=str(provider_id)
    ).first()

    if not user:
        username = generate_username_from_email(email)
        user = User(
            username=username,
            email=email,
            name=name,
            provider=provider,
            provider_id=str(provider_id),
            email_verified=email_verified
        )
        db.session.add(user)
        db.session.commit()

    return user

@auth_bp.route('/token-signin', methods=['POST'])
def token_signin():
    token = request.json.get('id_token')
    if not token:
        return jsonify({'status':'error','message':'Missing id_token'}), 400
    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), GOOGLE_CLIENT_ID)

        existing = User.query.filter_by(email=idinfo['email']).first()
        if existing and existing.provider != 'google':
            return jsonify({
                'status': 'error',
                'message': f"This email is already registered via {existing.provider}. Please sign in with that."
            }), 400
        
        user = login_or_create_user(
            email=idinfo['email'],
            name=idinfo.get('name') or idinfo['email'],
            provider='google',
            provider_id=idinfo['sub'],
            email_verified=True
        )

        login_user(user)

        return jsonify({'status': 'ok', 'name': user.name})
    except Exception as e:
        print("Login Error: ", e)
        return jsonify({'status': 'error', 'message': str(e)}), 400

@auth_bp.route('/signin',  methods=['GET'])
@auth_bp.route('/signin/', methods=['GET'], strict_slashes=False)
def login_page():
    return render_template(
        'auth/login.html',
        google_client_id=GOOGLE_CLIENT_ID,
        github_login_url=url_for('auth.github_login')
    )

@auth_bp.route('/google-login')
def google_login():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    redirect_uri = url_for('auth.google_callback', _external=True)
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + requests.compat.urlencode(params)

    # 🔥 DEBUG LOGGING — copy these values exactly into your Cloud Console
    print("👉 Using GOOGLE_CLIENT_ID:", GOOGLE_CLIENT_ID)
    print("👉 Full Google OAuth URL:", auth_url)
    # 👆 You should see in your terminal the exact client_id and redirect_uri being sent.

    return redirect(auth_url)



@auth_bp.route('/google/callback')
def google_callback():
    # 1) verify state
    if request.args.get('state') != session.pop('oauth_state', None):
        return "Invalid state", 400

    # 2) grab the code
    code = request.args.get('code')
    if not code:
        return "Missing code", 400

    # 3) exchange code for tokens
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data = {
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  url_for('auth.google_callback', _external=True),
            "grant_type":    "authorization_code"
        }
    ).json()

    idt = token_resp.get("id_token")
    if not idt:
        return "Token exchange failed", 400

    # 4) verify & pull user info from the ID token
    idinfo = id_token.verify_oauth2_token(idt, grequests.Request(), GOOGLE_CLIENT_ID)

    # 5) find or create your user
    user = login_or_create_user(
        email           = idinfo["email"],
        name            = idinfo.get("name") or idinfo["email"],
        provider        = "google",
        provider_id     = idinfo["sub"],
        email_verified  = idinfo.get("email_verified", False)
    )

    # 6) log them in & go home
    login_user(user)
    return redirect(url_for('index'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))

@auth_bp.route('/github-login')
def github_login():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    params = {
        "client_id":     GITHUB_CLIENT_ID,
        "redirect_uri":  url_for('auth.github_callback', _external=True),
        "scope":         "read:user user:email",
        "state":         state
    }
    github_auth_url = "https://github.com/login/oauth/authorize"
    return redirect(f"{github_auth_url}?{requests.compat.urlencode(params)}")

@auth_bp.route('/github/callback')
def github_callback():
    if request.args.get('state') != session.pop('oauth_state', None):
        return "Invalid state", 400

    code = request.args.get('code')
    if not code:
        return "Missing code", 400

    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id":     GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code":          code,
            "redirect_uri":  url_for('auth.github_callback', _external=True),
        }
    ).json()

    access_token = token_resp.get("access_token")
    if not access_token:
        return jsonify(token_resp), 400

    headers = {
      "Authorization": f"token {access_token}",
      "Accept": "application/vnd.github.v3+json"
    }
    # 1) Get basic profile
    user_resp = requests.get("https://api.github.com/user", headers=headers).json()
    email = user_resp.get("email")

    # 2) If no public email, fetch the list of emails
    if not email:
        emails = requests.get("https://api.github.com/user/emails", headers=headers)
        if emails.ok:
            for e in emails.json():
                # pick the primary & verified one
                if e.get("primary") and e.get("verified"):
                    email = e.get("email")
                    break
    if not email:
        flash(
            "Could not retrieve a verified email from GitHub. Make sure it’s public or primary.",
            "warning"
        )
        return redirect(url_for('auth.login_page'))

    existing = User.query.filter_by(email=email).first()
    if existing and existing.provider != 'github':
        flash(
            f"This email is already registered via {existing.provider.title()}. Please sign in with that.",
            "warning"
        )
        return redirect(url_for('auth.login_page'))



    user = login_or_create_user(
        email=email,
        name=user_resp.get("name") or user_resp.get("login"),
        provider='github',
        provider_id=user_resp["id"],
        email_verified=True
    )

    login_user(user)
    return redirect(url_for('index'))