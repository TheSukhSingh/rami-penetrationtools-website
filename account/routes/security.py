from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from extensions import db
from auth.models import User
from auth.utils import validate_and_set_password
from auth.models import LocalAuth
from .. import account_bp
from ..email_tokens import make_email_change_token, parse_email_change_token

@account_bp.route("/security", methods=["GET", "POST"])
@jwt_required()
def security():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if request.method == "POST":
        # change password
        current = request.form.get("current_password", "")
        new_pw  = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        la: LocalAuth = user.local_auth
        if not la or not la.check_password(current):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("account.security"))

        if not validate_and_set_password(user, new_pw, confirm, commit=False):
            # helper flashes details; stay on page
            return redirect(url_for("account.security"))

        db.session.add(user.local_auth)
        db.session.commit()
        flash("Password updated.", "success")
        return redirect(url_for("account.security"))

    return render_template("account/security.html", user=user)

@account_bp.route("/security/change-email", methods=["POST"])
@jwt_required()
def change_email_request():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    new_email = (request.form.get("new_email") or "").strip().lower()
    current   = request.form.get("current_password", "")

    la: LocalAuth = user.local_auth
    if not la or not la.check_password(current):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("account.security"))

    if not new_email or "@" not in new_email:
        flash("Enter a valid email address.", "error")
        return redirect(url_for("account.security"))

    exists = User.query.filter(func.lower(User.email) == new_email).first()
    if exists and exists.id != user.id:
        flash("That email is already in use.", "error")
        return redirect(url_for("account.security"))

    token = make_email_change_token(user.id, new_email)
    confirm_url = url_for("account.change_email_confirm", token=token, _external=True)
    print("DEBUG: Email change confirm link:", confirm_url)  # replace with mailer
    flash("Confirmation link sent to the new email (check logs in dev).", "success")
    return redirect(url_for("account.security"))

@account_bp.route("/security/change-email/confirm/<token>", methods=["GET"])
@jwt_required()
def change_email_confirm(token):
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    uid_new = parse_email_change_token(token)
    if not isinstance(uid_new, tuple):
        flash("Email change link is invalid or expired.", "error")
        return redirect(url_for("account.security"))

    uid, new_email = uid_new
    if uid != user.id:
        flash("Email change link is invalid for this account.", "error")
        return redirect(url_for("account.security"))

    exists = User.query.filter(func.lower(User.email) == new_email.lower()).first()
    if exists and exists.id != user.id:
        flash("That email is already in use.", "error")
        return redirect(url_for("account.security"))

    user.email = new_email
    db.session.add(user); db.session.commit()
    flash("Email updated.", "success")
    return redirect(url_for("account.security"))
