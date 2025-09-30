from flask import Blueprint

support_bp = Blueprint(
    "support",
    __name__,
    url_prefix="/support",
    template_folder="templates",
    static_folder="static",
)
from extensions import csrf
csrf.exempt(support_bp)
# Make sure models are imported so Alembic detects them
from . import models            # ← add this line
from . import routes            # keep this
