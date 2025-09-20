import os
from flask import Flask, g, render_template, request
from dotenv import load_dotenv
from datetime import timedelta
from flask_jwt_extended import JWTManager
from flask import current_app
from auth import auth_bp
from tools import tools_bp
from admin import admin_bp
from blog import blog_bp
from admin.api import admin_api_bp
from account import account_bp
import secrets
from extensions import db, bcrypt, migrate, limiter, csrf
from user_dashboard import user_dashboard_bp
import enum
from auth.utils import init_mail, init_jwt_manager
from flask.json.provider import DefaultJSONProvider

load_dotenv()

class EnumJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, enum.Enum):
            return o.value
        return super().default(o)

def create_app():
    app = Flask(
        __name__, 
        instance_relative_config=True, 
        template_folder='templates', 
        static_folder='static'
    )

    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev'),
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', os.getenv('SECRET_KEY', 'dev')),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            'DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER'),
        JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1),
        JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7),

        TURNSTILE_SITE_KEY=os.getenv('TURNSTILE_SITE_KEY', ''),    
        TURNSTILE_SECRET_KEY=os.getenv('TURNSTILE_SECRET_KEY', ''),

        RATELIMIT_HEADERS_ENABLED=True,

        FEATURE_BILLING=os.getenv("FEATURE_BILLING", "0") == "1",
        FEATURE_HELP=os.getenv("FEATURE_HELP", "0") == "1",
    )
    # ───────── COOKIE SETTINGS ─────────
    app.config.update({
        "JWT_TOKEN_LOCATION": ["cookies"],            # read/write JWTs from cookies
        "JWT_COOKIE_SECURE": True,                    # only send over HTTPS
        "JWT_COOKIE_SAMESITE": "Lax",                 # CSRF protection level
        "JWT_COOKIE_CSRF_PROTECT": True,              # enable double-submit CSRF
        "JWT_ACCESS_COOKIE_PATH": "/",                # where access cookie is sent
        "JWT_REFRESH_COOKIE_PATH": "/auth",
        "JWT_ACCESS_CSRF_COOKIE_PATH": "/",
        "JWT_REFRESH_CSRF_COOKIE_PATH": "/",      
        "WTF_CSRF_TIME_LIMIT":3600,
        "WTF_CSRF_METHODS":['POST','PUT','PATCH','DELETE'],
        "WTF_CSRF_HEADERS": ["X-CSRFToken", "X-CSRF-Token"],
    })
    from tempfile import gettempdir

    # Base directory for uploads; override with RECON_ROOT if you want a custom path
    RECON_ROOT = os.getenv("RECON_ROOT", os.path.join(gettempdir(), "recon_uploads"))

    app.config['UPLOAD_INPUT_FOLDER']  = os.path.join(RECON_ROOT, "user_uploads")
    app.config['UPLOAD_OUTPUT_FOLDER'] = os.path.join(RECON_ROOT, "results")
    os.makedirs(app.config['UPLOAD_INPUT_FOLDER'],  exist_ok=True)
    os.makedirs(app.config['UPLOAD_OUTPUT_FOLDER'], exist_ok=True)


    # app.config.update({
            # --- HIBP k-anonymity password check ---
    # "HIBP_ENABLE": True,                 # master switch
    # "HIBP_BLOCK_COUNT": 100,             # block if seen ≥ this many times
    # "HIBP_ADMIN_BLOCK_ANY": True,        # admins blocked if seen ≥ 1
    # "HIBP_CACHE_TTL_SECONDS": 7*24*3600, # per-prefix cache TTL (7d)
    # "HIBP_API_TIMEOUT": 2.0,             # seconds
    # "HIBP_USER_AGENT": "hibp-check/1.0 (contact@example.com)",

    # Optional: point to a dir containing per-prefix files like 'ABCDE.txt'
    # each file line: SUFFIX:COUNT  (SUFFIX is 35 uppercase hex chars)
    # "HIBP_OFFLINE_PREFIX_DIR": None,     # e.g. "/var/hibp_prefix"
    # })
    
    app.config.update({
        "HIBP_ENABLE": True,               # master switch
        "HIBP_BLOCK_ANY": True,            # block if seen in HIBP at all (>0)
        "HIBP_API_TIMEOUT": 2.0,           # seconds
        "HIBP_USER_AGENT": "hibp-check/1.0 (you@example.com)",
    })

    app.config.update({
        "TRUSTED_DEVICE_COOKIE_NAME": "tdid",
        "TRUSTED_DEVICE_DAYS": 30,
    })

    app.config.setdefault('CELERY_BROKER_URL', os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'))
    app.config.setdefault('CELERY_RESULT_BACKEND', os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1'))
    app.config.setdefault('CELERY_TIMEZONE', os.getenv('CELERY_TIMEZONE', 'UTC'))
    app.config.setdefault('CELERY_TASK_ROUTES', {
        'tools.tasks.*': {'queue': 'tools_default'}
    })

    os.makedirs(app.config['UPLOAD_INPUT_FOLDER'],  exist_ok=True)
    os.makedirs(app.config['UPLOAD_OUTPUT_FOLDER'], exist_ok=True)

    csrf.init_app(app)  

    limiter.init_app(app)

    limiter.default_limits = ["200 per day", "50 per hour"]

    os.makedirs(app.instance_path, exist_ok=True)
    jwt = JWTManager(app)
    
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    app.json_provider_class = EnumJSONProvider
    app.json = app.json_provider_class(app)

    
    init_mail(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(user_dashboard_bp)

    init_jwt_manager(app, jwt)

    @app.context_processor
    def inject_turnstile():
        # expose a plain variable TURNSTILE_SITE_KEY to all templates
        return {
            "TURNSTILE_SITE_KEY": current_app.config.get("TURNSTILE_SITE_KEY", "")
        }
    
    @app.before_request
    def _set_csp_nonce():
        # one fresh, unpredictable token per response
        g.csp_nonce = secrets.token_urlsafe(16)

    # ── Security headers ─────────────────────────────────────────
    @app.after_request
    def set_security_headers(resp):
        nonce = getattr(g, "csp_nonce", None)
        if not nonce:
            # fall back so errors can still render
            nonce = secrets.token_urlsafe(16)
        # Clickjacking & MIME sniffing
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        resp.headers['Permissions-Policy'] = "camera=(), microphone=(), geolocation=()"

        # HSTS only when HTTPS (or if you set FORCE_HTTPS=True in config)
        if request.is_secure or app.config.get('FORCE_HTTPS'):
            resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        resp.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://accounts.google.com https://apis.google.com https://challenges.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; "
            "img-src 'self' data: https://*.googleusercontent.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://accounts.google.com https://apis.google.com; "
            "frame-ancestors 'none'; "
            "frame-src https://accounts.google.com https://challenges.cloudflare.com;"
        )
        return resp
    @app.context_processor
    def inject_config():
        return {"config": current_app.config}

    @app.route('/')
    def index():
        return render_template('landing_page.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
