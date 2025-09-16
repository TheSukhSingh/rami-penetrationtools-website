from flask import Blueprint

user_dashboard_bp = Blueprint(
    "user_dashboard",
    __name__,
    url_prefix="/dashboard",
    template_folder="templates",
    static_folder="static",
)

# Import routes to attach them to the blueprint
from .api import dashboard  # noqa: E402,F401
