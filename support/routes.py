from datetime import datetime
from flask import jsonify, current_app, request, abort
from . import support_bp
from .authz import admin_required, auth_required, current_user_and_admin

from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, cast, String, or_
from extensions import db
from support.models import (
    SupportTicket,
    SupportMessage,
    SupportAttachment,
    SupportSnippet,
    STATUS_VALUES,
    PRIORITY_VALUES,
    VISIBILITY_VALUES,
)

# Uses your existing auth models
from auth.models import User, Role

# NEW: notifications
from support.notify import (
    notify_new_ticket,
    notify_user_reply_to_admin,
    notify_admin_public_reply_to_user,
    notify_status_change_to_user,
)

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

    ticket.status = new_status
    ticket.updated_at = now

def _safe_int(val, default=1, min_=1, max_=1000):
    try:
        n = int(val)
        if min_ is not None and n < min_:
            return min_
        if max_ is not None and n > max_:
            return max_
        return n
    except Exception:
        return default

def _ci_like(column, needle: str):
    return func.lower(column).like(f"%{needle.lower()}%")

def _normalize_tags_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []

def _add_tags(ticket: SupportTicket, add_list):
    add = set(_normalize_tags_list(add_list))
    tags = set(_normalize_tags_list(ticket.tags))
    tags |= add
    ticket.tags = sorted(tags)

def _remove_tags(ticket: SupportTicket, rem_list):
    rem = set(_normalize_tags_list(rem_list))
    tags = set(_normalize_tags_list(ticket.tags))
    tags -= rem
    ticket.tags = sorted(tags)

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
        "next": ["/support (user view)", "/support/admin (this)"]
    })

@support_bp.post("/new")
@auth_required
def support_new_ticket():
    """
    Create a new ticket with first public message.
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

    # ── Notifications
    requester = User.query.get(requester_id)
    admin_user = User.query.get(default_assignee_id) if default_assignee_id else None
    try:
        if requester:
            notify_new_ticket(ticket, requester, admin_user=admin_user)
    except Exception:
        current_app.logger.exception("[support] notify_new_ticket failed")

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
            "tags": t.tags or [],
        },
        "messages": messages
    })

@support_bp.post("/t/<int:ticket_id>/reply")
@auth_required
def support_ticket_reply(ticket_id: int):
    """
    Add a reply; also triggers relevant emails.
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

    if not is_admin and (not me_user or t.requester_user_id != me_user.id):
        abort(403)

    now = datetime.utcnow()
    internal = bool(payload.get("internal", False)) if is_admin else False
    visibility = "internal" if internal else "public"

    msg = SupportMessage(
        ticket_id=t.id,
        author_user_id=(me_user.id if me_user else None),
        visibility=visibility,
        body=body,
    )
    db.session.add(msg)

    status_before = t.status

    if is_admin:
        requested = (payload.get("set_status") or "").strip().lower()
        if requested:
            _set_status(t, requested)
        else:
            if t.status == "new":
                _set_status(t, "open")
            else:
                t.updated_at = now
    else:
        if t.status in ("pending_user", "solved", "closed"):
            _set_status(t, "open")
        else:
            t.updated_at = now

    db.session.commit()

    # ── Notifications
    try:
        if is_admin:
            # Admin's public reply → notify requester
            if visibility == "public":
                requester = User.query.get(t.requester_user_id)
                if requester and getattr(requester, "email", None):
                    notify_admin_public_reply_to_user(t, admin_user=me_user, requester=requester)
            # If admin set status to solved/closed in the same call, notify user
            if t.status in ("solved", "closed") and status_before != t.status:
                requester = User.query.get(t.requester_user_id)
                if requester and getattr(requester, "email", None):
                    notify_status_change_to_user(t, requester)
        else:
            # User reply → notify admin_owner (or assignee)
            admin_user = None
            if t.assignee_user_id:
                admin_user = User.query.get(t.assignee_user_id)
            if not admin_user:
                aid = _get_admin_owner_user_id()
                admin_user = User.query.get(aid) if aid else None
            if admin_user and getattr(admin_user, "email", None):
                notify_user_reply_to_admin(t, user=me_user, admin_user=admin_user)
    except Exception:
        current_app.logger.exception("[support] reply notifications failed")

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
    """
    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or "").strip().lower()
    if not new_status:
        abort(400, description="status is required")

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    prev = t.status
    _set_status(t, new_status)
    db.session.commit()

    # ── Notifications on solved/closed
    try:
        if t.status in ("solved", "closed") and prev != t.status:
            requester = User.query.get(t.requester_user_id)
            if requester and getattr(requester, "email", None):
                notify_status_change_to_user(t, requester)
    except Exception:
        current_app.logger.exception("[support] status-change notification failed")

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

# ---------- Admin Inbox & Filters (Task 5) -----------------------------------

@support_bp.get("/admin/tickets")
@admin_required
def support_admin_tickets():
    """
    List tickets with filters, sorting, pagination + status counters.
    """
    args = request.args

    q = SupportTicket.query

    status = (args.get("status") or "").strip().lower()
    if status and status in STATUS_VALUES:
        q = q.filter(SupportTicket.status == status)

    priority = (args.get("priority") or "").strip().lower()
    if priority and priority in PRIORITY_VALUES:
        q = q.filter(SupportTicket.priority == priority)

    requester_email = (args.get("requester_email") or "").strip()
    if requester_email:
        q = (q.join(User, User.id == SupportTicket.requester_user_id)
               .filter(_ci_like(User.email, requester_email)))

    assignee_id = args.get("assignee_id")
    if assignee_id:
        try:
            assignee_id_int = int(assignee_id)
            q = q.filter(SupportTicket.assignee_user_id == assignee_id_int)
        except Exception:
            pass

    tool = (args.get("tool") or "").strip()
    if tool:
        q = q.filter(_ci_like(cast(SupportTicket.meta, String), tool))
    category = (args.get("category") or "").strip()
    if category:
        q = q.filter(_ci_like(cast(SupportTicket.meta, String), category))

    def _parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return None
    date_from = (args.get("date_from") or "").strip()
    date_to   = (args.get("date_to") or "").strip()
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    if df and dt:
        q = q.filter(SupportTicket.created_at >= df,
                     SupportTicket.created_at < (dt.replace(hour=23, minute=59, second=59)))
    elif df:
        q = q.filter(SupportTicket.created_at >= df)
    elif dt:
        q = q.filter(SupportTicket.created_at < (dt.replace(hour=23, minute=59, second=59)))

    search = (args.get("search") or "").strip()
    if search:
        if search.isdigit():
            q = q.filter(or_(
                SupportTicket.id == int(search),
                _ci_like(SupportTicket.subject, search),
                _ci_like(SupportTicket.description, search),
            ))
        else:
            q = q.filter(or_(
                _ci_like(SupportTicket.subject, search),
                _ci_like(SupportTicket.description, search),
            ))

    sort = (args.get("sort") or "created_at").strip()
    sort_map = {
        "created_at": SupportTicket.created_at,
        "updated_at": SupportTicket.updated_at,
        "priority": SupportTicket.priority,
        "status": SupportTicket.status,
    }
    sort_col = sort_map.get(sort, SupportTicket.created_at)

    order = (args.get("order") or "").strip().lower()
    if not order:
        order = "desc" if sort in ("created_at", "updated_at") else "asc"

    if order == "asc":
        q = q.order_by(sort_col.asc(), SupportTicket.id.asc())
    else:
        q = q.order_by(sort_col.desc(), SupportTicket.id.desc())

    page = _safe_int(args.get("page"), default=1, min_=1, max_=100000)
    per_page = _safe_int(args.get("per_page"), default=20, min_=1, max_=100)
    total = q.count()
    rows = q.limit(per_page).offset((page - 1) * per_page).all()

    q_counters = SupportTicket.query
    if priority and priority in PRIORITY_VALUES:
        q_counters = q_counters.filter(SupportTicket.priority == priority)
    if requester_email:
        q_counters = (q_counters.join(User, User.id == SupportTicket.requester_user_id)
                                   .filter(_ci_like(User.email, requester_email)))
    if assignee_id and assignee_id.isdigit():
        q_counters = q_counters.filter(SupportTicket.assignee_user_id == int(assignee_id))
    if tool:
        q_counters = q_counters.filter(_ci_like(cast(SupportTicket.meta, String), tool))
    if category:
        q_counters = q_counters.filter(_ci_like(cast(SupportTicket.meta, String), category))
    if df and dt:
        q_counters = q_counters.filter(SupportTicket.created_at >= df,
                                       SupportTicket.created_at < (dt.replace(hour=23, minute=59, second=59)))
    elif df:
        q_counters = q_counters.filter(SupportTicket.created_at >= df)
    elif dt:
        q_counters = q_counters.filter(SupportTicket.created_at < (dt.replace(hour=23, minute=59, second=59)))
    if search:
        if search.isdigit():
            q_counters = q_counters.filter(or_(
                SupportTicket.id == int(search),
                _ci_like(SupportTicket.subject, search),
                _ci_like(SupportTicket.description, search),
            ))
        else:
            q_counters = q_counters.filter(or_(
                _ci_like(SupportTicket.subject, search),
                _ci_like(SupportTicket.description, search),
            ))

    counts = {s: 0 for s in STATUS_VALUES}
    for s, c in (db.session.query(SupportTicket.status, func.count(SupportTicket.id))
                 .select_from(q_counters.subquery())
                 .group_by(SupportTicket.status)
                 .all()):
        counts[s] = c

    items = [{
        "id": t.id,
        "subject": t.subject,
        "status": t.status,
        "priority": t.priority,
        "requester_user_id": t.requester_user_id,
        "assignee_user_id": t.assignee_user_id,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
        "meta": t.meta or {},
        "tags": t.tags or [],
    } for t in rows]

    return jsonify({
        "ok": True,
        "filters": {
            "status": status or None,
            "priority": priority or None,
            "requester_email": requester_email or None,
            "assignee_id": assignee_id or None,
            "tool": tool or None,
            "category": category or None,
            "search": search or None,
            "date_from": date_from or None,
            "date_to": date_to or None,
            "sort": sort,
            "order": order,
            "page": page,
            "per_page": per_page,
        },
        "counts": counts,
        "total": total,
        "tickets": items,
    })

# ---------- Quick edits, bulk actions, snippets (Task 6) ---------------------

@support_bp.patch("/t/<int:ticket_id>/priority")
@admin_required
def support_ticket_set_priority(ticket_id: int):
    payload = request.get_json(silent=True) or {}
    new_priority = (payload.get("priority") or "").strip().lower()
    if new_priority not in PRIORITY_VALUES:
        abort(400, description="invalid priority")
    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")
    t.priority = new_priority
    t.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "ticket": {"id": t.id, "priority": t.priority, "updated_at": t.updated_at.isoformat()}})

@support_bp.patch("/t/<int:ticket_id>/assign")
@admin_required
def support_ticket_assign(ticket_id: int):
    payload = request.get_json(silent=True) or {}
    assignee_user_id = payload.get("assignee_user_id", None)

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    if assignee_user_id is None:
        t.assignee_user_id = None
    else:
        try:
            uid = int(assignee_user_id)
        except Exception:
            abort(400, description="assignee_user_id must be int or null")
        ok = (db.session.query(User.id)
              .join(User.roles)
              .filter(User.id == uid, Role.name == "admin_owner")
              .first())
        if not ok:
            abort(400, description="assignee must be an admin_owner in Solo Mode")
        t.assignee_user_id = uid

    t.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "ticket": {"id": t.id, "assignee_user_id": t.assignee_user_id, "updated_at": t.updated_at.isoformat()}})

@support_bp.post("/admin/bulk")
@admin_required
def support_admin_bulk_actions():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ticket_ids") or []
    if not isinstance(ids, list) or not ids:
        abort(400, description="ticket_ids list is required")

    q = SupportTicket.query.filter(SupportTicket.id.in_(ids))
    rows = q.all()
    if not rows:
        return jsonify({"ok": True, "updated": 0, "found": 0})

    set_status = (payload.get("set_status") or "").strip().lower()
    if set_status and set_status not in STATUS_VALUES:
        abort(400, description="invalid set_status")

    set_priority = (payload.get("set_priority") or "").strip().lower()
    if set_priority and set_priority not in PRIORITY_VALUES:
        abort(400, description="invalid set_priority")

    assign_to_user_id = payload.get("assign_to_user_id", None)
    if assign_to_user_id is not None:
        try:
            assign_to_user_id = int(assign_to_user_id)
        except Exception:
            abort(400, description="assign_to_user_id must be int")
        ok = (db.session.query(User.id)
              .join(User.roles)
              .filter(User.id == assign_to_user_id, Role.name == "admin_owner")
              .first())
        if not ok:
            abort(400, description="assignee must be an admin_owner in Solo Mode")

    add_tags = payload.get("add_tags")
    remove_tags = payload.get("remove_tags")

    updated = 0
    now = datetime.utcnow()
    for t in rows:
        touched = False
        if set_status:
            _set_status(t, set_status)
            touched = True
        if set_priority:
            t.priority = set_priority
            touched = True
        if assign_to_user_id is not None:
            t.assignee_user_id = assign_to_user_id
            touched = True
        if add_tags:
            _add_tags(t, add_tags)
            touched = True
        if remove_tags:
            _remove_tags(t, remove_tags)
            touched = True
        if touched:
            t.updated_at = now
            updated += 1

    db.session.commit()
    return jsonify({"ok": True, "found": len(rows), "updated": updated})

@support_bp.get("/admin/snippets")
@admin_required
def support_snippets_list():
    active_only = str(request.args.get("active_only", "0")).lower() in ("1", "true", "yes")
    q = SupportSnippet.query
    if active_only:
        q = q.filter(SupportSnippet.is_active.is_(True))
    rows = q.order_by(SupportSnippet.title.asc()).all()
    return jsonify({"ok": True, "snippets": [{
        "id": s.id, "title": s.title, "is_active": s.is_active,
        "updated_at": s.updated_at.isoformat(), "created_at": s.created_at.isoformat()
    } for s in rows]})

@support_bp.post("/admin/snippets")
@admin_required
def support_snippets_create():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title or len(title) > 80:
        abort(400, description="title is required (<=80 chars)")
    if not body or len(body) > 5000:
        abort(400, description="body is required (<=5000 chars)")

    s = SupportSnippet(title=title, body=body, is_active=bool(payload.get("is_active", True)))
    db.session.add(s)
    db.session.commit()
    return jsonify({"ok": True, "snippet": {"id": s.id, "title": s.title, "is_active": s.is_active}}), 201

@support_bp.patch("/admin/snippets/<int:snippet_id>")
@admin_required
def support_snippets_update(snippet_id: int):
    payload = request.get_json(silent=True) or {}
    s = SupportSnippet.query.filter_by(id=snippet_id).first()
    if not s:
        abort(404, description="snippet not found")

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title or len(title) > 80:
            abort(400, description="invalid title")
        s.title = title

    if "body" in payload:
        body = (payload.get("body") or "").strip()
        if not body or len(body) > 5000:
            abort(400, description="invalid body")
        s.body = body

    if "is_active" in payload:
        s.is_active = bool(payload.get("is_active"))

    db.session.commit()
    return jsonify({"ok": True, "snippet": {"id": s.id, "title": s.title, "is_active": s.is_active}})

@support_bp.delete("/admin/snippets/<int:snippet_id>")
@admin_required
def support_snippets_delete(snippet_id: int):
    s = SupportSnippet.query.filter_by(id=snippet_id).first()
    if not s:
        abort(404, description="snippet not found")
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})

@support_bp.post("/t/<int:ticket_id>/apply-snippet")
@admin_required
def support_ticket_apply_snippet(ticket_id: int):
    payload = request.get_json(silent=True) or {}
    sid = payload.get("snippet_id")
    if not sid:
        abort(400, description="snippet_id required")

    t = SupportTicket.query.filter_by(id=ticket_id).first()
    if not t:
        abort(404, description="ticket not found")

    s = SupportSnippet.query.filter_by(id=int(sid), is_active=True).first()
    if not s:
        abort(404, description="snippet not found or inactive")

    internal = bool(payload.get("internal", False))
    visibility = "internal" if internal else "public"

    me_user, _ = current_user_and_admin()
    msg = SupportMessage(
        ticket_id=t.id,
        author_user_id=(me_user.id if me_user else None),
        visibility=visibility,
        body=s.body,
    )
    db.session.add(msg)

    requested = (payload.get("set_status") or "").strip().lower()
    if requested:
        _set_status(t, requested)
    else:
        if t.status == "new" and visibility == "public":
            _set_status(t, "open")
        else:
            t.updated_at = datetime.utcnow()

    db.session.commit()

    # On public snippet post, optionally notify requester (same behavior as admin public reply)
    try:
        if visibility == "public":
            requester = User.query.get(t.requester_user_id)
            if requester and getattr(requester, "email", None):
                notify_admin_public_reply_to_user(t, admin_user=me_user, requester=requester)
        if t.status in ("solved", "closed") and requested:
            requester = User.query.get(t.requester_user_id)
            if requester and getattr(requester, "email", None):
                notify_status_change_to_user(t, requester)
    except Exception:
        current_app.logger.exception("[support] apply-snippet notifications failed")

    return jsonify({
        "ok": True,
        "message": {"id": msg.id, "visibility": visibility, "created_at": msg.created_at.isoformat()},
        "ticket": {"id": t.id, "status": t.status, "updated_at": t.updated_at.isoformat()}
    })
