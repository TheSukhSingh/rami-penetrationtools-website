from __future__ import annotations
from flask import Blueprint

# Package-level blueprint (consistent with your other modules)
credits_bp = Blueprint("credits_bp", __name__, url_prefix="/credits")

# Bind routes onto this blueprint
from . import routes
