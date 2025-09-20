from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from .. import account_bp
from ..models import AccountNotificationPrefs

@account_bp.route("/notifications", methods=["GET", "POST"])
@jwt_required()
def notifications():
    user_id = get_jwt_identity()
    prefs = (AccountNotificationPrefs.query.filter_by(user_id=user_id).first()
             or AccountNotificationPrefs(user_id=user_id))

    if request.method == "POST":
        prefs.product_updates  = bool(request.form.get("product_updates"))
        prefs.marketing_emails = bool(request.form.get("marketing_emails"))
        prefs.security_alerts  = bool(request.form.get("security_alerts"))
        db.session.add(prefs); db.session.commit()
        flash("Notification preferences saved.", "success")
        return redirect(url_for("account.notifications"))

    return render_template("account/notifications.html", prefs=prefs)
