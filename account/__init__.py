from flask import Blueprint

account_bp = Blueprint(
    "account",
    __name__,
    url_prefix="/account",
    template_folder="templates",
    static_folder="static",
    static_url_path="/account/static",
)

# Route modules
from .routes import notifications, privacy, profile, security, sessions
