from datetime import datetime
from flask import render_template, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from tools.models import ToolScanHistory, db
from . import tools_bp
from .alltools import dnsx, gau, github_subdomains, gospider, hakrawler, httpx, katana, linkfinder, naabu, subfinder

@tools_bp.route('/', methods=['GET'])
def tools_index():
    return render_template('tools/tools.html')

@tools_bp.route('/api/scan', methods=['POST'])
@jwt_required(optional=True)
def api_scan():
    user_id = get_jwt_identity()
    # if not user_id:
    #     return jsonify({
    #         'status': 'error',
    #         'message': 'Login to do your scan'
    #     }), 401
    
    tool    = request.form.get('tool')
    cmd     = request.form.get('cmd')  
    
    options = {}
    for key, vals in request.form.lists():
        if key in ('tool', 'cmd'):
            continue
        options[key] = vals if len(vals) > 1 else vals[0]

    # handle uploaded .txt file, if any
    file_field = f"{tool}-file"
    if file_field in request.files:
        uploaded = request.files[file_field]
        if uploaded.filename:
            from werkzeug.utils import secure_filename
            import os
            from flask import current_app
            # choose your upload folder, e.g. in Flask config
            upload_dir = current_app.config.get('UPLOAD_FOLDER', '/tmp')
            os.makedirs(upload_dir, exist_ok=True)
            filename = secure_filename(uploaded.filename)
            filepath = os.path.join(upload_dir, filename)
            uploaded.save(filepath)
            options[file_field] = filepath

    try:
        if tool == 'dnsx':                result = dnsx.run_scan(options)
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
        success = False

    
    if success:
        result.setdefault('status', 'success')
        result.setdefault('output', '')

    # 7) Persist the scan record
    scan = ToolScanHistory(
        user_id           = user_id,
        tool_name         = tool,
        parameters        = options,
        command           = cmd,
        raw_output        = (result.get('output') or result.get('message')),
        scanned_at        = datetime.utcnow(),
        scan_success_state= success
    )
    db.session.add(scan)
    db.session.commit()

    return jsonify(result)


# @tools_bp.route('/api/history', methods=['GET'])
# @jwt_required()
# def get_scan_history():
#     """
#     Return the most recent 25 scans for the current user and (optional) tool.
#     Query param: ?tool=<tool_name>
#     """
#     user_id = int(get_jwt_identity())
#     tool = request.args.get('tool')

#     q = ToolScanHistory.query.filter_by(user_id=user_id)
#     if tool:
#         q = q.filter_by(tool_name=tool)
#     records = q.order_by(ToolScanHistory.scanned_at.desc()).limit(25).all()

#     history = [{
#         'id':      r.id,
#         'tool':    r.tool_name,
#         'command': r.command,
#         'output':  r.raw_output,  # truncate for payload
#         'when':    r.scanned_at.isoformat()
#     } for r in records]

#     return jsonify(status='ok', history=history)