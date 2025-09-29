from flask import jsonify, current_app, request, abort
from . import support_bp
from .authz import admin_required, auth_required, current_user_and_admin

from flask_jwt_extended import get_jwt_identity
from extensions import db
from support.models import (
    SupportTicket,
    SupportMessage,
    STATUS_VALUES,
    PRIORITY_VALUES,
    VISIBILITY_VALUES,
)

# You already have admin_owner role; we’ll assign tickets to the first admin_owner by default.
from auth.models import User, Role


def _get_admin_owner_user_id():
    """
    Returns a user.id who has Role 'admin_owner', or None if not found.
    """
    try:
        admin_user_id = (
            db.session.query(User.id)
            .join(User.roles)
            .filter(Role.name == "admin_owner")
            .order_by(User.id.asc())
            .first()
        )
        return admin_user_id[0] if admin_user_id else None
    except Exception:
        return None


@support_bp.get("/")
@auth_required
def support_home():
    user, is_admin = current_user_and_admin()
    return jsonify({
        "ok": True,
        "feature_help": bool(current_app.config.get("FEATURE_HELP", False)),
        "solo_mode": True,
        "me": getattr(user, "email", None),
        "role_view": "admin" if is_admin else "user",
        "message": "Support Center (Solo Mode) is live."
    })


@support_bp.get("/admin")
@admin_required
def support_admin_home():
    # Thin stub — inbox/workspace come in next tasks
    return jsonify({
        "ok": True,
        "message": "Admin Support Console (Solo Mode) ready.",
        "next": ["/support (user view)", "/support/admin (this)", "Ticket CRUD in Task 4+"]
    })


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 endpoints
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.post("/new")
@auth_required
def support_new_ticket():
    """
    Create a new ticket with first public message.
    Body: JSON
      - subject (str, required, <=150)
      - description (str, required, <=10000)
      - priority (optional: low|normal|high|urgent; default normal)
      - tool (optional, str)
      - category (optional, str)
      - context (optional, dict)  # extra info from FE if available
    """
    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or "").strip()
    description = (payload.get("description") or "").strip()
    priority = (payload.get("priority") or "normal").strip().lower()

    if not subject or not description:
        abort(400, description="subject and description are required")

    if len(subject) > 150:
        abort(400, description="subject too long (max 150)")

    if len(description) > 10000:
        abort(400, description="description too long (max 10000)")

    if priority not in PRIORITY_VALUES:
        priority = "normal"

    # Build meta from request headers + optional fields
    meta = {
        "ua": request.headers.get("User-Agent"),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }
    # Optional fields from client
    if payload.get("tool"):
        meta["tool"] = str(payload["tool"])
    if payload.get("category"):
        meta["category"] = str(payload["category"])
    if isinstance(payload.get("context"), dict):
        meta["context"] = payload["context"]

    # requester and default assignee
    requester_id = get_jwt_identity()
    default_assignee_id = _get_admin_owner_user_id()

    # Create ticket + first public message
    ticket = SupportTicket(
        requester_user_id=requester_id,
        subject=subject,
        description=description,
        status="new",
        priority=priority,
        assignee_user_id=default_assignee_id,
        meta=meta,
    )
    db.session.add(ticket)
    db.session.flush()  # to get ticket.id

    msg = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=requester_id,
        visibility="public",
        body=description,
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({
        "ok": True,
        "ticket": {
            "id": ticket.id,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
            "assignee_user_id": ticket.assignee_user_id,
            "created_at": ticket.created_at.isoformat(),
        }
    }), 201


@support_bp.get("/my")
@auth_required
def support_my_tickets():
    """
    List the current user's tickets (basic fields for quick verification).
    """
    me = get_jwt_identity()
    q = (SupportTicket.query
         .filter(SupportTicket.requester_user_id == me)
         .order_by(SupportTicket.created_at.desc()))
    items = [{
        "id": t.id,
        "subject": t.subject,
        "status": t.status,
        "priority": t.priority,
        "updated_at": t.updated_at.isoformat(),
    } for t in q.limit(100).all()]

    return jsonify({"ok": True, "tickets": items})


@support_bp.get("/t/<int:ticket_id>")
@auth_required
def support_ticket_detail(ticket_id: int):
    """
    Ticket detail. Users see only their own tickets and only PUBLIC messages.
    Admin (admin_owner) sees all tickets and both PUBLIC + INTERNAL messages.
    """
    me_user, is_admin = current_user_and_admin()

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    # Row-level guard for non-admins: requester only
    if not is_admin and (not me_user or t.requester_user_id != me_user.id):
        abort(403)

    # Message visibility
    if is_admin:
        msgs_q = SupportMessage.query.filter_by(ticket_id=t.id).order_by(SupportMessage.created_at.asc())
    else:
        msgs_q = (SupportMessage.query
                  .filter_by(ticket_id=t.id)
                  .filter(SupportMessage.visibility == "public")
                  .order_by(SupportMessage.created_at.asc()))

    messages = [{
        "id": m.id,
        "author_user_id": m.author_user_id,
        "visibility": m.visibility,
        "body": m.body,
        "created_at": m.created_at.isoformat(),
    } for m in msgs_q.all()]

    return jsonify({
        "ok": True,
        "ticket": {
            "id": t.id,
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "requester_user_id": t.requester_user_id,
            "assignee_user_id": t.assignee_user_id,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
            "meta": t.meta or {},
        },
        "messages": messages
    })
