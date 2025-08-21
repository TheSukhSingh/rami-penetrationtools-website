
from flask import request
from admin.api import admin_api_bp
from admin.api.common import ok
from admin.services.user_service import UserService
from admin.errors import BadRequest, AdminError, NotFound, ServerError

svc = UserService()

def _to_int(v, default, lo=None, hi=None):
    try:
        x = int(v)
    except Exception:
        return default
    if lo is not None and x < lo: x = lo
    if hi is not None and x > hi: x = hi
    return x

@admin_api_bp.get("/users/summary")
def users_summary():
    rng = (request.args.get("range") or request.args.get("period") or "7d").lower()
    try:
        data = svc.users_summary(rng)
        return ok(data)
    except Exception as e:
        raise BadRequest(str(e))

@admin_api_bp.get("/users")
def list_users():
    print('users table  01')
    page = _to_int(request.args.get("page", 1), 1, 1, None)
    print('users table  02')
    
    per_page = _to_int(request.args.get("per_page", 20), 20, 1, 100)
    
    print('users table  03')
    q = (request.args.get("q") or "").strip() or None
    print('users table  04')
    sort = (request.args.get("sort") or "-last_login_at").strip()

    # normalize sort
    print('users table  05')
    is_desc = sort.startswith("-")
    print('users table  6')
    sort_field = sort[1:] if is_desc else sort
    print('users table  07')
    if sort_field not in ("last_login_at", "created_at", "email", "username", "name", "scan_count"):
        sort_field = "last_login_at"

    print('users table  08')
    try:
        items, total = svc.list_users(page=page, per_page=per_page, q=q, sort_field=sort_field, desc=is_desc)
        return ok(items, meta={"page": page, "per_page": per_page, "total": int(total or 0)})
    except Exception as e:
        print(f'users table  01 error now - {e}')
        raise BadRequest(str(e))

@admin_api_bp.post("/users/<int:user_id>/blocked")
def set_blocked(user_id: int):
    try:
        body = request.get_json(silent=True) or {}
        value = bool(body.get("value"))
        data = svc.set_blocked(user_id, value)
        return ok(data)
    except NotFound as e:
        raise e
    except AdminError as e:
        raise e
    except Exception as e:
        raise ServerError(str(e))

@admin_api_bp.post("/users/<int:user_id>/email_verified")
def set_email_verified(user_id: int):
    try:
        body = request.get_json(silent=True) or {}
        value = bool(body.get("value"))
        data = svc.set_email_verified(user_id, value)
        return ok(data)
    except NotFound as e:
        raise e
    except AdminError as e:
        raise e
    except Exception as e:
        raise ServerError(str(e))


@admin_api_bp.get("/users/<int:user_id>")
def user_detail(user_id: int):
    try:
        data = svc.user_detail(user_id)
        return ok(data)
    except Exception as e:
        raise BadRequest(str(e))

@admin_api_bp.post("/users/<int:user_id>/deactivate")
def deactivate_user(user_id: int):
    try:
        data = svc.deactivate(user_id)
        return ok(data)
    except Exception as e:
        raise BadRequest(str(e))

@admin_api_bp.post("/users/<int:user_id>/reactivate")
def reactivate_user(user_id: int):
    try:
        data = svc.reactivate(user_id)
        return ok(data)
    except Exception as e:
        raise BadRequest(str(e))

@admin_api_bp.post("/users/<int:user_id>/tier")
def set_tier(user_id: int):
    try:
        body = request.get_json(silent=True) or {}
        tier = (body.get("tier") or "").strip()
        if not tier:
            return BadRequest("Missing 'tier'")
        data = svc.set_tier(user_id, tier)
        return ok(data)
    except Exception as e:
        raise BadRequest(str(e))
