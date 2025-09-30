from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from .services.ledger import ensure_daily_grant, debit, InsufficientCredits, monthly_usage_mic
from .models import BalanceSnapshot, CreditUserState, LedgerEntry
from . import credits_bp
from credits.services.entitlements import list_entitlements
from plans.catalog import DAILY_FREE_CREDITS, PRO_MONTHLY_CREDITS, MILLICREDITS

@credits_bp.get("/balance")
@jwt_required()
def get_balance():
    user_id = get_jwt_identity()
    with db.session.begin():
        ensure_daily_grant(user_id)
        snap = db.session.get(BalanceSnapshot, user_id)
        state = db.session.get(CreditUserState, user_id)

        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_to_reset = int((next_midnight - now).total_seconds())

        resp = {
            "daily_mic": snap.daily_mic if snap else 0,
            "monthly_mic": snap.monthly_mic if snap else 0,
            "topup_mic": snap.topup_mic if snap else 0,
            "next_daily_reset_utc": next_midnight.isoformat(),
            "seconds_to_reset": seconds_to_reset,
            "pro_active": bool(state and state.pro_active),
            "period": {
                "start": state.current_period_start.isoformat() if state and state.current_period_start else None,
                "end": state.current_period_end.isoformat() if state and state.current_period_end else None,
            },
        }
    return jsonify(resp)

@credits_bp.post("/debit")
@jwt_required()
def post_debit():
    user_id = get_jwt_identity()
    body = request.get_json(force=True)
    cost_mic = int(body.get("cost_mic", 0))
    ref = body.get("ref")
    with db.session.begin():
        try:
            breakdown = debit(user_id, cost_mic, ref=ref)
        except InsufficientCredits:
            return jsonify({"ok": False, "error": "INSUFFICIENT_CREDITS"}), 402
    return jsonify({"ok": True, "breakdown": breakdown})

@credits_bp.get("/activity")
@jwt_required()
def get_activity():
    user_id = get_jwt_identity()
    limit = int(request.args.get("limit", 50))
    rows = (db.session.query(LedgerEntry)
            .filter(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit).all())
    items = [{
        "type": le.type.value if hasattr(le.type, "value") else str(le.type),
        "bucket": le.bucket.value if hasattr(le.bucket, "value") else str(le.bucket),
        "amount_mic": le.amount_mic,
        "ref": le.ref,
        "meta": le.meta,
        "created_at": le.created_at.isoformat() if le.created_at else None,
    } for le in rows]
    return jsonify({"ok": True, "items": items})

@credits_bp.get("/entitlements")
@jwt_required()
def get_entitlements():
    user_id = get_jwt_identity()
    data = list_entitlements(user_id)
    return jsonify({"ok": True, "entitlements": data})

@credits_bp.get("/usage")
@jwt_required()
def get_usage():
    user_id = get_jwt_identity()
    with db.session.begin():
        state = db.session.get(CreditUserState, user_id)
        if state and state.current_period_start and state.current_period_end:
            period_start = state.current_period_start
            period_end   = state.current_period_end
        else:
            period_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            period_end   = period_start + timedelta(days=1)
        used_mic = monthly_usage_mic(user_id, period_start, period_end)
    return jsonify({
        "ok": True,
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "monthly_used_mic": int(used_mic),
    })

@credits_bp.get("/config")
@jwt_required()
def credits_config():
    return jsonify({
        "ok": True,
        "millicredits": MILLICREDITS,
        "daily_free_mic": DAILY_FREE_CREDITS,
        "pro_monthly_mic": PRO_MONTHLY_CREDITS,
    })

@credits_bp.post("/admin/grant-topup")
@jwt_required()
def admin_grant_topup():
    """Dev-only helper: requires scope billing.adjust_credits."""
    from auth.models import User  # keep local to avoid circulars on import graph
    actor_id = get_jwt_identity()
    data = request.get_json(force=True)
    target_user_id = int(data.get("target_user_id", 0))
    amount_mic = int(data.get("amount_mic", 0))
    reason = (data.get("reason") or "").strip()[:120]
    if amount_mic <= 0 or target_user_id <= 0:
        return jsonify({"ok": False, "error": "INVALID_INPUT"}), 400
    actor = db.session.get(User, actor_id)
    if not actor or not actor.has_scope("billing.adjust_credits"):
        return jsonify({"ok": False, "error": "FORBIDDEN"}), 403
    ref = f"admin_{uuid.uuid4().hex[:8]}:{reason or 'adjust'}"
    with db.session.begin():
        from .services.ledger import grant_topup
        grant_topup(target_user_id, amount_mic, ref=ref)
    return jsonify({"ok": True, "granted_to": target_user_id, "amount_mic": amount_mic, "ref": ref})

@credits_bp.post("/can-afford")
@jwt_required()
def can_afford():
    """
    Pure check (no debit): tell FE if user can afford a cost_mic right now,
    and how the debit would split across buckets. Returns deficit if not.
    """
    user_id = get_jwt_identity()
    body = request.get_json(force=True)
    cost_mic = int(body.get("cost_mic", 0))

    with db.session.begin():
        # ensure daily grant is applied before reading balances
        ensure_daily_grant(user_id)
        snap = db.session.get(BalanceSnapshot, user_id)

    daily = snap.daily_mic if snap else 0
    monthly = snap.monthly_mic if snap else 0
    topup = snap.topup_mic if snap else 0

    remaining = cost_mic
    from_daily = min(daily, remaining); remaining -= from_daily
    from_monthly = min(monthly, remaining); remaining -= from_monthly
    from_topup = min(topup, remaining); remaining -= from_topup

    can = remaining <= 0
    resp = {
        "ok": True,
        "cost_mic": cost_mic,
        "can_afford": can,
        "breakdown": {
            "from_daily": int(from_daily),
            "from_monthly": int(from_monthly),
            "from_topup": int(from_topup),
        },
        "deficit_mic": int(remaining) if remaining > 0 else 0,
    }
    return jsonify(resp)

@credits_bp.get("/activity.csv")
@jwt_required()
def activity_csv():
    """
    Download recent ledger as CSV for quick audits/support.
    Query param: ?limit=1000 (default 200)
    """
    user_id = get_jwt_identity()
    limit = int(request.args.get("limit", 200))

    rows = (db.session.query(LedgerEntry)
            .filter(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit).all())

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at", "type", "bucket", "amount_mic", "ref", "meta"])
    for le in rows:
        w.writerow([
            le.created_at.isoformat() if le.created_at else "",
            le.type.value if hasattr(le.type, "value") else str(le.type),
            le.bucket.value if hasattr(le.bucket, "value") else str(le.bucket),
            le.amount_mic,
            le.ref or "",
            (le.meta or {}),
        ])

    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=credits_activity.csv"
        },
    )
