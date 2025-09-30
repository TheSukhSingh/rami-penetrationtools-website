from __future__ import annotations
import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

STRIPE_PRICE_PRO_MONTHLY = os.getenv("STRIPE_PRICE_PRO_MONTHLY")
STRIPE_PRICE_TOPUP_100 = os.getenv("STRIPE_PRICE_TOPUP_100")
STRIPE_PRICE_TOPUP_200 = os.getenv("STRIPE_PRICE_TOPUP_200")
STRIPE_PRICE_TOPUP_500 = os.getenv("STRIPE_PRICE_TOPUP_500")

PACK_CODE_TO_PRICE = {
    "topup_100": STRIPE_PRICE_TOPUP_100,
    "topup_200": STRIPE_PRICE_TOPUP_200,
    "topup_500": STRIPE_PRICE_TOPUP_500,
}

def create_checkout_session_subscription(customer_id: str, success_url: str, cancel_url: str):
    return stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": STRIPE_PRICE_PRO_MONTHLY, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        automatic_tax={"enabled": False},
    )

def create_checkout_session_topup(customer_id: str, pack_code: str, success_url: str, cancel_url: str):
    price_id = PACK_CODE_TO_PRICE.get(pack_code)
    if not price_id:
        raise ValueError(f"Unknown pack_code: {pack_code}")
    return stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        automatic_tax={"enabled": False},
        metadata={"pack_code": pack_code},  # <-- required for webhook
    )

def create_billing_portal_session(customer_id: str, return_url: str):
    return stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)

def construct_event_from_request(payload: bytes, sig_header: str):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def create_customer(user_id: int, email: str | None = None):
    """
    Create a Stripe Customer for this user. Email is optional.
    We always tag user_id in metadata for support/debug.
    """
    return stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user_id)},
    )




