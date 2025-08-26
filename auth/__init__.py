from flask import Blueprint

auth_bp = Blueprint(
    'auth',
    __name__,
    url_prefix="/auth",
    template_folder='templates',
    static_folder='static',
    static_url_path='/auth/static'
)
 
from . import oauth_routes, local_routes
