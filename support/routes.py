from datetime import datetime
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

# Uses your existing auth models
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


# ---------- helpers -----------------------------------------------------------

def _set_status(ticket: SupportTicket, new_status: str):
    """
    Centralized status setter with ancillary timestamp updates.
    """
    if new_status not in STATUS_VALUES:
        abort(400, description="invalid status")

    now = datetime.utcnow()

    # Clear resolution timestamps on re-open-ish states
    if new_status in ("new", "open", "pending_user", "on_hold"):
        ticket.solved_at = None
        ticket.closed_at = None

    # Set resolution timestamps appropriately
    if new_status == "solved":
        ticket.solved_at = now
        ticket.closed_at = None
    elif new_status == "closed":
        ticket.closed_at = now
        # keep solved_at as-is if it was set earlier, otherwise None

    ticket.status = new_status
    ticket.updated_at = now


# ---------- existing endpoints ------------------------------------------------

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
    return jsonify({
        "ok": True,
        "message": "Admin Support Console (Solo Mode) ready.",
        "next": ["/support (user view)", "/support/admin (this)", "Ticket CRUD in Task 5+"]
    })


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
      - context (optional, dict)
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

    meta = {
        "ua": request.headers.get("User-Agent"),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }
    if payload.get("tool"):
        meta["tool"] = str(payload["tool"])
    if payload.get("category"):
        meta["category"] = str(payload["category"])
    if isinstance(payload.get("context"), dict):
        meta["context"] = payload["context"]

    requester_id = get_jwt_identity()
    default_assignee_id = _get_admin_owner_user_id()

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
    db.session.flush()

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
    me_user, is_admin = current_user_and_admin()

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    if not is_admin and (not me_user or t.requester_user_id != me_user.id):
        abort(403)

    if is_admin:
        msgs_q = (SupportMessage.query
                  .filter_by(ticket_id=t.id)
                  .order_by(SupportMessage.created_at.asc()))
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


# ---------- NEW: Task 4 endpoints --------------------------------------------

@support_bp.post("/t/<int:ticket_id>/reply")
@auth_required
def support_ticket_reply(ticket_id: int):
    """
    Add a reply to a ticket.
    Body: JSON
      - body (str, required, <=10000)
      - internal (bool, optional; admin_owner only; default False)
      - set_status (str, optional; admin_owner only)
          one of: new|open|pending_user|on_hold|solved|closed
    Behavior:
      - User (requester): public-only; on reply, auto-reopen to 'open' if status in pending_user/solved/closed.
      - Admin: can post public or internal; if ticket was 'new', default to 'open' unless set_status provided.
    """
    me_user, is_admin = current_user_and_admin()
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if not body:
        abort(400, description="body is required")
    if len(body) > 10000:
        abort(400, description="body too long (max 10000)")

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    # Row-level guard for non-admins
    if not is_admin and (not me_user or t.requester_user_id != me_user.id):
        abort(403)

    now = datetime.utcnow()

    # Visibility
    internal = bool(payload.get("internal", False)) if is_admin else False
    visibility = "internal" if internal else "public"

    # Create message
    msg = SupportMessage(
        ticket_id=t.id,
        author_user_id=(me_user.id if me_user else None),
        visibility=visibility,
        body=body,
    )
    db.session.add(msg)

    # Status transitions
    if is_admin:
        requested = (payload.get("set_status") or "").strip().lower()
        if requested:
            _set_status(t, requested)
        else:
            # Default: first admin reply transitions 'new' -> 'open'
            if t.status == "new":
                _set_status(t, "open")
            else:
                t.updated_at = now
    else:
        # User reply: auto-reopen
        if t.status in ("pending_user", "solved", "closed"):
            _set_status(t, "open")
        else:
            t.updated_at = now

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": {
            "id": msg.id,
            "visibility": msg.visibility,
            "created_at": msg.created_at.isoformat(),
        },
        "ticket": {
            "id": t.id,
            "status": t.status,
            "updated_at": t.updated_at.isoformat(),
            "solved_at": t.solved_at.isoformat() if t.solved_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
    }), 201


@support_bp.patch("/t/<int:ticket_id>/status")
@admin_required
def support_ticket_set_status(ticket_id: int):
    """
    Admin-only status change.
    Body: JSON
      - status (str, required): new|open|pending_user|on_hold|solved|closed
    """
    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or "").strip().lower()
    if not new_status:
        abort(400, description="status is required")

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    _set_status(t, new_status)
    db.session.commit()

    return jsonify({
        "ok": True,
        "ticket": {
            "id": t.id,
            "status": t.status,
            "updated_at": t.updated_at.isoformat(),
            "solved_at": t.solved_at.isoformat() if t.solved_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
    })
