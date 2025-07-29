import datetime
from io import BytesIO
from flask import (
    render_template, redirect, send_file, session, url_for,
    request, flash
)
import pyotp
import qrcode
from .utils import (
    generate_confirmation_token,
    confirm_token,
    login_required,
    send_email,
    login_user,
    validate_and_set_password
)
from . import auth_bp
from extensions import limiter
from .models import db, User
from flask_limiter.util import get_remote_address


@auth_bp.route('/signup', methods=['GET', 'POST'])
@auth_bp.route('/signup/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # Basic validation
        if not all([username, name, email, password, confirm]):
            flash('All fields are required.', 'warning')
            return redirect(url_for('auth.signup'))
        
        if password != confirm:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('auth.signup'))
        
        existing = User.query.filter_by(email=email).first()
        if existing:
            if existing.provider != 'local':
                flash(
                    f"This email is already registered via {existing.provider}. Please sign in with that.",
                    'warning'
                )
            else:
                flash('Email is already registered.', 'warning')
            return redirect(url_for('auth.signup'))
        
        try:
            User._validate_username(username)
        except ValueError as ve:
            flash(str(ve), 'warning')
            return redirect(url_for('auth.signup'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'warning')
            return redirect(url_for('auth.signup'))

        # Create and persist new user
        user = User(username=username, email=email, name=name, provider='local')
 
        if not validate_and_set_password(user, password, confirm):
            return redirect(url_for('auth.signup'))

        # Send email confirmation link
        token       = generate_confirmation_token(user.email)
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        html        = render_template('auth/activate.html', confirm_url=confirm_url)
        send_email(user.email, 'Please confirm your email', html)

        flash('Signup successful! Check your email to confirm your account.', 'success')
        return redirect(url_for('auth.login_page'))

    return render_template(
        'auth/signup.html'
    )


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('index'))

    user = User.query.filter_by(email=email).first_or_404()
    if not user:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.signup'))
    if user.email_verified:
        flash('Account already confirmed. Please log in.', 'info')
    else:
        user.email_verified = True
        db.session.commit()
        flash('Your account has been confirmed!', 'success')
    return redirect(url_for('index'))

@auth_bp.route('/signin',  methods=['POST'])
@auth_bp.route('/signin/', methods=['POST'], strict_slashes=False)
@limiter.limit(
    "3 per 15 minutes",
    key_func=lambda: request.form.get('email', get_remote_address()),
    error_message="Too many attempts for that account; try again in 15 minutes."
)
def login_local():
    email    = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    user = User.query.filter_by(email=email, provider='local').first()


    if not user:
        flash('Email not found.', 'danger')
        return redirect(url_for('auth.login_page'))
    if user.is_blocked:
        flash('Your account is blocked. Contact admin.', 'danger')
        return redirect(url_for('auth.login_page'))
    if user.failed_logins >= 3:
        lock_expires = user.last_failed_login_at + datetime.timedelta(minutes=15)
        if datetime.datetime.utcnow() < lock_expires:
            flash("Account locked due to too many attempts. Try again later.", "danger")
            return redirect(url_for('auth.login_page'))
        else:
            # lock expired → reset counter
            user.failed_logins = 0
            db.session.commit()
    if not user.email_verified:
        flash('Please verify your email before logging in.', 'warning')
        return redirect(url_for('auth.login_page'))

    if user.check_password(password):
        if user.mfa_enabled:
            session['mfa_user'] = user.id
            return redirect(url_for('auth.verify_mfa'))
        login_user(user)
        flash('Logged in successfully.', 'success')
        return redirect(url_for('index'))

    else:
        user.failed_logins += 1
        user.last_failed_login_at = datetime.datetime.utcnow()
        db.session.commit()
        flash('Incorrect password.', 'danger')
        return redirect(url_for('auth.login_page'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email, provider='local').first()
        if user:
            # Generate and email reset token
            token     = user.generate_reset_token(expires_in=600)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            html      = render_template('auth/reset_password_email.html', reset_url=reset_url)
            flash('Password reset link sent. Check your mail.', 'info')
            send_email(user.email, 'Your Password Reset Link', html)
        # Always show this message to avoid enumeration

        if not user:
            flash('This email is not registered.', 'info')
        return redirect(url_for('auth.login_page'))
    return render_template('auth/forgot.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash('The reset password link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if not validate_and_set_password(user, password, confirm, commit=False):
            return redirect(url_for('auth.reset_password', token=token))
        
        user.reset_token        = None
        user.reset_token_expiry = None
        db.session.commit()

        flash('Your password has been updated! Please log in.', 'success')
        return redirect(url_for('auth.login_page'))

    return render_template('auth/reset_password.html', token=token, user=user)


@auth_bp.route('/mfa-setup')
@login_required
def mfa_setup():
    # 1) ensure secret exists
    user = User.query.get(session['user']['id'])
    if not user.mfa_secret:
        user.mfa_secret = pyotp.random_base32()
        db.session.commit()

    # 2) build provisioning URI
    totp = pyotp.TOTP(user.mfa_secret)
    uri  = totp.provisioning_uri(user.email, issuer_name="YourAppName")

    # 3) render QR code
    img = qrcode.make(uri)
    buf = BytesIO(); img.save(buf); buf.seek(0)
    return send_file(buf, mimetype='image/png')


@auth_bp.route('/verify-mfa', methods=['GET','POST'])
def verify_mfa():
    user_id = session.get('mfa_user')
    if not user_id:
        return redirect(url_for('auth.login_page'))
    user = User.query.get(user_id)

    if request.method=='POST':
        token = request.form['token']
        if pyotp.TOTP(user.mfa_secret).verify(token):
            # success → finalize login
            login_user(user)
            session.pop('mfa_user', None)
            flash("Logged in with MFA.", "success")
            return redirect(url_for('index'))
        flash("Invalid authentication code.", "danger")

    return render_template('auth/verify_mfa.html')
