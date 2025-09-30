from __future__ import annotations
import json
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from .services.stripe_client import construct_event_from_request
from .services import events as ev

billing_webhooks_bp = Blueprint("billing_webhooks_bp", __name__, url_prefix="/billing/webhook")

# Map Stripe event types to our handlers
HANDLERS = {
    "invoice.paid": ev.on_invoice_paid,
    # treat "created" as an update for our purposes
    "customer.subscription.created": ev.on_subscription_updated,
    "customer.subscription.deleted": ev.on_subscription_deleted,
    "checkout.session.completed": ev.on_checkout_completed,
    # extra safety (we’ll add the handler below)
    "invoice.payment_failed": ev.on_invoice_payment_failed,
}

@billing_webhooks_bp.post("")
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")

    try:
        event = construct_event_from_request(payload, sig)
    except Exception as e:
        current_app.logger.exception("stripe_webhook: signature/parse failed")
        return jsonify({"ok": False, "error": "bad_signature", "detail": str(e)}), 400

    etype = event.get("type")
    evid = event.get("id")
    data_obj = (event.get("data") or {}).get("object") or {}

    handler = HANDLERS.get(etype)
    current_app.logger.info("stripe_webhook: %s %s", etype, evid)

    if not handler:
        # Don't 4xx for unknown events; just acknowledge
        return jsonify({"ok": True, "note": f"ignored:{etype}"}), 200

    try:
        # keep each event atomic
        with db.session.begin():
            handler(evid, data_obj)
        return jsonify({"ok": True, "handled": etype}), 200
    except Exception as e:
        current_app.logger.exception("stripe_webhook: handler failed for %s %s", etype, evid)
        # 200 with ok:false to prevent endless Stripe retries while still surfacing the problem
        return jsonify({"ok": False, "handled": etype, "error": str(e)}), 200
