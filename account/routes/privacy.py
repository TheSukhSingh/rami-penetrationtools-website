from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required
from .. import account_bp

@account_bp.route("/privacy", methods=["GET"])
@jwt_required()
def privacy():
    return render_template("account/privacy.html")

@account_bp.route("/privacy/export", methods=["POST"])
@jwt_required()
def privacy_export():
    # TODO: enqueue background job
    flash("Data export requested. You’ll receive an email when it’s ready.", "success")
    return redirect(url_for("account.privacy"))

@account_bp.route("/privacy/delete", methods=["POST"])
@jwt_required()
def privacy_delete():
    # TODO: queue delete (grace period)
    flash("Delete account request queued. We’ll email steps to confirm.", "warning")
    return redirect(url_for("account.privacy"))
