from flask import Blueprint

billing_bp = Blueprint("billing_bp", __name__, url_prefix="/billing")
billing_webhooks_bp = Blueprint("billing_webhooks_bp", __name__, url_prefix="/billing/webhook")

from . import routes, webhooks  