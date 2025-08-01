from flask import render_template, request, jsonify
from . import tools_bp
from .alltools import dnsx, gau, github_subdomains, gospider, hakrawler, httpx, katana, linkfinder, naabu, subfinder

@tools_bp.route('/', methods=['GET'])
def tools_index():
    return render_template('tools/tools.html')

@tools_bp.route('/api/scan', methods=['POST'])
def api_scan():
    # payload = request.get_json() or {}
    # tool    = payload.get('tool')
    # options = payload.get('options', {})

    # for multipart/form-data: get tool and options from form
    tool    = request.form.get('tool')
    # flatten form fields into an options dict
    options = {}
    for key, vals in request.form.lists():
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

    if tool == 'dnsx':
        result = dnsx.run_scan(options)

    elif tool == 'gau':
        result = gau.run_scan(options)

    elif tool == 'github-subdomains':
        result = github_subdomains.run_scan(options)

    elif tool == 'gospider':
        result = gospider.run_scan(options)

    elif tool == 'hakrawler':
        result = hakrawler.run_scan(options)

    elif tool == 'httpx':
        result = httpx.run_scan(options)

    elif tool == 'katana':
        result = katana.run_scan(options)

    elif tool == 'linkfinder':
        result = linkfinder.run_scan(options)

    elif tool == 'naabu':
        result = naabu.run_scan(options)

    elif tool == 'subfinder':
        result = subfinder.run_scan(options)

    else:
        return jsonify({
            'status': 'error',
            'message': f'Unknown tool: {tool}'
        }), 400

    return jsonify(result)
