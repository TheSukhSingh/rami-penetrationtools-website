from io import BytesIO
from flask import (
    render_template, redirect, send_file,
    url_for, request, jsonify, current_app, flash, session
)

from flask_jwt_extended import set_access_cookies, set_refresh_cookies
from . import auth_bp
from .models import (
    db, User, Role,
    PasswordReset,
)

from .utils import (
    generate_confirmation_token,
    confirm_token,
    send_email,
    
    validate_and_set_password,
    login_local as util_login_local,
    get_current_user
)
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():

    data = request.get_json() or {}
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
# @limiter.limit(
#     "3 per 15 minutes",
#     key_func=lambda: request.form.get('email', get_remote_address()),
#     error_message="Too many login attempts; try again later."
# )
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


# @auth_bp.route('/refresh', methods=['POST'])
# @jwt_required(refresh=True)
# def refresh():
#     identity     = get_jwt_identity()
#     access_token = create_access_token(identity=identity)
#     return jsonify(access_token=access_token), 200


@jwt_required(refresh=True)
def refresh():
    new_at = create_access_token(identity=get_jwt_identity())
    resp = jsonify({"msg":"Token refreshed"})
    set_access_cookies(resp, new_at)
    return resp, 200




@auth_bp.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method=='POST':
        email = request.form.get('email','').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user and user.local_auth:
            pr = PasswordReset(user_id=user.id)
            token = pr.generate_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            html = render_template('auth/reset_password_email.html', reset_url=reset_url)
            send_email(user.email, 'Your Password Reset Link', html)

        # always show this to avoid user enumeration
        flash('If that email is registered, you’ll receive a reset link.', 'info')
        return redirect(url_for('auth.login_page'))

    return render_template('auth/forgot.html')


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