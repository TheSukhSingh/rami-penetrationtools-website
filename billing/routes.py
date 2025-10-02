from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta
from flask import render_template, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from extensions import db
from .models import BillingCustomer, SubscriptionSnapshot
from .services.stripe_client import (
    create_checkout_session_subscription,
    create_checkout_session_topup,
    create_billing_portal_session,
    create_customer,
    list_invoices,
    latest_paid_invoice,
)
from plans.catalog import TOPUP_PACKS
from credits.models import CreditUserState
from . import billing_bp
from .services import events as ev

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
    if not current_app.config.get("FEATURE_BILLING"):
        return jsonify({"ok": False, "error": "BILLING_DISABLED"}), 400
    if os.getenv("APP_ENV", "development") == "production":
        return jsonify({"ok": False, "error": "DISALLOWED_IN_PROD"}), 400

    user_id = get_jwt_identity()
    if db.session.get(BillingCustomer, user_id):
        return jsonify({"ok": True, "note": "already_exists"})
    customer = create_customer(user_id=user_id)
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
        period_start = state.current_period_start if state and state.current_period_start else None
        period_end   = state.current_period_end   if state and state.current_period_end   else None
        now = datetime.now(timezone.utc)
        seconds_to_renewal = int((period_end - now).total_seconds()) if period_end else None
        days_to_renewal = (seconds_to_renewal // 86400) if seconds_to_renewal and seconds_to_renewal > 0 else None
        resp = {
            "ok": True,
            "customer_id": bc.stripe_customer_id if bc else None,
            "billing_status": state.billing_status if state else "free",
            "pro_active": bool(state and state.pro_active),
            "subscription_id": state.stripe_subscription_id if state else None,
            "period": {
                "start": period_start.isoformat() if period_start else None,
                "end":   period_end.isoformat()   if period_end   else None,
                "seconds_to_renewal": seconds_to_renewal,
                "days_to_renewal": days_to_renewal,
            },
        }
    return jsonify(resp)

@billing_bp.get("/packs")
@jwt_required()
def list_packs():
    items = [{"code": code, "credits_mic": pack.credits_mic} for code, pack in TOPUP_PACKS.items()]
    return jsonify({"ok": True, "packs": items})

@billing_bp.get("/history")
@jwt_required()
def billing_history():
    user_id = get_jwt_identity()
    with db.session.begin():
        snaps = (db.session.query(SubscriptionSnapshot)
                 .filter(SubscriptionSnapshot.user_id == user_id)
                 .order_by(SubscriptionSnapshot.created_at.desc())
                 .limit(20).all())
        items = [{
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "status": s.status,
            "subscription_id": s.stripe_subscription_id,
            "period_start": s.current_period_start.isoformat() if s.current_period_start else None,
            "period_end": s.current_period_end.isoformat() if s.current_period_end else None,
        } for s in snaps]
    return jsonify({"ok": True, "items": items})

@billing_bp.post("/dev/simulate-invoice-paid")
@jwt_required()
def dev_simulate_invoice_paid():
    if not current_app.config.get("FEATURE_BILLING"):
        return jsonify({"ok": False, "error": "BILLING_DISABLED"}), 400
    if os.getenv("APP_ENV", "development") == "production":
        return jsonify({"ok": False, "error": "DISALLOWED_IN_PROD"}), 400

    user_id = get_jwt_identity()
    bc = db.session.get(BillingCustomer, user_id)
    if not bc:
        return jsonify({"ok": False, "error": "NO_STRIPE_CUSTOMER"}), 400

    now = datetime.now(timezone.utc)
    fake_invoice = {
        "id": f"inv_sim_{int(now.timestamp())}",
        "customer": bc.stripe_customer_id,
        "subscription": "sub_simulated",
        "lines": {"data": [{"period": {
            "start": int(now.timestamp()),
            "end": int((now + timedelta(days=30)).timestamp())
        }}]},
    }
    with db.session.begin():
        ev.on_invoice_paid(event_id=f"evt_sim_{int(now.timestamp())}", invoice=fake_invoice)

    return jsonify({"ok": True, "note": "monthly grant simulated", "invoice_id": fake_invoice["id"]})

@billing_bp.post("/dev/simulate-invoice-failed")
@jwt_required()
def dev_simulate_invoice_failed():
    """
    Dev-only: simulate invoice.payment_failed for the current user.
    Effect: set past_due, expire monthly, downgrade entitlements.
    """
    if not current_app.config.get("FEATURE_BILLING"):
        return jsonify({"ok": False, "error": "BILLING_DISABLED"}), 400
    if os.getenv("APP_ENV", "development") == "production":
        return jsonify({"ok": False, "error": "DISALLOWED_IN_PROD"}), 400

    user_id = get_jwt_identity()
    bc = db.session.get(BillingCustomer, user_id)
    if not bc:
        return jsonify({"ok": False, "error": "NO_STRIPE_CUSTOMER"}), 400

    now = datetime.now(timezone.utc)
    fake_invoice = {
        "id": f"inv_fail_{int(now.timestamp())}",
        "customer": bc.stripe_customer_id,
        "subscription": "sub_simulated",
        # period fields aren’t strictly needed for 'failed'
        "lines": {"data": [{"period": {"start": int(now.timestamp()), "end": int(now.timestamp())}}]},
    }
    with db.session.begin():
        ev.on_invoice_payment_failed(event_id=f"evt_fail_{int(now.timestamp())}", invoice=fake_invoice)

    return jsonify({"ok": True, "note": "invoice.payment_failed simulated", "invoice_id": fake_invoice["id"]})


@billing_bp.post("/dev/simulate-topup/<pack_code>")
@jwt_required()
def dev_simulate_topup(pack_code: str):
    """
    Dev-only: simulate checkout.session.completed for a top-up purchase.
    """
    if not current_app.config.get("FEATURE_BILLING"):
        return jsonify({"ok": False, "error": "BILLING_DISABLED"}), 400
    if os.getenv("APP_ENV", "development") == "production":
        return jsonify({"ok": False, "error": "DISALLOWED_IN_PROD"}), 400

    user_id = get_jwt_identity()
    bc = db.session.get(BillingCustomer, user_id)
    if not bc:
        return jsonify({"ok": False, "error": "NO_STRIPE_CUSTOMER"}), 400

    now = datetime.now(timezone.utc)
    fake_session = {
        "id": f"cs_sim_{int(now.timestamp())}",
        "mode": "payment",
        "customer": bc.stripe_customer_id,
        "metadata": {"pack_code": pack_code},
    }
    with db.session.begin():
        ev.on_checkout_completed(event_id=f"evt_csc_{int(now.timestamp())}", session=fake_session)

    return jsonify({"ok": True, "note": "checkout.session.completed simulated", "pack_code": pack_code})


@billing_bp.get("/invoices/latest")
@jwt_required()
def get_latest_invoice():
    user_id = get_jwt_identity()
    bc = db.session.get(BillingCustomer, user_id)
    if not bc:
        return jsonify({"ok": False, "error": "NO_STRIPE_CUSTOMER"}), 400

    try:
        inv = latest_paid_invoice(bc.stripe_customer_id)
        if not inv:
            return jsonify({"ok": True, "invoice": None})
        out = {
            "id": inv.get("id"),
            "status": inv.get("status"),
            "total": inv.get("total"),
            "currency": inv.get("currency"),
            "created": inv.get("created"),
            "hosted_invoice_url": inv.get("hosted_invoice_url"),
            "invoice_pdf": inv.get("invoice_pdf"),
            "number": inv.get("number"),
        }
        return jsonify({"ok": True, "invoice": out})
    except Exception as e:
        return jsonify({"ok": False, "error": "stripe_error", "message": str(e)}), 400


@billing_bp.get("/invoices")
@jwt_required()
def get_invoices():
    """
    List recent invoices (default 10). Optional ?status=paid|open|void|draft|uncollectible
    """
    user_id = get_jwt_identity()
    bc = db.session.get(BillingCustomer, user_id)
    if not bc:
        return jsonify({"ok": False, "error": "NO_STRIPE_CUSTOMER"}), 400

    status = request.args.get("status") or None
    limit = max(1, min(int(request.args.get("limit", 10)), 50))
    try:
        invs = list_invoices(bc.stripe_customer_id, limit=limit, status=status)
        items = []
        for inv in invs.get("data") or []:
            items.append({
                "id": inv.get("id"),
                "status": inv.get("status"),
                "total": inv.get("total"),
                "currency": inv.get("currency"),
                "created": inv.get("created"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
                "invoice_pdf": inv.get("invoice_pdf"),
                "number": inv.get("number"),
                "subscription": inv.get("subscription"),
            })
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": "stripe_error", "message": str(e)}), 400

@billing_bp.get("/config")
@jwt_required()
def billing_config():
    # Only expose safe info; price IDs are fine in client-side apps, but we already use server routes to create sessions.
    from plans.catalog import TOPUP_PACKS
    packs = [{"code": code, "credits_mic": pack.credits_mic} for code, pack in TOPUP_PACKS.items()]
    return jsonify({"ok": True, "packs": packs})


@billing_bp.get("/ui")
@jwt_required()
def billing_ui():
    return render_template("billing_page.html")
