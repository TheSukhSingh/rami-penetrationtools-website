from datetime import datetime
from flask import render_template, jsonify, request, send_file, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import user_dashboard_bp
from ..services.dashboard_service import (
    get_overview, list_scans, get_scan_detail, get_analytics, get_download_path
)

@user_dashboard_bp.get("/")
@jwt_required(optional=True)  # HTML shell; JS will call APIs
def page():
    return render_template("user/dashboard.html")

def _parse_int(v, default):
    try:
        return int(v)
    except Exception:
        return default

def _parse_date(v):
    if not v: return None
    try:
        # Accept YYYY-MM-DD or ISO8601
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None

@user_dashboard_bp.get("/api/dashboard/overview")
@jwt_required()
def api_overview():
    user_id = get_jwt_identity()
    data = get_overview(user_id=user_id, days=_parse_int(request.args.get("days", 30), 30))
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/scans")
@jwt_required()
def api_scans():
    user_id = get_jwt_identity()
    data = list_scans(
        user_id=user_id,
        tool=request.args.get("tool"),
        status=request.args.get("status"),
        q=request.args.get("search"),
        page=_parse_int(request.args.get("page", 1), 1),
        per_page=_parse_int(request.args.get("per_page", 20), 20),
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
    )
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/scans/<int:scan_id>")
@jwt_required()
def api_scan_detail(scan_id: int):
    user_id = get_jwt_identity()
    data = get_scan_detail(user_id=user_id, scan_id=scan_id)
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/analytics")
@jwt_required()
def api_analytics():
    user_id = get_jwt_identity()
    data = get_analytics(
        user_id=user_id,
        days=_parse_int(request.args.get("range", "30d").replace("d",""), 30),
        tool=request.args.get("tool"),
    )
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/download/<int:scan_id>")
@jwt_required()
def api_download(scan_id: int):
    user_id = get_jwt_identity()
    path = get_download_path(user_id=user_id, scan_id=scan_id)
    if not path:
        abort(404)
    return send_file(path, as_attachment=True)
