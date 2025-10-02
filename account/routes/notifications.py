from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from .. import account_bp
from ..models import AccountNotificationPrefs

def wants_fragment() -> bool:
    return request.args.get("fragment") == "1" or request.headers.get("X-Fragment") == "1"

def as_bool(v) -> bool:
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in ("1", "true", "on", "yes")

@account_bp.route("/notifications", methods=["GET", "POST"])
@jwt_required()
def notifications():
    user_id = get_jwt_identity()

    def _ensure_prefs(uid: int) -> AccountNotificationPrefs:
        prefs = AccountNotificationPrefs.query.filter_by(user_id=uid).first()
        if prefs:
            return prefs

        # Python-side defaults that mirror your model intent
        prefs = AccountNotificationPrefs(
            user_id=uid,
            # group flags (for back-compat/UI grouping)
            product_updates=True,
            marketing_emails=False,
            security_alerts=True,
            # granular flags
            login_alerts=True,
            password_change_alerts=True,
            tfa_change_alerts=True,
            new_tools_updates=True,
            feature_updates=True,
            promotions=False,
            newsletter=False,
            scan_completion=True,
            weekly_summary=False,
        )
        db.session.add(prefs)
        db.session.commit()
        return prefs

    prefs = _ensure_prefs(user_id)


    if request.method == "POST" or request.is_json:
        data = request.get_json(silent=True) or request.form

        # Granular fields (names match the template below)
        prefs.login_alerts            = as_bool(data.get("login_alerts"))
        prefs.password_change_alerts  = as_bool(data.get("password_change_alerts"))
        prefs.tfa_change_alerts       = as_bool(data.get("tfa_change_alerts"))

        prefs.new_tools_updates       = as_bool(data.get("new_tools_updates"))
        prefs.feature_updates         = as_bool(data.get("feature_updates"))

        # Marketing
        if as_bool(data.get("unsubscribe_all_marketing")):
            prefs.promotions = False
            prefs.newsletter = False
        else:
            prefs.promotions = as_bool(data.get("promotions"))
            prefs.newsletter = as_bool(data.get("newsletter"))

        # In-app
        prefs.scan_completion         = as_bool(data.get("scan_completion"))
        prefs.weekly_summary          = as_bool(data.get("weekly_summary"))

        # Keep GROUP flags in sync (OR of granular)
        prefs.recompute_groups()

        db.session.add(prefs); db.session.commit()
        flash("Notification preferences saved.", "success")

        if wants_fragment():
            return render_template("account/partials/notifications.html", prefs=prefs)

        if request.is_json:
            return jsonify({
                "ok": True,
                "prefs": {
                    "security_alerts": prefs.security_alerts,
                    "product_updates": prefs.product_updates,
                    "marketing_emails": prefs.marketing_emails,
                    "login_alerts": prefs.login_alerts,
                    "password_change_alerts": prefs.password_change_alerts,
                    "tfa_change_alerts": prefs.tfa_change_alerts,
                    "new_tools_updates": prefs.new_tools_updates,
                    "feature_updates": prefs.feature_updates,
                    "promotions": prefs.promotions,
                    "newsletter": prefs.newsletter,
                    "scan_completion": prefs.scan_completion,
                    "weekly_summary": prefs.weekly_summary,
                }
            })

        return redirect(url_for("account.notifications"))

    # GET
    if wants_fragment():
        return render_template("account/partials/notifications.html", prefs=prefs)
    return render_template("account/shell.html", prefs=prefs,
                           partial="account/partials/notifications.html")
