# admin/routes.py
from flask import render_template, abort, redirect, request, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from auth.models import User
from . import admin_bp

def _guard_or_redirect():
    uid = get_jwt_identity()
    if not uid:
        return False
    user = db.session.get(User, int(uid))
    if not user or not (user.is_admin_user or user.is_master_user):
        return False
    return True

@admin_bp.route("/", methods=["GET"])
@jwt_required()
def admin_index():
    if _guard_or_redirect():
        return render_template("admin/admin.html")

    return redirect(url_for('index'))

@admin_bp.route("/<path:subpath>", methods=["GET"])
@jwt_required()
def admin_catchall(subpath):
    _guard_or_redirect()
    if subpath.startswith("api"): 
        abort(404)
    return render_template("admin/admin.html")
