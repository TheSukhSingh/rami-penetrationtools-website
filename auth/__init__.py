from flask import Blueprint
from flask import Blueprint, g, request, current_app
import secrets

auth_bp = Blueprint(
    'auth',
    __name__,
    url_prefix="/auth",
    template_folder='templates',
    static_folder='static',
    static_url_path='/auth/static'
)
 
import click

# --- CSP NONCE (per-request) ---
@auth_bp.before_app_request
def _inject_csp_nonce():
    # one random nonce per request; accessible in templates as {{ csp_nonce }}
    g.csp_nonce = secrets.token_urlsafe(16)

@auth_bp.app_context_processor
def _expose_csp_nonce():
    return {"csp_nonce": getattr(g, "csp_nonce", "")}

# --- Security headers (auth pages only) ---
@auth_bp.after_app_request
def _auth_security_headers(response):
    # only protect auth endpoints/pages (don’t disturb other blueprints)
    if not (request.blueprint == "auth" or request.path.startswith("/auth")):
        return response

    # HSTS (enable under HTTPS)
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")

    # Classic hardening
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), gyroscope=(), magnetometer=(),"
        "fullscreen=(self), clipboard-read=(self), clipboard-write=(self)"
    )
    # We also set frame-ancestors via CSP (more modern), but keep XFO for legacy
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")

    # --- Content Security Policy with nonce ---
    # Allow inline scripts ONLY with the per-request nonce.
    # Allow external scripts/frames for Google One Tap + Cloudflare Turnstile.
    nonce = getattr(g, "csp_nonce", "")
    csp = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://accounts.google.com https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline'; "  # keep inline styles for now to avoid breaking forms; can tighten later
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://accounts.google.com https://challenges.cloudflare.com; "
        "frame-src https://accounts.google.com https://challenges.cloudflare.com; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests"
    )
    response.headers["Content-Security-Policy"] = csp

    return response

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
