from flask import Blueprint

tools_bp = Blueprint(
    'tools',
    __name__,
    template_folder='templates',    
    static_folder='static',         
    static_url_path='/tools/static' 
)

from . import routes 