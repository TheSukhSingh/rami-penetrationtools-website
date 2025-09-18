from datetime import datetime, timezone
from flask import render_template, request, jsonify, abort
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_
from tools.models import (
    ToolCategory,
    ToolScanHistory, 
    ScanDiagnostics, 
    ScanStatus, 
    ErrorReason, 
    Tool,
    ToolCategoryLink,
    WorkflowDefinition
)
from extensions import db, limiter
from . import tools_bp
from .alltools import (
    dnsx, 
    gau,
    github_subdomains, 
    gospider, 
    hakrawler, 
    httpx, 
    katana, 
    linkfinder, 
    naabu, 
    subfinder
)
import time
utcnow = lambda: datetime.now(timezone.utc)

@tools_bp.get("/")
def tools_index():
    return render_template("tools/index.html")

@tools_bp.get("/api/tools")
def api_tools():
    # Fetch enabled categories with their enabled tools, ordered
    cats = (
        db.session.query(ToolCategory)
        .filter(ToolCategory.enabled.is_(True))
        .order_by(ToolCategory.sort_order.asc(), ToolCategory.name.asc())
        .all()
    )

    payload = {"categories": {}}
    for c in cats:
        rows = []
        # sort by link.sort_order then tool.name
        links = sorted(c.tool_links, key=lambda l: ((l.sort_order or 100), (l.tool.name or "")))
        for link in links:
            t = link.tool
            if not t or not t.enabled:
                continue
            meta = t.meta_info or {}
            rows.append({
                "slug": t.slug,
                "name": t.name,
                "desc": meta.get("desc") or meta.get("description") or "",
                "type": meta.get("type") or meta.get("tool_type") or "",
                "time": meta.get("time") or meta.get("est_runtime") or "",
            })
        payload["categories"][c.name] = rows

    return jsonify(payload)

@tools_bp.route('/api/scan', methods=['POST'])
@jwt_required()
def api_scan():
    user_id = get_jwt_identity()    
    tool    = request.form.get('tool')
    cmd     = request.form.get('cmd')  
    
    base_name = ''
    filename  = ''

    options = {}
    for key, vals in request.form.lists():
        if key in ('tool', 'cmd'):
            continue
        options[key] = vals if len(vals) > 1 else vals[0]

    file_field = f"{tool}-file"

    if file_field in request.files:
        uploaded = request.files[file_field]
        if uploaded.filename:
            from werkzeug.utils import secure_filename
            import os
            from flask import current_app
            base = current_app.config['UPLOAD_INPUT_FOLDER']
            user_folder = os.path.join(base, str(user_id))
            os.makedirs(user_folder, exist_ok=True)
            base_name = secure_filename(uploaded.filename)
            timestamp = utcnow().strftime('%Y%m%d%H%M%S%f')
            filename = f"{timestamp}_{base_name}"
            filepath = os.path.join(user_folder, filename)
            uploaded.save(filepath)
            options['input_method'] = 'file'
            options['file_path'] = filepath

    start_req = time.time()
    try:
        if   tool == 'dnsx':              result = dnsx.run_scan(options)
        elif tool == 'gau':               result = gau.run_scan(options)
        elif tool == 'github-subdomains': result = github_subdomains.run_scan(options)
        elif tool == 'gospider':          result = gospider.run_scan(options)
        elif tool == 'hakrawler':         result = hakrawler.run_scan(options)
        elif tool == 'httpx':             result = httpx.run_scan(options)
        elif tool == 'katana':            result = katana.run_scan(options)
        elif tool == 'linkfinder':        result = linkfinder.run_scan(options)
        elif tool == 'naabu':             result = naabu.run_scan(options)
        elif tool == 'subfinder':         result = subfinder.run_scan(options)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown tool: {tool}'
            }), 400
        success = True
    except Exception as e:
        result = {
            'status': 'error',
            'message': str(e),
            'output': ''
        }
        success = (result.get('status') != 'error')

    if success:
        result.setdefault('status', 'success')
        result.setdefault('output', '')

    scan = ToolScanHistory(
        user_id            = user_id,
        tool               = tool,
        parameters         = options,
        command            = cmd,
        raw_output         = (result.get('output') or result.get('message')),
        scan_success_state = success,
        filename_by_user   = base_name,
        filename_by_be     = filename
    )
    db.session.add(scan)
    db.session.flush()

    er_val = result.get('error_reason')
    er_enum = ErrorReason[er_val] if er_val in ErrorReason.__members__ else None

    diag = ScanDiagnostics(
        scan_id        = scan.id,
        status         = ScanStatus.SUCCESS   if success else ScanStatus.FAILURE,
        total_domain_count   = result.get('total_domain_count', None),
        valid_domain_count   = result.get('valid_domain_count', None),
        invalid_domain_count   = result.get('invalid_domain_count', None),
        duplicate_domain_count   = result.get('duplicate_domain_count', None),
        file_size_b    = result.get('file_size_b'),
        execution_ms   = result.get('execution_ms', int((time.time() - start_req)*1000)),
        # error_reason   = (ErrorReason[result.get('error_reason')]),
        # error_reason   = ErrorReason[error_reason_value]
        #                  if error_reason_value in ErrorReason.__members__
        #                  else None,
        error_reason   = er_enum,
        error_detail   = result.get('error_detail'),
        value_entered   = result.get('value_entered')

    )
    db.session.add(diag)
    db.session.commit()

    return jsonify(result)

# ─────────────────────────────────────────────────────────
# Workflows CRUD (definitions / presets)
# ─────────────────────────────────────────────────────────

def _serialize_workflow(wf: WorkflowDefinition):
    return {
        "id": wf.id,
        "pretty_id": getattr(wf, "pretty_id", None),
        "owner_id": wf.owner_id,
        "title": wf.title,
        "description": wf.description,
        "version": wf.version,
        "is_shared": wf.is_shared,
        "is_archived": wf.is_archived,
        "forked_from_id": wf.forked_from_id,
        "graph": wf.graph_json or {},
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }

def _require_owner(wf: WorkflowDefinition, user_id: int):
    # v1: only the owner may modify/delete. (Admin override can be added later.)
    if (wf.owner_id is not None) and (wf.owner_id != user_id):
        abort(403, description="Not allowed")

def _validate_graph(graph: dict):
    if not isinstance(graph, dict):
        abort(400, description="graph must be an object")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        abort(400, description="graph must contain arrays: nodes[], edges[]")
    # v1: minimal shape checks
    for n in nodes:
        if not isinstance(n, dict) or "tool_slug" not in n:
            abort(400, description="each node must include tool_slug")
    for e in edges:
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            abort(400, description="each edge must include from/to")

@tools_bp.post("/api/workflows")
@jwt_required()
@limiter.limit("15/minute")
def create_workflow():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    graph = data.get("graph") or {}
    is_shared = bool(data.get("is_shared") or False)

    if not title:
        return jsonify({"error": "title is required"}), 400
    _validate_graph(graph)

    wf = WorkflowDefinition(
        owner_id=user_id,
        title=title,
        description=description or None,
        version=1,
        is_shared=is_shared,
        is_archived=False,
        graph_json=graph,
    )
    db.session.add(wf)
    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(wf)}), 201

@tools_bp.get("/api/workflows")
@jwt_required()
def list_workflows():
    user_id = get_jwt_identity()
    q = (request.args.get("q") or "").strip()
    mine = request.args.get("mine", "true").lower() in ("1", "true", "yes")
    shared = request.args.get("shared", "false").lower() in ("1", "true", "yes")
    include_archived = request.args.get("include_archived", "false").lower() in ("1", "true", "yes")

    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)

    qry = db.session.query(WorkflowDefinition)

    filters = []
    if mine:
        filters.append(WorkflowDefinition.owner_id == user_id)
    if shared:
        filters.append(WorkflowDefinition.is_shared.is_(True))

    if filters:
        qry = qry.filter(or_(*filters))
    else:
        # default: mine=true
        qry = qry.filter(WorkflowDefinition.owner_id == user_id)

    if not include_archived:
        qry = qry.filter(WorkflowDefinition.is_archived.is_(False))

    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(WorkflowDefinition.title.ilike(like),
                             WorkflowDefinition.description.ilike(like)))

    qry = qry.order_by(WorkflowDefinition.updated_at.desc(), WorkflowDefinition.id.desc())
    page_obj = qry.paginate(page=page, per_page=per_page, error_out=False)

    items = [_serialize_workflow(w) for w in page_obj.items]
    return jsonify({
        "items": items,
        "page": page_obj.page,
        "per_page": page_obj.per_page,
        "total": page_obj.total,
        "pages": page_obj.pages
    })

@tools_bp.get("/api/workflows/<int:wf_id>")
@jwt_required()
def get_workflow(wf_id: int):
    user_id = get_jwt_identity()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    # view permission: owner or shared
    if (wf.owner_id != user_id) and not wf.is_shared:
        abort(403, description="Not allowed")
    return jsonify({"workflow": _serialize_workflow(wf)})

@tools_bp.put("/api/workflows/<int:wf_id>")
@jwt_required()
@limiter.limit("20/minute")
def update_workflow(wf_id: int):
    user_id = get_jwt_identity()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    _require_owner(wf, user_id)

    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        wf.title = title
    if "description" in data:
        wf.description = (data.get("description") or "").strip() or None
    if "is_shared" in data:
        wf.is_shared = bool(data.get("is_shared"))
    if "graph" in data:
        graph = data.get("graph") or {}
        _validate_graph(graph)
        wf.graph_json = graph
        # optional: bump version when graph changes
        wf.version = (wf.version or 1) + 1

    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(wf)})

@tools_bp.post("/api/workflows/<int:wf_id>/clone")
@jwt_required()
@limiter.limit("10/minute")
def clone_workflow(wf_id: int):
    user_id = get_jwt_identity()
    src = db.session.get(WorkflowDefinition, wf_id)
    if not src:
        return jsonify({"error": "not found"}), 404
    # view permission to clone: owner or shared
    if (src.owner_id != user_id) and not src.is_shared:
        abort(403, description="Not allowed")

    data = request.get_json(silent=True) or {}
    new_title = (data.get("title") or f"{src.title} (Copy)").strip()

    clone = WorkflowDefinition(
        owner_id=user_id,
        title=new_title,
        description=src.description,
        version=1,
        is_shared=False,
        is_archived=False,
        forked_from_id=src.id,
        graph_json=src.graph_json or {}
    )
    db.session.add(clone)
    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(clone)}), 201

@tools_bp.delete("/api/workflows/<int:wf_id>")
@jwt_required()
@limiter.limit("10/minute")
def delete_workflow(wf_id: int):
    user_id = get_jwt_identity()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    _require_owner(wf, user_id)

    # soft-delete (archive)
    wf.is_archived = True
    db.session.commit()
    return ("", 204)
