# admin/routes.py
from flask import render_template, abort, redirect, request, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from auth.models import User
from . import admin_bp

def _guard_or_redirect():
    print(2)
    uid = get_jwt_identity()
    print(3)
    if not uid:
        return False
    print(4)
    user = db.session.get(User, int(uid))
    print(5)
    # use your hybrid props from the auth model
    if not user or not (user.is_admin_user or user.is_master_user):
        print(5.5)
        return False
        # abort(403)
    print(6)
    return True

@admin_bp.route("/", methods=["GET"])
@jwt_required()
def admin_index():
    print(1)
    if _guard_or_redirect():
        return render_template("admin/admin.html")
    else:
        return redirect(url_for('index'))
    print(7)

@admin_bp.route("/<path:subpath>", methods=["GET"])
@jwt_required()
def admin_catchall(subpath):
    _guard_or_redirect()
    if subpath.startswith("api"): 
        abort(404)
    return render_template("admin/admin.html")
