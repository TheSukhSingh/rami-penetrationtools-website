from flask import request
from admin.api import admin_api_bp
from admin.api.common import ok, parse_pagination, parse_sort, get_json
from admin.permissions import require_scopes
from admin.services.user_service import UserService

svc = UserService()

@admin_api_bp.get("/users/summary")
@require_scopes("admin.users.read")
def users_summary():
    data = svc.users_summary()
    return ok(data)

@admin_api_bp.get("/users")
@require_scopes("admin.users.read")
def list_users():
    page, per_page = parse_pagination()
    # default sort: last_login_at DESC
    field, is_desc = parse_sort({"last_login_at", "created_at", "email", "username", "name"}, default="-last_login_at")
    q = request.args.get("q")
    items, total = svc.list_users(page, per_page, q, field, is_desc)
    return ok(
        items, 
        meta={"page": page, "per_page": per_page, "total": total, "q": q, "sort": ("-" if is_desc else "") + field}
    )

@admin_api_bp.get("/users/<int:user_id>")
@require_scopes("admin.users.read")
def user_detail(user_id):
    data = svc.user_detail(user_id)
    return ok(data)

@admin_api_bp.post("/users/<int:user_id>/deactivate")
@require_scopes("admin.users.write")
def deactivate_user(user_id):
    res = svc.deactivate(user_id)
    return ok(res)

@admin_api_bp.post("/users/<int:user_id>/reactivate")
@require_scopes("admin.users.write")
def reactivate_user(user_id):
    res = svc.reactivate(user_id)
    return ok(res)

@admin_api_bp.post("/users/<int:user_id>/tier")
@require_scopes("admin.users.write")
def set_tier(user_id):
    data = get_json(required=("tier",))
    res = svc.set_tier(user_id, data["tier"])
    return ok(res)
