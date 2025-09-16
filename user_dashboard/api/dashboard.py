from flask import jsonify, render_template, request, send_file, abort
from flask_jwt_extended import jwt_required
from .. import user_dashboard_bp
from ..services.dashboard_service import (
    get_overview,
    list_scans,
    get_scan_detail,
    get_analytics,
    get_download_path,
)

@user_dashboard_bp.get("/")
@jwt_required(optional=True)  # allow page to render; JS will call APIs with auth
def page():
    return render_template("user/dashboard.html")

@user_dashboard_bp.get("/api/dashboard/overview")
@jwt_required()
def api_overview():
    data = get_overview()
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/scans")
@jwt_required()
def api_scans():
    data = list_scans(
        tool=request.args.get("tool"),
        status=request.args.get("status"),
        q=request.args.get("search"),
        page=int(request.args.get("page", 1)),
        per_page=int(request.args.get("per_page", 20)),
        date_from=request.args.get("from"),
        date_to=request.args.get("to"),
    )
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/scans/<int:scan_id>")
@jwt_required()
def api_scan_detail(scan_id: int):
    data = get_scan_detail(scan_id)
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/analytics")
@jwt_required()
def api_analytics():
    data = get_analytics(
        range=request.args.get("range", "30d"),
        tool=request.args.get("tool"),
    )
    return jsonify(data)

@user_dashboard_bp.get("/api/dashboard/download/<int:scan_id>")
@jwt_required()
def api_download(scan_id: int):
    path = get_download_path(scan_id)
    if not path:
        abort(404)
    return send_file(path, as_attachment=True)
