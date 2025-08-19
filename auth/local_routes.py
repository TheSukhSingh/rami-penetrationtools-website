from io import BytesIO
from sqlalchemy.exc import IntegrityError, DataError, OperationalError, ProgrammingError, SQLAlchemyError

from flask import (
    render_template, redirect, send_file, session,
    url_for, request, jsonify, current_app, flash
)
from flask_limiter.util import get_remote_address
import pyotp
import qrcode
from extensions import limiter
from flask_jwt_extended import set_access_cookies, set_refresh_cookies
from . import auth_bp
from .models import (
    MFASetting, RecoveryCode, RefreshToken, User, Role,
    PasswordReset,
)
from extensions import db
from .utils import (
    _remember_device,
    generate_confirmation_token,
    confirm_token,
    generate_recovery_codes,
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

    # db.session.flush()  

    try:
        db.session.flush()  # will assign user.id or throw if constraints fail
    except IntegrityError as e:
        db.session.rollback()
        s = str(getattr(e, "orig", e)).lower()
        if "username_min_len" in s or "username_max_len" in s or "username_no_spaces" in s:
            return jsonify(message="Invalid username (4–15 chars, no spaces)."), 400
        if "users.username" in s and "unique" in s:
            return jsonify(message="Username already taken."), 400
        if "users.email" in s and "unique" in s:
            return jsonify(message="Email already registered."), 400
        
        # fallback
        current_app.logger.exception("Signup failed on flush")
        return jsonify(message="Could not create user."), 400
    except DataError as e:
        print(f"this is dataerror -> {e}")
    except OperationalError as e:
        print(f"this is OperationalError -> {e}")
    except ProgrammingError as e:
        print(f"this is ProgrammingError -> {e}")
    except SQLAlchemyError as e:
        print(f"this is sqlalchemy error -> {e}")

    except Exception as e:
        print(f"error in flush - {e}")
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

def _signin_key():
    data = (request.get_json(silent=True) or {})
    email = (data.get('email') or "").strip().lower()
    ip = get_remote_address()
    return f"{ip}:{email}" if email else ip

@auth_bp.route('/signin',  methods=['POST'])
@limiter.limit("5 per 15 minutes", key_func=_signin_key)
def local_login():
    data = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    tokens, err = util_login_local(email, password)
    
    # ⬇️ If MFA is required, park user id in session and tell FE where to go
    if err == "MFA_REQUIRED":
        user = User.query.filter_by(email=email).first()
        session['mfa_user'] = user.id
        return jsonify({"mfa_required": True, "verify_url": url_for('auth.verify_mfa')}), 202
    
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
@limiter.limit("20 per hour", key_func=get_remote_address)
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
        html = render_template('emails/reset_password_email.html', reset_url=reset_url)
        send_email(user.email, 'Your Password Reset Link', html)

    # Always return generic message to avoid user enumeration
    return jsonify(message="If that email is registered, you’ll receive a reset link."), 200

# @auth_bp.route('/reset-password/<token>', methods=['GET','POST'])
# def reset_password(token):
#     user = PasswordReset.verify_reset_token(token)
#     if not user or not user.local_auth:
#         flash('Invalid or expired reset link.', 'danger')
#         return redirect(url_for('auth.forgot_password'))

#     if request.method == 'POST':
#         pwd     = request.form.get('password', '')
#         confirm = request.form.get('confirm_password', '')

#         # validate & set (but don’t commit yet)
#         if not validate_and_set_password(user, pwd, confirm, commit=False):
#             # flashes are handled in the helper
#             return redirect(url_for('auth.reset_password', token=token))

#         # everything’s valid: persist the new hash
#         db.session.commit()
#         flash('Your password has been updated! Please log in.', 'success')
#         return redirect(url_for('auth.login_page'))

#     return render_template('auth/reset_password.html', token=token, user=user)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    print(1)
    if request.method == 'GET':
        print(2)
        pr = PasswordReset.get_valid_record(token)
        print(3)
        if not pr:
            print(4)
            flash('Invalid or expired reset link.', 'danger')
            return redirect(url_for('index'))
        print(5)
        # pass pr.user to template (or drop hidden fields)
        try:
            return render_template('auth/reset_password.html', token=token, user=pr.user)
        except Exception as e:
            print(f"error for something - {e}")
    
    print(6)

    # POST
    pr = PasswordReset.get_valid_record(token)
    print(7)
    if not pr:
        print(8)
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('index'))
    print(9)

    pwd     = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')

    print(10)
    if not validate_and_set_password(pr.user, pwd, confirm, commit=False):
        return redirect(url_for('auth.reset_password', token=token))
    print(11)

    pr.consume()                # consume the token only on success
    db.session.commit()
    print(12)
    flash('Your password has been updated! Please log in.', 'success')
    return redirect(url_for('auth.login_page'))



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

@auth_bp.route('/mfa/setup', methods=['GET'])
@jwt_required()  # require a logged-in session to set up MFA
def mfa_setup():
    user = get_current_user()
    if not user:
        return jsonify({"msg": "Unauthorized"}), 401

    # Ensure a secret exists (do not enable yet)
    m = user.mfa_setting or MFASetting(user_id=user.id, secret=pyotp.random_base32(), enabled=False)
    if not user.mfa_setting:
        db.session.add(m); db.session.commit()

    # Build otpauth URI and render QR as PNG
    uri = pyotp.TOTP(m.secret).provisioning_uri(name=user.email, issuer_name=current_app.name)
    img = qrcode.make(uri)
    buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return send_file(buf, mimetype="image/png")

@auth_bp.route('/mfa/enable', methods=['POST'])
@jwt_required()
def mfa_enable():
    user = get_current_user()
    if not user:
        return jsonify({"msg": "Unauthorized"}), 401

    code = (request.json or {}).get("code", "").strip()
    m = user.mfa_setting
    if not m or not m.secret:
        return jsonify({"msg": "No MFA secret to verify"}), 400

    ok = pyotp.TOTP(m.secret).verify(code, valid_window=1)
    if not ok:
        return jsonify({"msg": "Invalid code"}), 400

    m.enabled = True
    db.session.commit()

    # Generate recovery codes once and return (plaintext) to the user to store
    codes = generate_recovery_codes(user.id, count=10)
    return jsonify({"msg": "MFA enabled", "recovery_codes": codes}), 200

@auth_bp.route('/verify-mfa', methods=['GET','POST'])
def verify_mfa():
    # UI for entering code is already in templates/auth/verify_mfa.html (has remember checkbox) :contentReference[oaicite:10]{index=10}
    if request.method == 'GET':
        if not session.get('mfa_user'):
            # If someone hits this directly, show the form but it won’t succeed
            return render_template('auth/verify_mfa.html')
        return render_template('auth/verify_mfa.html')

    # POST
    uid = session.get('mfa_user')
    if not uid:
        flash('Session expired. Please sign in again.', 'warning')
        return redirect(url_for('index'))

    user = User.query.get(uid)
    m = user.mfa_setting
    token = (request.form.get('token') or '').strip()
    remember = bool(request.form.get('remember'))

    ok = False
    # 1) Try TOTP (6-digit)
    if m and m.secret and token.isdigit() and len(token) in (6, 8):
        ok = pyotp.TOTP(m.secret).verify(token, valid_window=1)

    # 2) Fallback: recovery code (any length). We store only hashes.
    if not ok and token:
        h = sha256(token.encode()).hexdigest()
        rc = RecoveryCode.query.filter_by(user_id=user.id, code_hash=h, used=False).first()
        if rc:
            rc.used = True
            db.session.commit()
            ok = True

    if not ok:
        flash('Invalid authentication code.', 'danger')
        return render_template('auth/verify_mfa.html')

    # Success → issue JWTs same as a normal login
    from .utils import jwt_login  # local import to avoid cycles
    tokens = jwt_login(user)

    resp = redirect(url_for('index'))
    set_access_cookies(resp, tokens["access_token"])
    set_refresh_cookies(resp, tokens["refresh_token"])

    # Optionally mark this device as trusted for N days
    if remember:
        raw, exp = _remember_device(user.id, request.headers.get('User-Agent', ''))
        resp.set_cookie(
            current_app.config.get("TRUSTED_DEVICE_COOKIE_NAME", "tdid"),
            raw,
            secure=True, httponly=True, samesite="Lax",
            expires=exp  # set server-side expiry to match DB
        )

    # Clean up the staged MFA session
    session.pop('mfa_user', None)
    flash('MFA verified — signed in!', 'success')
    return resp

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