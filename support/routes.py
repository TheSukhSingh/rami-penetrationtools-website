from flask import jsonify, current_app
from . import help_bp
from .authz import admin_required, auth_required, current_user_and_admin

@help_bp.get("/")
@auth_required
def help_home():
    user, is_admin = current_user_and_admin()
    return jsonify({
        "ok": True,
        "feature_help": bool(current_app.config.get("FEATURE_HELP", False)),
        "solo_mode": True,
        "me": getattr(user, "email", None),
        "role_view": "admin" if is_admin else "user",
        "message": "Help Center (Solo Mode) is live."
    })

@help_bp.get("/admin")
@admin_required
def help_admin_home():
    # Thin stub — in Task 5/6 you'll get the full inbox + workspace
    return jsonify({
        "ok": True,
        "message": "Admin Support Console (Solo Mode) ready.",
        "next": ["/help (user view)", "/help/admin (this)", "Ticket CRUD in Task 2+"]
    })
