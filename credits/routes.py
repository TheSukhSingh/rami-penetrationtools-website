from __future__ import annotations
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from credits.services.entitlements import list_entitlements
from extensions import db
from .services.ledger import ensure_daily_grant, debit, InsufficientCredits
from .models import BalanceSnapshot, CreditUserState, LedgerEntry  
from . import credits_bp

@credits_bp.get("/balance")
@jwt_required()
def get_balance():
    user_id = get_jwt_identity()
    with db.session.begin():
        ensure_daily_grant(user_id)
        snap = db.session.get(BalanceSnapshot, user_id)
        state = db.session.get(CreditUserState, user_id)

        resp = {
            "daily_mic": snap.daily_mic if snap else 0,
            "monthly_mic": snap.monthly_mic if snap else 0,
            "topup_mic": snap.topup_mic if snap else 0,
            "next_daily_reset_utc": "00:00:00",  # client can compute countdown to 00:00 UTC
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
    ref = body.get("ref") # optional idempotency key from caller
    with db.session.begin():
        try:
            breakdown = debit(user_id, cost_mic, ref=ref)
        except InsufficientCredits:
            return jsonify({"ok": False, "error": "INSUFFICIENT_CREDITS"}), 402
    return jsonify({"ok": True, "breakdown": breakdown})


@credits_bp.get("/entitlements")
@jwt_required()
def get_entitlements():
    user_id = get_jwt_identity()
    data = list_entitlements(user_id)
    return jsonify({ "ok": True, "entitlements": data })

@credits_bp.get("/activity")
@jwt_required()
def get_activity():
    user_id = get_jwt_identity()
    limit = int(request.args.get("limit", 50))
    q = (
        db.session.query(LedgerEntry)
        .filter(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(min(limit, 200))
    )
    items = []
    for row in q.all():
        items.append({
            "id": row.id,
            "type": row.type,
            "bucket": row.bucket,
            "amount_mic": row.amount_mic,
            "ref": row.ref,
            "meta": row.meta or {},
            "created_at": row.created_at.isoformat(),
        })
    return jsonify({"ok": True, "items": items})
