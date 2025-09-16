from datetime import datetime, timezone
from flask import render_template, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from tools.models import (
    ToolCategory,
    ToolScanHistory, 
    ScanDiagnostics, 
    ScanStatus, 
    ErrorReason, 
    Tool,
    ToolCategoryLink
)
from extensions import db
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

