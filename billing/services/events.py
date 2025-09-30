from datetime import datetime, timezone
from credits.services.entitlements import apply_entitlements
from extensions import db
from ..models import BillingCustomer, SubscriptionSnapshot, ProcessedStripeEvent
from credits.models import CreditUserState
from credits.services.ledger import grant_monthly, grant_topup, expire_all_monthly
from plans.catalog import PRO_MONTHLY_CREDITS, TOPUP_PACKS

def _mark_event(event_id: str) -> bool:
    if db.session.query(ProcessedStripeEvent).filter_by(event_id=event_id).first():
        return False
    db.session.add(ProcessedStripeEvent(event_id=event_id))
    return True

def _user_id_by_customer(customer_id: str) -> int | None:
    row = db.session.query(BillingCustomer).filter_by(stripe_customer_id=customer_id).first()
    return row.user_id if row else None

def on_invoice_paid(event_id: str, invoice: dict):
    if not _mark_event(event_id): return
    user_id = _user_id_by_customer(invoice.get("customer"))
    if not user_id: return
    lines = (invoice.get("lines") or {}).get("data") or []
    period = (lines[0].get("period") if lines else {}) or {}
    start = datetime.fromtimestamp(period.get("start", 0), tz=timezone.utc)
    end   = datetime.fromtimestamp(period.get("end", 0), tz=timezone.utc)

    state = db.session.get(CreditUserState, user_id) or CreditUserState(user_id=user_id)
    state.pro_active = 1
    state.past_due_since = None
    state.current_period_start = start
    state.current_period_end = end
    state.stripe_subscription_id = invoice.get("subscription")
    state.billing_status = "active"
    db.session.add(state)

    grant_monthly(user_id, PRO_MONTHLY_CREDITS, ref=f"inv_{invoice.get('id')}")
    apply_entitlements(user_id, "pro")
    db.session.add(SubscriptionSnapshot(
        user_id=user_id,
        stripe_subscription_id=invoice.get("subscription"),
        status="active",
        current_period_start=start,
        current_period_end=end,
    ))

def on_subscription_updated(event_id: str, subscription: dict):
    if not _mark_event(event_id): return
    user_id = _user_id_by_customer(subscription.get("customer"))
    if not user_id: return
    state = db.session.get(CreditUserState, user_id) or CreditUserState(user_id=user_id)
    state.billing_status = subscription.get("status")
    state.pro_active = 1 if subscription.get("status") == "active" else 0
    cps = subscription.get("current_period_start")
    cpe = subscription.get("current_period_end")
    if cps: state.current_period_start = datetime.fromtimestamp(cps, tz=timezone.utc)
    if cpe: state.current_period_end   = datetime.fromtimestamp(cpe, tz=timezone.utc)
    db.session.add(state)

def on_subscription_deleted(event_id: str, subscription: dict):
    if not _mark_event(event_id): return
    user_id = _user_id_by_customer(subscription.get("customer"))
    if not user_id: return
    state = db.session.get(CreditUserState, user_id) or CreditUserState(user_id=user_id)
    state.billing_status = "canceled"
    state.pro_active = 0
    db.session.add(state)
    expire_all_monthly(user_id, ref=f"sub_cancel_{subscription.get('id')}")
    apply_entitlements(user_id, "free")

def on_checkout_completed(event_id: str, session: dict):
    if not _mark_event(event_id): return
    if session.get("mode") != "payment":  # we only grant packs here
        return
    user_id = _user_id_by_customer(session.get("customer"))
    if not user_id: return
    pack_code = ((session.get("metadata") or {}).get("pack_code")) or ""
    pack = TOPUP_PACKS.get(pack_code)
    if not pack: return
    grant_topup(user_id, pack.credits_mic, ref=f"cs_{session.get('id')}")

def on_invoice_payment_failed(event_id: str, invoice: dict):
    if not _mark_event(event_id):
        return
    user_id = _user_id_by_customer(invoice.get("customer"))
    if not user_id:
        return
    state = db.session.get(CreditUserState, user_id) or CreditUserState(user_id=user_id)
    state.billing_status = "past_due"
    # keep Pro active during grace
    if state.pro_active != 1:
        state.pro_active = 1
    if not state.past_due_since:
        state.past_due_since = datetime.now(timezone.utc)
    db.session.add(state)
