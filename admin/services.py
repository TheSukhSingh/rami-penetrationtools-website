from auth.models import User, Role, LoginEvent, RefreshToken
from .models import SiteSetting


# USER MANAGEMENT

def get_all_users():
    return User.query.order_by(User.date_joined.desc()).all()


def get_user(user_id):
    return User.query.get_or_404(user_id)


def update_user(user, email, username, role_ids, is_active):
    user.email = email
    user.username = username
    user.roles = Role.query.filter(Role.id.in_(role_ids)).all()
    user.is_active = is_active
    user.save()


# SETTINGS

def get_setting(key, default=None):
    setting = SiteSetting.query.get(key)
    return setting.value if setting else default


def set_setting(key, value):
    setting = SiteSetting.query.get(key) or SiteSetting(key=key)
    setting.value = value
    setting.save()


# METRICS

def count_active_users():
    return User.query.filter_by(is_active=True).count()


def recent_signups(days=7):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    return User.query.filter(User.date_joined >= cutoff).count()