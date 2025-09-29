from flask import current_app, request
from flask_mail import Message

def _mail_ext():
    """
    Return Flask-Mail extension if initialized (auth.utils.init_mail does this).
    """
    try:
        return current_app.extensions.get("mail")  # type: ignore
    except Exception:
        return None

def _sender():
    return current_app.config.get("MAIL_DEFAULT_SENDER") or "no-reply@localhost"

def _base_url():
    # Prefer explicit EXTERNAL_BASE_URL, else request.url_root
    base = current_app.config.get("EXTERNAL_BASE_URL")
    if base:
        return str(base).rstrip("/")
    try:
        return str(request.url_root).rstrip("/")
    except Exception:
        # fallback if no request context
        return ""

def _ticket_url(ticket_id: int):
    base = _base_url()
    if not base:
        return f"/support/t/{ticket_id}"
    return f"{base}/support/t/{ticket_id}"

def _send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    mail = _mail_ext()
    if not mail:
        current_app.logger.warning("[support.notify] Mail extension not configured; would send → %s | %s", to_email, subject)
        return False
    try:
        msg = Message(subject=subject, recipients=[to_email], sender=_sender(), body=text_body or None, html=html_body or None)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.exception("[support.notify] send failed → %s | %s | %r", to_email, subject, e)
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Notification composers
# ─────────────────────────────────────────────────────────────────────────────

def notify_new_ticket(ticket, requester, admin_user=None):
    """
    - To requester: receipt
    - To admin: new ticket
    """
    link = _ticket_url(ticket.id)
    subj_user = f"[hackr.gg] Ticket #{ticket.id} received — {ticket.subject}"
    html_user = f"""
        <p>Hi {getattr(requester, 'name', requester.email)},</p>
        <p>We received your ticket <strong>#{ticket.id}</strong>: “{ticket.subject}”.</p>
        <p>You can follow and reply here: <a href="{link}">{link}</a></p>
        <p>— Support</p>
    """
    _send_email(requester.email, subj_user, html_user)

    if admin_user and getattr(admin_user, "email", None):
        subj_admin = f"[Support] New ticket #{ticket.id} — {ticket.subject}"
        html_admin = f"""
            <p>New ticket from <strong>{requester.email}</strong>.</p>
            <p><a href="{link}">Open Ticket #{ticket.id}</a></p>
            <pre style="white-space:pre-wrap">{ticket.description}</pre>
        """
        _send_email(admin_user.email, subj_admin, html_admin)

def notify_user_reply_to_admin(ticket, user, admin_user):
    """
    User replied → notify admin_owner.
    """
    if not admin_user or not getattr(admin_user, "email", None):
        return
    link = _ticket_url(ticket.id)
    subj = f"[Support] User replied on #{ticket.id} — {ticket.subject}"
    html = f"""
        <p>{getattr(user, 'email', 'User')} replied on ticket #{ticket.id}.</p>
        <p><a href="{link}">Open Ticket</a></p>
    """
    _send_email(admin_user.email, subj, html)

def notify_admin_public_reply_to_user(ticket, admin_user, requester):
    """
    Admin posted a public reply → notify requester.
    """
    link = _ticket_url(ticket.id)
    subj = f"[hackr.gg] Update on ticket #{ticket.id} — {ticket.subject}"
    html = f"""
        <p>Hi {getattr(requester, 'name', requester.email)},</p>
        <p>We’ve posted an update on your ticket <strong>#{ticket.id}</strong>.</p>
        <p>View it here: <a href="{link}">{link}</a></p>
        <p>— Support</p>
    """
    _send_email(requester.email, subj, html)

def notify_status_change_to_user(ticket, requester):
    """
    Status → solved/closed → notify requester.
    """
    link = _ticket_url(ticket.id)
    subj = f"[hackr.gg] Ticket #{ticket.id} {ticket.status} — {ticket.subject}"
    extra = ""
    if ticket.status == "solved":
        extra = "<p>If this didn’t resolve it, just reply to reopen the ticket.</p>"
    html = f"""
        <p>Hi {getattr(requester, 'name', requester.email)},</p>
        <p>Your ticket <strong>#{ticket.id}</strong> is now <strong>{ticket.status}</strong>.</p>
        {extra}
        <p>Details: <a href="{link}">{link}</a></p>
        <p>— Support</p>
    """
    _send_email(requester.email, subj, html)

def notify_pending_user_reminder(ticket, requester, days_waited: int):
    link = _ticket_url(ticket.id)
    subj = f"[hackr.gg] Reminder: we’re waiting on you (Ticket #{ticket.id})"
    html = f"""
        <p>Hi {getattr(requester, 'name', requester.email)},</p>
        <p>We’re still waiting for your reply on ticket <strong>#{ticket.id}</strong> (“{ticket.subject}”).</p>
        <p>Please reply here: <a href="{link}">{link}</a></p>
        <p>— Support</p>
    """
    _send_email(requester.email, subj, html)

def notify_auto_close_reminder(ticket, requester, days_remaining: int):
    link = _ticket_url(ticket.id)
    subj = f"[hackr.gg] Ticket #{ticket.id} will auto-close soon"
    html = f"""
        <p>Hi {getattr(requester, 'name', requester.email)},</p>
        <p>Your ticket <strong>#{ticket.id}</strong> is currently <strong>solved</strong>. If you still need help, just reply.</p>
        <p>Otherwise it will auto-close in <strong>{days_remaining} day(s)</strong>.</p>
        <p>Link: <a href="{link}">{link}</a></p>
        <p>— Support</p>
    """
    _send_email(requester.email, subj, html)
