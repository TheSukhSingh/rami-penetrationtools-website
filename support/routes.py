from flask import jsonify, current_app
from . import support_bp
from .authz import admin_required, auth_required, current_user_and_admin

@support_bp.get("/")
@auth_required
def support_home():
    user, is_admin = current_user_and_admin()
    return jsonify({
        "ok": True,
        "feature_help": bool(current_app.config.get("FEATURE_HELP", False)),
        "solo_mode": True,
        "me": getattr(user, "email", None),
        "role_view": "admin" if is_admin else "user",
        "message": "Support Center (Solo Mode) is live."
    })

@support_bp.get("/admin")
@admin_required
def support_admin_home():
    # Thin stub — inbox/workspace come in next tasks
    return jsonify({
        "ok": True,
        "message": "Admin Support Console (Solo Mode) ready.",
        "next": ["/support (user view)", "/support/admin (this)", "Ticket CRUD in Task 3+"]
    })
