from __future__ import annotations
import json
from flask import Blueprint, request, jsonify
from extensions import db
from .services.stripe_client import construct_event_from_request
from .services import events as ev
from . import billing_webhooks_bp



@billing_webhooks_bp.post("")
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = construct_event_from_request(payload, sig)
    except Exception as e:
        return ("", 400)


    etype = event.get("type")
    data = event.get("data", {}).get("object", {})
    with db.session.begin():
        if etype == "invoice.paid":
            ev.on_invoice_paid(event.get("id"), data)
        elif etype == "customer.subscription.updated":
            ev.on_subscription_updated(event.get("id"), data)
        elif etype == "customer.subscription.deleted":
            ev.on_subscription_deleted(event.get("id"), data)
        elif etype == "checkout.session.completed":
            ev.on_checkout_completed(event.get("id"), data)
        elif etype == "invoice.payment_failed":
            ev.on_invoice_payment_failed(event.get("id"), data)
        elif etype in ("charge.refunded", "charge.dispute.created", "charge.dispute.funds_withdrawn", "charge.dispute.funds_reinstated"):
            pass
    return jsonify({"received": True})