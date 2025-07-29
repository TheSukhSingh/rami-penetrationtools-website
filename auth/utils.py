import os
import re
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app, session, flash, redirect, url_for
from functools import wraps
from .models import db, User
from datetime import datetime
from flask_mail import Mail, Message
from .passwords import COMMON_PASSWORDS
from flask_login import login_user as _flask_login_user, current_user

mail = Mail()

def init_mail(app):
    mail.init_app(app)

def generate_confirmation_token(email: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    salt = current_app.config.get('SECURITY_PASSWORD_SALT','email-confirm-salt')
    return serializer.dumps(email, salt=salt)

def confirm_token(token: str, expiration: int = 3600*24) -> str | None:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    salt = current_app.config.get('SECURITY_PASSWORD_SALT','email-confirm-salt')
    try:
        return serializer.loads(token, salt=salt, max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None

def send_email(to: str, subject: str, html_body: str) -> None:
    msg = Message(subject, recipients=[to], html=html_body, sender=current_app.config['MAIL_DEFAULT_SENDER'])
    mail.send(msg)

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login_page'))
        return view_func(*args, **kwargs)
    return wrapped

def login_user(user):
    user.failed_logins = 0
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    _flask_login_user(user)
    session['user'] = {'id': user.id, 'email': user.email, 'name': user.name, 'provider': user.provider}


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
    forbidden_fragments = [user.name.lower(), user.email.lower()]
    for fragment in forbidden_fragments:
        if fragment and fragment in lower_pw:
            flash('Password must not contain your username or email.', 'warning')
            return False

    # 7) Not a common/simple password
    if lower_pw in COMMON_PASSWORDS:
        flash('That password is too common. Please choose a stronger one.', 'warning')
        return False

    # OK: hash & store it
    try:
        user.set_password(password)
    except ValueError as ve:
        flash(str(ve), 'warning')
        return False

    if commit:
        # for new users you probably need db.session.add(user) first
        db.session.add(user)
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