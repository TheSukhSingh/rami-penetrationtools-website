from flask import render_template
from . import admin_bp

@admin_bp.route('/', methods=['GET'])
def tools_index():
    return render_template('admin/admin.html')