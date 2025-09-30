from __future__ import annotations
import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from extensions import db
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
    portal = create_billing_portal_session(customer_id, return_url)
    return jsonify({"ok": True, "portal_url": portal.get("url")})

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


