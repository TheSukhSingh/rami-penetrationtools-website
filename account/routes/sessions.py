from flask import render_template, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from auth.models import RefreshToken
from .. import account_bp

@account_bp.route("/sessions", methods=["GET"])
@jwt_required()
def sessions():
    user_id = get_jwt_identity()
    tokens = (RefreshToken.query
              .filter_by(user_id=user_id)
              .order_by(RefreshToken.revoked.asc(), RefreshToken.expires_at.desc())
              .all())
    return render_template("account/sessions.html", tokens=tokens)

@account_bp.route("/sessions/revoke/<int:token_id>", methods=["POST"])
@jwt_required()
def revoke_session(token_id: int):
    user_id = get_jwt_identity()
    rt = RefreshToken.query.filter_by(id=token_id, user_id=user_id).first()
    if rt:
        rt.revoked = True
        db.session.add(rt); db.session.commit()
        flash("Session revoked.", "success")
    else:
        flash("Not found or not yours.", "error")
    return redirect(url_for("account.sessions"))

@account_bp.route("/sessions/revoke-all", methods=["POST"])
@jwt_required()
def revoke_all_sessions():
    user_id = get_jwt_identity()
    RefreshToken.query.filter_by(user_id=user_id, revoked=False).update({"revoked": True})
    db.session.commit()
    flash("All sessions revoked.", "success")
    return redirect(url_for("account.sessions"))
