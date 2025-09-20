from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from auth.models import User
from .. import account_bp
from ..models import AccountProfile

@account_bp.route("/", methods=["GET"])
@jwt_required()
def home():
    return redirect(url_for("account.profile"))

@account_bp.route("/profile", methods=["GET", "POST"])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    prof = user.account_profile or AccountProfile(user_id=user.id)

    if request.method == "POST":
        user.name        = request.form.get("name") or user.name
        prof.timezone    = request.form.get("timezone") or prof.timezone or "UTC"
        prof.locale      = request.form.get("locale")   or prof.locale   or "en"
        prof.avatar_url  = request.form.get("avatar_url") or prof.avatar_url
        prof.bio         = request.form.get("bio") or prof.bio
        user.account_profile = prof
        db.session.add_all([user, prof]); db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account.profile"))

    return render_template("account/profile.html", user=user, prof=prof)
