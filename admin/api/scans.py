# # admin/api/scans.py
# from datetime import datetime
# from flask import request
# from admin.api import admin_api_bp
# from admin.api.common import ok, parse_pagination, parse_sort
# # from admin.permissions import require_scopes

# from admin.services.scan_service import ScanService

# svc = ScanService()

# @admin_api_bp.get("/scans/summary")
# # @require_scopes("admin.scans.read")
# def scans_summary():
#     period = (request.args.get("range") or request.args.get("period") or "7d").lower()
#     data = svc.summary(period)
#     return ok(data)

# @admin_api_bp.get("/scans")
# # @require_scopes("admin.scans.read")
# def list_scans():
#     page, per_page = parse_pagination()
#     # allowed sort fields: scanned_at|created_at, tool, status, duration, user
#     sort_field, is_desc = parse_sort({"scanned_at", "created_at", "tool", "status", "duration", "user"}, default="-scanned_at")

#     q      = request.args.get("q") or None
#     tool   = request.args.get("tool") or None
#     status = request.args.get("status") or None
#     user   = request.args.get("user") or None

#     # optional explicit date filter (ISO8601). If absent, the FE should rely on the global period/summary.
#     start_s = request.args.get("from") or request.args.get("start")
#     end_s   = request.args.get("to")   or request.args.get("end")
#     start = datetime.fromisoformat(start_s) if start_s else None
#     end   = datetime.fromisoformat(end_s)   if end_s else None

#     items, total = svc.list_scans(
#         page=page, per_page=per_page,
#         q=q, tool=tool, status=status, user=user,
#         start=start, end=end,
#         sort_field=sort_field, is_desc=is_desc,
#     )
#     return ok(items, meta={"page": page, "per_page": per_page, "total": total, "q": q, "tool": tool, "status": status, "user": user})

# @admin_api_bp.get("/scans/<int:scan_id>")
# # @require_scopes("admin.scans.read")
# def scan_detail(scan_id: int):
#     data = svc.scan_detail(scan_id)
#     return ok(data)




# admin/api/scans.py
from datetime import datetime
from flask import request
from admin.api import admin_api_bp
from admin.api.common import ok, parse_pagination, parse_sort
# from admin.permissions import require_scopes
from admin.services.scan_service import ScanService

svc = ScanService()

@admin_api_bp.get("/scans/summary")
# @require_scopes("admin.scans.read")
def scans_summary():
    print('scan summary 1')
    period = (request.args.get("range") or "7d").lower()
    print('scan summary 2')
    active_window = int(request.args.get("active_window", "30"))  # minutes
    print('scan summary 3')
    data = svc.summary(period, active_window_minutes=active_window)
    print('scan summary 4')
    return ok(data)

@admin_api_bp.get("/scans")
# @require_scopes("admin.scans.read")
def list_scans():
    print('list scans 1')

    page, per_page = parse_pagination()
    print('list scans 1')
    sort_field, is_desc = parse_sort({"scanned_at","created_at","tool","status","duration","user"}, default="-scanned_at")

    q      = request.args.get("q") or None
    tool   = request.args.get("tool") or None
    status = request.args.get("status") or None
    user   = request.args.get("user") or None

    print('list scans 1')
    start_s = request.args.get("from") or request.args.get("start")
    end_s   = request.args.get("to")   or request.args.get("end")
    start = datetime.fromisoformat(start_s) if start_s else None
    end   = datetime.fromisoformat(end_s)   if end_s else None

    print('list scans 1')
    items, total = svc.list_scans(
        page=page, per_page=per_page, q=q, tool=tool, status=status, user=user,
        start=start, end=end, sort_field=sort_field, is_desc=is_desc,
    )
    print('list scans 1')
    return ok(items, meta={"page": page, "per_page": per_page, "total": total})
    
@admin_api_bp.get("/scans/<int:scan_id>")
# @require_scopes("admin.scans.read")
def scan_detail(scan_id: int):
    data = svc.scan_detail(scan_id)
    return ok(data)
