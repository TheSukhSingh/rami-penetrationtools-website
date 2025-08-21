from flask import request
from admin.api import admin_api_bp
from admin.api.common import ok
from admin.permissions import require_scopes
from admin.services.overview_service import OverviewService

svc = OverviewService()

@admin_api_bp.get("/overview")
# @require_scopes("admin.overview.read") 
def get_overview():
    period = (request.args.get("range") or "7d").lower()
    data = svc.combined(period)
    return ok(data)
