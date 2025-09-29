from flask import Blueprint

# /support routes (ticket-only module; we'll add models in Task 2)
support_bp = Blueprint(
    "support",
    __name__,
    url_prefix="/support",
    template_folder="templates",
    static_folder="static",
)

# Import routes so they register
from . import routes  # noqa: E402,F401
