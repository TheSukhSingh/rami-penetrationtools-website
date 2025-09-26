from flask import Blueprint

auth_bp = Blueprint(
    'auth',
    __name__,
    url_prefix="/auth",
    template_folder='templates',
    static_folder='static',
    static_url_path='/auth/static'
)
 
import click

@auth_bp.after_request
def _auth_security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')  # relax only where needed
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    # If you use a nonce-based global CSP, prefer that instead of this baseline.
    resp.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "script-src 'self' https://accounts.google.com https://www.gstatic.com; "
        "frame-src https://accounts.google.com; "
        "connect-src 'self'; "
        "img-src 'self' data: https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline'"
    )
    return resp

@auth_bp.cli.command("purge-expired")
@click.option("--dry", is_flag=True, help="Show counts only; do not delete")
def purge_expired(dry: bool):
    """
    Delete expired refresh tokens, expired trusted devices,
    and stale/used password reset + used recovery codes.
    Usage:
        flask auth purge-expired            # delete
        flask auth purge-expired --dry      # counts only
    """
    from datetime import datetime, timezone, timedelta
    from extensions import db
    from .models import RefreshToken, TrustedDevice, PasswordReset, RecoveryCode

    now = datetime.now(timezone.utc)
    ninety_days = now - timedelta(days=90)
    thirty_days = now - timedelta(days=30)

    rt_q = RefreshToken.query.filter(
        (RefreshToken.expires_at <= now) |
        ((RefreshToken.revoked == True) & (RefreshToken.created_at <= ninety_days))
    )
    td_q = TrustedDevice.query.filter(TrustedDevice.expires_at <= now)
    pr_q = PasswordReset.query.filter(
        (PasswordReset.used == True) | (PasswordReset.expires_at <= now)
    )
    rc_q = RecoveryCode.query.filter(RecoveryCode.used == True, RecoveryCode.created_at <= ninety_days)

    counts = {
        "refresh_tokens": rt_q.count(),
        "trusted_devices": td_q.count(),
        "password_resets": pr_q.count(),
        "used_recovery_codes": rc_q.count(),
    }
    click.echo(f"{'Would delete' if dry else 'Deleting'}: {counts}")

    if not dry:
        rt_q.delete(synchronize_session=False)
        td_q.delete(synchronize_session=False)
        pr_q.delete(synchronize_session=False)
        rc_q.delete(synchronize_session=False)
        db.session.commit()
        click.echo("Done.")


from . import oauth_routes, local_routes
