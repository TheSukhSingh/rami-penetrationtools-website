from flask import (
    render_template, redirect,
    url_for, request, jsonify, current_app, flash
)
from flask_limiter.util import get_remote_address
from extensions import limiter
from flask_jwt_extended import set_access_cookies, set_refresh_cookies
from . import auth_bp
from .models import (
    RefreshToken, User, Role,
    PasswordReset,
)
from extensions import db
from .utils import (
    generate_confirmation_token,
    confirm_token,
    send_email,
    
    validate_and_set_password,
    login_local as util_login_local,
    get_current_user,
    verify_turnstile
)
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    create_refresh_token, get_jwt, decode_token
)
from hashlib import sha256
from datetime import datetime, timezone
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():

    data = request.get_json() or {}
    turnstile_token = data.get('turnstile_token')
    ok, err = verify_turnstile(turnstile_token, request.remote_addr)
    if not ok:
        return jsonify(message=f"Captcha failed: {err or 'try again'}"), 400
    username = data.get('username', '').strip()
    name     = data.get('name', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm  = data.get('confirm_password', '')

    # 1) Required fields
    if not all([username, name, email, password, confirm]):
        return jsonify(message="All fields are required."), 400

    # 2) Unique email
    if User.query.filter_by(email=email).first():
        return jsonify(message="Email already registered."), 400

    # 3) Password match
    if password != confirm:
        return jsonify(message="Passwords do not match."), 400
    
    # 4) Username validity & uniqueness
    try:
        User._validate_username(username)
    except ValueError as ve:
        return jsonify(message=str(ve)), 400

    if User.query.filter_by(username=username).first():
        return jsonify(message="Username already taken."), 400

    # Create and persist new user
    user = User(username=username, email=email, name=name)
    db.session.add(user)
    db.session.flush()  

    role = Role.query.filter_by(name='user').first()
    if not role:
        role = Role(name='user', description='Default user role')
        db.session.add(role)
        db.session.flush()
    user.roles.append(role)

    if not validate_and_set_password(user, password, confirm, commit=False):
        db.session.rollback()
        return jsonify(message="Password does not meet requirements."), 400
    
    db.session.add(user.local_auth)
    db.session.commit()

    # Send email confirmation link
    token       = generate_confirmation_token(user.email)
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    html        = render_template('auth/activate.html', confirm_url=confirm_url)
    send_email(user.email, 'Please confirm your email', html)

    return jsonify(message="Signup successful! Check your email to confirm your account."), 201




@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('index'))

    user = User.query.filter_by(email=email).first_or_404()
    if not user.local_auth:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.signup'))
    
    if user.local_auth.email_verified:
        flash('Account already confirmed. Please log in.', 'info')

    else:
        user.local_auth.email_verified = True
        db.session.commit()
        flash('Your account has been confirmed!', 'success')

    return redirect(url_for('index'))


@auth_bp.route('/signin',  methods=['POST'])
# @limiter.limit("5 per 15 minutes", key_func=lambda: (request.json or {}).get('email') or get_remote_address())
def local_login():
    data = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    tokens, err = util_login_local(email, password)
    if err:
        # all errors come back as err string; adjust status if you want 403 for locked/blocked, etc.
        return jsonify({"msg": err}), 401
    
    # issue cookies instead of JSON body
    resp = jsonify({"msg":"Login successful"})
    set_access_cookies(resp, tokens["access_token"])
    set_refresh_cookies(resp, tokens["refresh_token"])

    return resp, 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
# @limiter.limit("20 per hour", key_func=get_remote_address)
def refresh():
    # new_at = create_access_token(identity=get_jwt_identity())
    # resp = jsonify({"msg":"Token refreshed"})
    # set_access_cookies(resp, new_at)
    # return resp, 200
    # 1) Identify current refresh token
    jwt_data = get_jwt()
    jti = jwt_data["jti"]
    sub = jwt_data["sub"]  # the user id as string
    hashed = sha256(jti.encode("utf-8")).hexdigest()

    row = RefreshToken.query.filter_by(token_hash=hashed).first()

    # 2) Reuse detection: if it's missing or already revoked → nuke all sessions
    if not row or row.revoked:
        try:
            uid = int(sub)
            RefreshToken.query.filter_by(user_id=uid, revoked=False).update({"revoked": True})
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"msg": "Token has been revoked"}), 401

    # 3) Rotate: revoke old, mint new refresh + access, persist new refresh JTI
    row.revoked = True

    new_rt = create_refresh_token(identity=sub)
    payload = decode_token(new_rt)  # to pull JTI and exp
    new_hash = sha256(payload["jti"].encode("utf-8")).hexdigest()

    db.session.add(RefreshToken(
        user_id=int(sub),
        token_hash=new_hash,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    ))

    new_at = create_access_token(identity=sub)
    db.session.commit()

    resp = jsonify({"msg": "Token refreshed"})
    set_access_cookies(resp, new_at)
    set_refresh_cookies(resp, new_rt)
    return resp, 200



# @auth_bp.route('/forgot-password', methods=['GET','POST'])
# def forgot_password():
#     if request.method=='POST':
#         email = request.form.get('email','').strip().lower()
#         user  = User.query.filter_by(email=email).first()
#         if user and user.local_auth:
#             pr = PasswordReset(user_id=user.id)
#             token = pr.generate_reset_token()
#             reset_url = url_for('auth.reset_password', token=token, _external=True)
#             html = render_template('auth/reset_password_email.html', reset_url=reset_url)
#             send_email(user.email, 'Your Password Reset Link', html)

#         # always show this to avoid user enumeration
#         flash('If that email is registered, you’ll receive a reset link.', 'info')
#         return redirect(url_for('auth.login_page'))

#     return render_template('auth/forgot.html')

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per hour", key_func=get_remote_address)
def forgot_password():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()

    turnstile_token = data.get('turnstile_token')
    ok, err = verify_turnstile(turnstile_token, request.remote_addr)
    if not ok:
        return jsonify(message=f"Captcha failed: {err or 'try again'}"), 400

    user = User.query.filter_by(email=email).first()
    if user and user.local_auth:
        pr = PasswordReset(user_id=user.id)
        token = pr.generate_reset_token()
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        html = render_template('auth/reset_password_email.html', reset_url=reset_url)
        send_email(user.email, 'Your Password Reset Link', html)

    # Always return generic message to avoid user enumeration
    return jsonify(message="If that email is registered, you’ll receive a reset link."), 200

@auth_bp.route('/reset-password/<token>', methods=['GET','POST'])
def reset_password(token):
    user = PasswordReset.verify_reset_token(token)
    if not user or not user.local_auth:
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        pwd     = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # validate & set (but don’t commit yet)
        if not validate_and_set_password(user, pwd, confirm, commit=False):
            # flashes are handled in the helper
            return redirect(url_for('auth.reset_password', token=token))

        # everything’s valid: persist the new hash
        db.session.commit()
        flash('Your password has been updated! Please log in.', 'success')
        return redirect(url_for('auth.login_page'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    user = get_current_user()
    return jsonify({
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'name': user.name
    }), 200




# @auth_bp.route('/mfa-setup')
# @login_required
# def mfa_setup():
#     uid = get_jwt_identity() if request.headers.get('Authorization') else session.get('user','{}').get('id')
#     user = User.query.get_or_404(uid)

#     # ensure setting exists
#     m = user.mfa_setting or MFASetting(user_id=user.id)
#     if not m.secret:
#         m.secret = pyotp.random_base32()
#     db.session.add(m)
#     db.session.commit()

#     totp = pyotp.TOTP(m.secret)
#     uri  = totp.provisioning_uri(user.email, issuer_name=current_app.name)

#     img = qrcode.make(uri)
#     buf = BytesIO(); img.save(buf); buf.seek(0)
#     return send_file(buf, mimetype='image/png')


# @auth_bp.route('/verify-mfa', methods=['GET','POST'])
# def verify_mfa():
#     if request.method=='POST':
#         token = request.form.get('token','')
#         uid   = session.get('mfa_user')
#         user  = User.query.get(uid)
#         m     = user.mfa_setting

#         if m and pyotp.TOTP(m.secret).verify(token):
#             # on success you’d issue tokens as in login_local
#             session.pop('mfa_user', None)
#             flash('MFA verified, please sign in again.', 'success')
#             return redirect(url_for('auth.login_page'))
#         flash('Invalid authentication code.', 'danger')

#     return render_template('auth/verify_mfa.html')