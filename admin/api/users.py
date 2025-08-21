# from flask import request
# from admin.api import admin_api_bp
# from admin.api.common import ok, parse_pagination, parse_sort, get_json
# from admin.permissions import require_scopes
# from admin.services.user_service import UserService

# svc = UserService()

# @admin_api_bp.get("/users/summary")
# # @require_scopes("admin.users.read")
# def users_summary():
#     # period = request.args.get("period", "7d")
#     rng = (request.args.get("range") or "7d").lower()
#     data = svc.users_summary()
#     return ok(data)

# @admin_api_bp.get("/users")
# # @require_scopes("admin.users.read")
# def list_users():
#     page, per_page = parse_pagination()
#     # default sort: last_login_at DESC
#     field, is_desc = parse_sort({"last_login_at", "created_at", "email", "username", "name"}, default="-last_login_at")
#     q = request.args.get("q")
#     items, total = svc.list_users(page, per_page, q, field, is_desc)
#     return ok(
#         items, 
#         meta={"page": page, "per_page": per_page, "total": total, "q": q, "sort": ("-" if is_desc else "") + field}
#     )

# @admin_api_bp.get("/users/<int:user_id>")
# # @require_scopes("admin.users.read")
# def user_detail(user_id):
#     data = svc.user_detail(user_id)
#     return ok(data)

# @admin_api_bp.post("/users/<int:user_id>/deactivate")
# # @require_scopes("admin.users.write")
# def deactivate_user(user_id):
#     res = svc.deactivate(user_id)
#     return ok(res)

# @admin_api_bp.post("/users/<int:user_id>/reactivate")
# # @require_scopes("admin.users.write")
# def reactivate_user(user_id):
#     res = svc.reactivate(user_id)
#     return ok(res)

# @admin_api_bp.post("/users/<int:user_id>/tier")
# # @require_scopes("admin.users.write")
# def set_tier(user_id):
#     data = get_json(required=("tier",))
#     res = svc.set_tier(user_id, data["tier"])
#     return ok(res)


from flask import Blueprint, request
from sqlalchemy import func, or_, desc, asc
from extensions import db
from admin.models import User, LoginEvent, ToolScanHistory
from .common import ok, bad_request  # adjust if names differ
from admin.services.user_service import UserService

admin_api_bp = Blueprint("admin_api_users", __name__)
svc = UserService()

@admin_api_bp.get("/users")
def list_users():
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)
        q = (request.args.get("q") or "").strip()
        sort = request.args.get("sort") or "-last_login_at"

        # base
        U = User
        LE = LoginEvent
        SH = ToolScanHistory

        # aggregates
        last_login = func.max(func.nullif(func.cast(LE.occurred_at, db.DateTime), None)).label("last_login_at")
        scan_count = func.count(SH.id).label("scan_count")

        query = (
            db.session.query(U, last_login, scan_count)
            .outerjoin(LE, (LE.user_id == U.id) & (LE.successful == True))
            .outerjoin(SH, SH.user_id == U.id)
            .group_by(U.id)
        )

        if q:
            like = f"%{q.lower()}%"
            query = query.filter(
                or_(
                    func.lower(U.email).like(like),
                    func.lower(U.username).like(like),
                    func.lower(U.name).like(like),
                )
            )

        # total AFTER filters
        total = db.session.query(func.count(U.id))
        if q:
            total = total.filter(
                or_(
                    func.lower(U.email).like(like),
                    func.lower(U.username).like(like),
                    func.lower(U.name).like(like),
                )
            )
        total = total.scalar() or 0

        # sorting
        order_cols = {
            "email": U.email,
            "username": U.username,
            "name": U.name,
            "created_at": U.created_at,
            "last_login_at": last_login,
            "scan_count": scan_count,
        }
        is_desc = sort.startswith("-")
        key = sort[1:] if is_desc else sort
        col = order_cols.get(key, last_login)
        query = query.order_by(desc(col) if is_desc else asc(col))

        rows = (
            query.offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # serialize
        items = []
        for u, last_login_at, scans in rows:
            tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
            items.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "name": u.name,
                "is_deactivated": bool(u.is_deactivated),
                "tier": tier,
                "scan_count": int(scans or 0),
                "last_login_at": last_login_at.isoformat() if last_login_at else None,
            })

        return ok({"items": items, "meta": {"page": page, "per_page": per_page, "total": total}})
    except Exception as e:
        db.session.rollback()
        # surface the error message to help you debug quickly
        return bad_request(str(e))

@admin_api_bp.get("/users/<int:user_id>")
def user_detail(user_id):
    U = User
    LE = LoginEvent
    SH = ToolScanHistory

    u = U.query.get(user_id)
    if not u:
        return bad_request("User not found")

    # last login
    last_login_at = db.session.query(func.max(LE.occurred_at)).filter(LE.user_id == user_id, LE.successful == True).scalar()

    # scans
    scan_count = db.session.query(func.count(SH.id)).filter(SH.user_id == user_id).scalar()

    # recent IP logs (if you have the model)
    ip_logs = []
    try:
        from admin.models import UserIPLog
        logs = (
            db.session.query(UserIPLog)
            .filter(UserIPLog.user_id == user_id)
            .order_by(UserIPLog.created_at.desc())
            .limit(10)
            .all()
        )
        ip_logs = [
            {
                "ip": x.ip,
                "user_agent": x.user_agent,
                "device": x.device,
                "created_at": x.created_at.isoformat() if x.created_at else None,
            }
            for x in logs
        ]
    except Exception:
        pass

    tier = next((r.name for r in (u.roles or []) if (r.name or "").startswith("tier_")), None)
    return ok({
        "id": u.id,
        "email": u.email,
        "username": u.username,
        "name": u.name,
        "is_deactivated": bool(u.is_deactivated),
        "tier": tier,
        "scan_count": int(scan_count or 0),
        "last_login_at": last_login_at.isoformat() if last_login_at else None,
        "ip_logs": ip_logs,
    })

@admin_api_bp.get("/users/summary")
def users_summary():
    rng = (request.args.get("range") or "7d").lower()
    data = svc.users_summary(rng)
    return ok(data)
