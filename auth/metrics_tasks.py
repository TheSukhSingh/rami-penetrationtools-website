# auth/metrics_tasks.py
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func, distinct
from extensions import db
from .models import AuthDailyStats, RateLimitEvent, SecurityEvent, User, LoginEvent

def _bounds(d: date):
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end

def compute_auth_rollup_for_day(target: date | None = None):
    if target is None:
        target = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    start, end = _bounds(target)
    start_m30 = start - timedelta(days=29)

    dau = db.session.query(func.count(func.distinct(LoginEvent.user_id))).filter(
        LoginEvent.successful.is_(True), LoginEvent.occurred_at >= start, LoginEvent.occurred_at < end
    ).scalar() or 0

    mau_30 = db.session.query(func.count(func.distinct(LoginEvent.user_id))).filter(
        LoginEvent.successful.is_(True), LoginEvent.occurred_at >= start_m30, LoginEvent.occurred_at < end
    ).scalar() or 0

    signups = db.session.query(func.count(User.id)).filter(User.created_at >= start, User.created_at < end).scalar() or 0
    verifications = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "EMAIL_VERIFIED", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0

    mfa_required = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "MFA_REQUIRED", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0
    mfa_success = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "MFA_SUCCESS", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0
    mfa_fail = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "MFA_FAIL", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0

    pr_req = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "PASSWORD_RESET_REQUESTED", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0
    pr_ok = db.session.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "PASSWORD_RESET_SUCCESS", SecurityEvent.occurred_at >= start, SecurityEvent.occurred_at < end
    ).scalar() or 0

    rlh = db.session.query(func.count(RateLimitEvent.id)).filter(
        RateLimitEvent.occurred_at >= start, RateLimitEvent.occurred_at < end
    ).scalar() or 0

    row = db.session.get(AuthDailyStats, target)
    if not row:
        row = AuthDailyStats(day=target)
        db.session.add(row)

    row.dau = dau
    row.mau_30 = mau_30
    row.signups = signups
    row.verifications = verifications
    row.mfa_required = mfa_required
    row.mfa_success = mfa_success
    row.mfa_fail = mfa_fail
    row.password_resets_requested = pr_req
    row.password_resets_success = pr_ok
    row.rate_limit_hits = rlh

    db.session.commit()
    return {"day": target.isoformat(), "dau": dau, "mau_30": mau_30}
