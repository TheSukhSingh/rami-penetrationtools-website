from datetime import datetime, timedelta
from sqlalchemy import and_
from extensions import db
from support.models import SupportTicket, SupportMessage
from auth.models import User
from flask import current_app

from support.notify import (
    notify_status_change_to_user,
    notify_pending_user_reminder,
    notify_auto_close_reminder,
)

# Celery instance lives in celery_app.celery; we import there to register tasks.
from celery_app import celery


def _system_note(ticket_id: int, body: str, public: bool = True):
    msg = SupportMessage(
        ticket_id=ticket_id,
        author_user_id=None,            # SYSTEM
        visibility=("public" if public else "internal"),
        body=body,
    )
    db.session.add(msg)
    return msg


def _already_noted(ticket_id: int, marker: str, since_dt: datetime) -> bool:
    """
    Avoid duplicate reminders: check if a system message containing `marker`
    exists since `since_dt`.
    """
    q = (SupportMessage.query
         .filter(SupportMessage.ticket_id == ticket_id)
         .filter(SupportMessage.author_user_id.is_(None))
         .filter(SupportMessage.created_at >= since_dt))
    for m in q.all():
        if marker in (m.body or ""):
            return True
    return False


@celery.task(name="support.tasks.pending_user_reminders")
def pending_user_reminders():
    """
    Send a reminder email + system message for tickets stuck in `pending_user`
    for >= SUPPORT_PENDING_REMINDER_DAYS (based on ticket.updated_at).
    """
    now = datetime.utcnow()
    days = int(current_app.config.get("SUPPORT_PENDING_REMINDER_DAYS", 3))
    threshold = now - timedelta(days=days)

    stuck = (SupportTicket.query
             .filter(SupportTicket.status == "pending_user")
             .filter(SupportTicket.updated_at <= threshold)
             .all())

    sent = 0
    for t in stuck:
        requester = User.query.get(t.requester_user_id)
        if not requester or not getattr(requester, "email", None):
            continue

        marker = "[system] pending reminder"
        # don’t spam: if we posted a reminder within the last `days`, skip
        if _already_noted(t.id, marker, since_dt=now - timedelta(days=days)):
            continue

        try:
            _system_note(t.id, f"{marker}: waiting for user reply", public=True)
            notify_pending_user_reminder(t, requester, days)
            # touch updated_at so we don’t re-trigger every run
            t.updated_at = now
            db.session.commit()
            sent += 1
        except Exception:
            db.session.rollback()
            current_app.logger.exception("[support.tasks] pending reminder failed for ticket=%s", t.id)

    return {"reminders_sent": sent, "pending_user_candidates": len(stuck)}


@celery.task(name="support.tasks.auto_close_and_remind")
def auto_close_and_remind():
    """
    1) For tickets in `solved`:
       - send an auto-close reminder at (solved_at + auto_close_days - 1) if not already sent
       - auto-close at (solved_at + auto_close_days)
    """
    now = datetime.utcnow()
    days = int(current_app.config.get("SUPPORT_AUTO_CLOSE_DAYS", 7))
    remind_at = now - timedelta(days=days - 1)  # “1 day before close”
    close_at  = now - timedelta(days=days)

    # We only consider tickets that actually have solved_at set
    q = (SupportTicket.query
         .filter(SupportTicket.status == "solved")
         .filter(SupportTicket.solved_at.isnot(None)))

    todo = q.all()
    reminded = 0
    closed = 0

    for t in todo:
        requester = User.query.get(t.requester_user_id)
        if not requester or not getattr(requester, "email", None):
            continue

        # (a) Reminder window (exactly one day before close or later, but not yet closed)
        if t.solved_at <= remind_at:
            marker = "[system] auto-close reminder"
            if not _already_noted(t.id, marker, since_dt=t.solved_at):
                try:
                    _system_note(t.id, f"{marker}: will close soon", public=True)
                    notify_auto_close_reminder(t, requester, 1)
                    # don’t change status here; just update updated_at to avoid repeats
                    t.updated_at = now
                    db.session.commit()
                    reminded += 1
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("[support.tasks] auto-close reminder failed for ticket=%s", t.id)

        # (b) Close window
        if t.solved_at <= close_at:
            try:
                marker2 = "[system] auto-closed"
                if not _already_noted(t.id, marker2, since_dt=t.solved_at):
                    _system_note(t.id, f"{marker2}: no reply after {days} days", public=True)
                # Close the ticket
                t.status = "closed"
                t.closed_at = now
                t.updated_at = now
                db.session.commit()

                try:
                    notify_status_change_to_user(t, requester)
                except Exception:
                    current_app.logger.exception("[support.tasks] close notify failed for ticket=%s", t.id)

                closed += 1
            except Exception:
                db.session.rollback()
                current_app.logger.exception("[support.tasks] auto-close failed for ticket=%s", t.id)

    return {"reminders_sent": reminded, "closed": closed, "solved_candidates": len(todo)}
