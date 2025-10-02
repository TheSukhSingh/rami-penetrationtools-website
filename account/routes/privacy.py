from __future__ import annotations
from datetime import datetime, timezone, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from .. import account_bp
from ..models import DataExportJob, AccountDeletionRequest, DeletionRequestStatus, DataExportStatus

# We’ll try to read the grace days from the Setting KV store if present.
# Falls back to 7 days. Your Setting model already exists in the project.
def _grace_days_default() -> int:
    try:
        from models import Setting  # generic KV; lives outside account app
        s = Setting.query.filter_by(key="account.deletion_grace_days").first()
        if s and s.value is not None:
            # allow int / str / {"days": N}
            if isinstance(s.value, dict) and "days" in s.value:
                return int(s.value["days"])
            return int(s.value)
    except Exception:
        pass
    return 7  # sane default

def wants_fragment() -> bool:
    return request.args.get("fragment") == "1" or request.headers.get("X-Fragment") == "1"

def _ctx(user_id: int) -> dict:
    # last completed export
    last = (DataExportJob.query
            .filter_by(user_id=user_id, status=DataExportStatus.COMPLETED.value)
            .order_by(DataExportJob.finished_at.desc())
            .first())
    last_export_at = None
    if last and last.finished_at:
        # render plainly; you can localize in Jinja
        last_export_at = last.finished_at.isoformat(sep=" ", timespec="seconds")

    return {
        "last_export_at": last_export_at,
        "deletion_grace_days": _grace_days_default(),
    }

@account_bp.route("/privacy", methods=["GET"])
@jwt_required()
def privacy():
    user_id = get_jwt_identity()
    ctx = _ctx(user_id)
    if wants_fragment():
        return render_template("account/partials/privacy.html", **ctx)
    return render_template("account/shell.html", partial="account/partials/privacy.html", **ctx)

@account_bp.route("/privacy/export", methods=["POST"])
@jwt_required()
def privacy_export():
    user_id = get_jwt_identity()

    # Create a queued export job (your worker will pick this up)
    job = DataExportJob(user_id=user_id, status=DataExportStatus.QUEUED.value)
    db.session.add(job)
    db.session.commit()

    flash("Data export requested. You’ll receive an email when it’s ready.", "success")

    ctx = _ctx(user_id)
    if wants_fragment():
        return render_template("account/partials/privacy.html", **ctx)
    return redirect(url_for("account.privacy"))

@account_bp.route("/privacy/delete", methods=["POST"])
@jwt_required()
def privacy_delete():
    user_id = get_jwt_identity()
    days = _grace_days_default()
    now = datetime.now(timezone.utc)

    # Allow only a single active (pending/confirmed) request at a time
    active = (AccountDeletionRequest.query
              .filter(AccountDeletionRequest.user_id == user_id,
                      AccountDeletionRequest.status.in_([
                          DeletionRequestStatus.PENDING.value,
                          DeletionRequestStatus.CONFIRMED.value
                      ]))
              .first())

    if active:
        flash("There is already an active deletion request.", "info")
    else:
        scheduled = now + timedelta(days=days)
        dr = AccountDeletionRequest(
            user_id=user_id,
            status=DeletionRequestStatus.PENDING.value,
            requested_at=now,
            scheduled_delete_at=scheduled,
            created_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")
        )
        db.session.add(dr)
        db.session.commit()
        flash(f"Delete account request queued. Scheduled on {scheduled.date()} (UTC). We’ll email steps to confirm.", "warning")

    ctx = _ctx(user_id)
    if wants_fragment():
        return render_template("account/partials/privacy.html", **ctx)
    return redirect(url_for("account.privacy"))
