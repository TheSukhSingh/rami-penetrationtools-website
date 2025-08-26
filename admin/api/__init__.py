from flask import Blueprint, jsonify, current_app
from admin.errors import AdminError, ServerError

admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/admin/api")

# Health probe
@admin_api_bp.get("/_health")
def _health():
    return jsonify({"ok": True, "service": "admin_api"}), 200

# Centralized error handling for AdminError and unexpected exceptions
@admin_api_bp.app_errorhandler(AdminError)
def handle_admin_error(err: AdminError):
    return jsonify(err.to_dict()), err.status_code

@admin_api_bp.app_errorhandler(Exception)
def handle_uncaught_error(err: Exception):
    # In debug, include a short repr; in prod, hide internals.
    payload = ServerError("Something went wrong").to_dict()
    if current_app and current_app.debug:
        payload["error"]["details"] = {"exception": repr(err)}
    print(f"something is wrong - {err}")
    return jsonify(payload), 500

from . import overview, users, scans