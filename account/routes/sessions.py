from __future__ import annotations
from flask import render_template, redirect, url_for, flash, request
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from datetime import datetime
from extensions import db
from auth.models import RefreshToken
from .. import account_bp

def wants_fragment() -> bool:
    return request.args.get("fragment") == "1" or request.headers.get("X-Fragment") == "1"

def _current_refresh_token_id() -> int | None:
    """
    Resolve the current browser's refresh token -> RefreshToken.id
    by decoding the 'refresh_token_cookie' to get its JTI, then
    looking up the DB row.
    """
    try:
        raw = request.cookies.get("refresh_token_cookie")
        if not raw:
            return None
        decoded = decode_token(raw)
        jti = decoded.get("jti")
        if not jti:
            return None
        rt = RefreshToken.query.filter_by(jti=jti).first()
        return rt.id if rt else None
    except Exception:
        return None

def _fmt(dt) -> str:
    if not dt:
        return ""
    # Render ISO or friendly as you prefer; keep simple:
    if isinstance(dt, datetime):
        return dt.isoformat(sep=" ", timespec="seconds")
    return str(dt)

def _device_label(user_agent: str | None) -> str:
    ua = (user_agent or "").strip()
    if not ua:
        return "Unknown device"
    # Keep simple. If you have UA parsing in your project, swap it in.
    # A few hints:
    if "Windows" in ua:
        base = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        base = "macOS"
    elif "iPhone" in ua or "iOS" in ua:
        base = "iPhone"
    elif "Android" in ua:
        base = "Android"
    else:
        base = "Device"
    if "Chrome" in ua:
        br = "Chrome"
    elif "Firefox" in ua:
        br = "Firefox"
    elif "Safari" in ua and "Chrome" not in ua:
        br = "Safari"
    else:
        br = "Browser"
    return f"{br} on {base}"

@account_bp.route("/sessions", methods=["GET"])
@jwt_required()
def sessions():
    user_id = get_jwt_identity()
    current_id = _current_refresh_token_id()

    tokens = (RefreshToken.query
              .filter_by(user_id=user_id)
              .order_by(RefreshToken.revoked.asc(),
                        RefreshToken.expires_at.desc())
              .all())

    rows = []
    for t in tokens:
        # Safe attribute access with defaults
        ua = getattr(t, "user_agent", "") or ""
        ip = getattr(t, "created_ip", None) or getattr(t, "ip", None) or ""
        loc = getattr(t, "approx_location", None) or ""  # if you store city/region
        created = getattr(t, "created_at", None)
        last_seen = getattr(t, "last_seen_at", None) or getattr(t, "updated_at", None)
        rows.append({
            "id": t.id,
            "revoked": bool(getattr(t, "revoked", False)),
            "expires_at": _fmt(getattr(t, "expires_at", None)),
            "created": _fmt(created),
            "last_seen": _fmt(last_seen),
            "ip": ip,
            "location": loc,
            "user_agent": ua,
            "device_label": _device_label(ua),
            "is_current": (t.id == current_id),
        })

    if wants_fragment():
        return render_template("account/partials/sessions.html", rows=rows)
    return render_template("account/shell.html", rows=rows,
                           partial="account/partials/sessions.html")

@account_bp.route("/sessions/revoke/<int:token_id>", methods=["POST"])
@jwt_required()
def revoke_session(token_id: int):
    user_id = get_jwt_identity()
    current_id = _current_refresh_token_id()

    if current_id and token_id == current_id:
        flash("You can’t revoke the current session from here.", "error")
        return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

    rt = RefreshToken.query.filter_by(id=token_id, user_id=user_id).first()
    if rt and not getattr(rt, "revoked", False):
        rt.revoked = True
        db.session.add(rt); db.session.commit()
        flash("Session revoked.", "success")
    else:
        flash("Not found or already revoked.", "error")

    return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

@account_bp.route("/sessions/revoke-all", methods=["POST"])
@jwt_required()
def revoke_all_sessions():
    user_id = get_jwt_identity()
    updated = (RefreshToken.query
               .filter_by(user_id=user_id, revoked=False)
               .update({"revoked": True}, synchronize_session=False))
    db.session.commit()
    flash(f"Revoked {updated} session(s).", "success")
    return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

@account_bp.route("/sessions/revoke-selected", methods=["POST"])
@jwt_required()
def revoke_selected_sessions():
    user_id = get_jwt_identity()
    current_id = _current_refresh_token_id()
    ids = request.form.getlist("token_id")
    if not ids:
        flash("No sessions selected.", "error")
        return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

    # Coerce to ints and filter out current id
    try:
        ids_int = {int(x) for x in ids}
    except ValueError:
        ids_int = set()

    if current_id:
        ids_int.discard(current_id)

    if not ids_int:
        flash("Nothing to revoke.", "info")
        return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

    q = (RefreshToken.query
         .filter(RefreshToken.user_id == user_id,
                 RefreshToken.revoked == False,
                 RefreshToken.id.in_(ids_int)))
    updated = 0
    for rt in q.all():
        rt.revoked = True
        db.session.add(rt)
        updated += 1
    db.session.commit()

    flash(f"Revoked {updated} selected session(s).", "success")
    return sessions() if wants_fragment() else redirect(url_for("account.sessions"))

@account_bp.route("/sessions/revoke-others", methods=["POST"])
@jwt_required()
def revoke_all_other_sessions():
    user_id = get_jwt_identity()
    current_id = _current_refresh_token_id()

    q = RefreshToken.query.filter_by(user_id=user_id, revoked=False)
    if current_id:
        q = q.filter(RefreshToken.id != current_id)
    updated = q.update({"revoked": True}, synchronize_session=False)
    db.session.commit()

    flash(f"Revoked {updated} other session(s).", "success")
    return sessions() if wants_fragment() else redirect(url_for("account.sessions"))
