# admin/routes.py
from flask import render_template, abort, redirect, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from auth.models import User
from . import admin_bp

def _guard_or_redirect():
    uid = get_jwt_identity()
    if not uid:
        return redirect(f"/auth/signin?next={request.path}")
    user = db.session.get(User, int(uid))
    # use your hybrid props from the auth model
    if not user or not (user.is_admin_user or user.is_master_user):
        abort(403)
    return user

@admin_bp.route("/", methods=["GET"])
@jwt_required()
def admin_index():
    _guard_or_redirect()
    return render_template("admin/admin.html")

@admin_bp.route("/<path:subpath>", methods=["GET"])
@jwt_required()
def admin_catchall(subpath):
    _guard_or_redirect()
    if subpath.startswith("api"): 
        abort(404)
    return render_template("admin/admin.html")
