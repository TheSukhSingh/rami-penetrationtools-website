from __future__ import annotations
import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from credits.models import CreditUserState
from extensions import db
from plans.catalog import TOPUP_PACKS
from .models import BillingCustomer
from .services.stripe_client import (
create_checkout_session_subscription,
create_checkout_session_topup,
create_billing_portal_session, create_customer,
)
from . import billing_bp

# NEW: helper to guarantee a mapping exists
def _ensure_customer_for_user(user_id: int) -> str:
    bc = db.session.get(BillingCustomer, user_id)
    if bc:
        return bc.stripe_customer_id
    cust = create_customer(user_id=user_id)
    bc = BillingCustomer(user_id=user_id, stripe_customer_id=cust["id"])
    db.session.add(bc)
    db.session.flush()
    return bc.stripe_customer_id

@billing_bp.post("/checkout/pro")
@jwt_required()
def start_pro_checkout():
    user_id = get_jwt_identity()
    data = request.get_json(force=True) if request.data else {}
    success_url = data.get("success_url", "https://hackr.gg/billing/return")
    cancel_url = data.get("cancel_url", "https://hackr.gg/pricing")
    customer_id = _ensure_customer_for_user(user_id)
    session = create_checkout_session_subscription(customer_id, success_url, cancel_url)
    return jsonify({"ok": True, "checkout_url": session.get("url")})

@billing_bp.post("/checkout/topup/<pack_code>")
@jwt_required()
def start_topup_checkout(pack_code: str):
    user_id = get_jwt_identity()
    data = request.get_json(force=True) if request.data else {}
    success_url = data.get("success_url", "https://hackr.gg/billing/return")
    cancel_url = data.get("cancel_url", "https://hackr.gg/pricing")
    customer_id = _ensure_customer_for_user(user_id)
    session = create_checkout_session_topup(customer_id, pack_code, success_url, cancel_url)
    return jsonify({"ok": True, "checkout_url": session.get("url")})

@billing_bp.post("/portal")
@jwt_required()
def open_portal():
    user_id = get_jwt_identity()
    data = request.get_json(force=True) if request.data else {}
    return_url = data.get("return_url", "https://hackr.gg/account/billing")
    customer_id = _ensure_customer_for_user(user_id)
    try:
        portal = create_billing_portal_session(customer_id, return_url)
        return jsonify({"ok": True, "portal_url": portal.get("url")})
    except stripe.error.StripeError as e:
        # surface real Stripe error instead of an HTML 500
        return jsonify({
            "ok": False,
            "error": "stripe_error",
            "type": getattr(e, "user_message", None) or e.__class__.__name__,
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500


@billing_bp.post("/dev/create-customer")
@jwt_required()
def dev_create_customer():
    # guard: only allow when FEATURE_BILLING and not production
    if not current_app.config.get("FEATURE_BILLING"):
        return jsonify({"ok": False, "error": "BILLING_DISABLED"}), 400
    if os.getenv("APP_ENV", "development") == "production":
        return jsonify({"ok": False, "error": "DISALLOWED_IN_PROD"}), 400

    user_id = get_jwt_identity()
    if db.session.get(BillingCustomer, user_id):
        return jsonify({"ok": True, "note": "already_exists"})

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    customer = stripe.Customer.create(
        metadata={"user_id": str(user_id)},
    )
    db.session.add(BillingCustomer(user_id=user_id, stripe_customer_id=customer["id"]))
    db.session.commit()
    return jsonify({"ok": True, "customer_id": customer["id"]})

@billing_bp.get("/status")
@jwt_required()
def billing_status():
    user_id = get_jwt_identity()
    with db.session.begin():
        state = db.session.get(CreditUserState, user_id)
        bc = db.session.get(BillingCustomer, user_id)
        resp = {
            "ok": True,
            "customer_id": bc.stripe_customer_id if bc else None,
            "billing_status": state.billing_status if state else "free",
            "pro_active": bool(state and state.pro_active),
            "subscription_id": state.stripe_subscription_id if state else None,
            "period": {
                "start": state.current_period_start.isoformat() if state and state.current_period_start else None,
                "end":   state.current_period_end.isoformat()   if state and state.current_period_end   else None,
            },
        }
    return jsonify(resp)

@billing_bp.get("/packs")
@jwt_required()
def list_packs():
    items = [{"code": code, "credits_mic": pack.credits_mic} for code, pack in TOPUP_PACKS.items()]
    return jsonify({"ok": True, "packs": items})

