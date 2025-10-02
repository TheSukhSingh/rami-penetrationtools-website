from __future__ import annotations
from flask import request, jsonify, current_app
from extensions import db
from .services.stripe_client import construct_event_from_request
from .services import events as ev
from . import billing_webhooks_bp

HANDLERS = {
    "invoice.paid": ev.on_invoice_paid,
    "invoice.payment_failed": ev.on_invoice_payment_failed,
    "customer.subscription.created": ev.on_subscription_updated,  # treat as update
    "customer.subscription.deleted": ev.on_subscription_deleted,
    "checkout.session.completed": ev.on_checkout_completed,
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
        return jsonify({"ok": True, "note": f"ignored:{etype}"}), 200

    try:
        with db.session.begin():
            handler(evid, data_obj)
        return jsonify({"ok": True, "handled": etype}), 200
    except Exception as e:
        # Log, but return 200 so Stripe doesn't retry endlessly in dev
        current_app.logger.exception("stripe_webhook: handler failed for %s %s", etype, evid)
        return jsonify({"ok": False, "handled": etype, "error": str(e)}), 200
