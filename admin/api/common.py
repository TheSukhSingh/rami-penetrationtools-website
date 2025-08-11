from typing import Any, Dict, Iterable, Optional, Tuple
from flask import request, jsonify
from admin.errors import BadRequest, Unprocessable

def ok(data: Any = None, meta: Optional[Dict[str, Any]] = None, status: int = 200):
    return jsonify({"ok": True, "data": data, "meta": meta or {}}), status

def get_json(*, required: Iterable[str] = (), optional: Iterable[str] = ()):
    if not request.is_json:
        raise BadRequest("Expected JSON body")
    data = request.get_json(silent=True) or {}
    missing = [k for k in required if k not in data]
    if missing:
        raise Unprocessable("Missing required fields", details={"fields": missing})
    allowed = set(required) | set(optional)
    unknown = [k for k in data.keys() if k not in allowed]
    if unknown:
        # We don't block unknown by default, just surface it
        data["_unknown"] = unknown
    return data

def parse_pagination(default_per_page: int = 20, max_per_page: int = 100) -> Tuple[int, int]:
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=default_per_page, type=int)
    if page < 1:
        raise Unprocessable("page must be >= 1")
    per_page = max(1, min(per_page, max_per_page))
    return page, per_page

def parse_sort(allowed_fields: Iterable[str], default: str = "created_at") -> Tuple[str, bool]:
    """
    Returns (field, desc). Accepts ?sort=field or ?sort=-field for DESC.
    """
    sort = request.args.get("sort", default)
    desc = sort.startswith("-")
    field = sort[1:] if desc else sort
    if field not in set(allowed_fields):
        raise Unprocessable("Invalid sort field", details={"allowed": list(allowed_fields)})
    return field, desc

def request_context() -> Dict[str, Any]:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent")
    return {"ip": ip, "user_agent": ua}
