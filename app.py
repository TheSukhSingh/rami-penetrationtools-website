import os
from flask import Flask, render_template, request
from dotenv import load_dotenv
from datetime import timedelta
from flask_jwt_extended import JWTManager
from flask_wtf import CSRFProtect

from auth import auth_bp
from tools import tools_bp
from admin import admin_bp
from admin.api import admin_api_bp
import secrets
from extensions import db, bcrypt, migrate, limiter

from auth.utils import login_required, init_mail, init_jwt_manager

load_dotenv()

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
        JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5),
        JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7),

        TURNSTILE_SITE_KEY=os.getenv('TURNSTILE_SITE_KEY', ''),    
        TURNSTILE_SECRET_KEY=os.getenv('TURNSTILE_SECRET_KEY', ''),

        RATELIMIT_HEADERS_ENABLED=True,
    )
    # ───────── COOKIE SETTINGS ─────────
    app.config.update({
        "JWT_TOKEN_LOCATION": ["cookies"],            # read/write JWTs from cookies
        "JWT_COOKIE_SECURE": True,                    # only send over HTTPS
        "JWT_COOKIE_SAMESITE": "Lax",                 # CSRF protection level
        "JWT_COOKIE_CSRF_PROTECT": True,              # enable double-submit CSRF
        "JWT_ACCESS_COOKIE_PATH": "/",                # where access cookie is sent
        "JWT_REFRESH_COOKIE_PATH": "/auth/refresh",   # refresh endpoint path
        "WTF_CSRF_TIME_LIMIT":3600,
        "WTF_CSRF_METHODS":['POST','PUT','PATCH','DELETE'],
    })
    # app.config['UPLOAD_FOLDER'] = '/tmp/recon_uploads'
    app.config['UPLOAD_INPUT_FOLDER']  = '/tmp/recon_uploads/user_uploads'
    app.config['UPLOAD_OUTPUT_FOLDER'] = '/tmp/recon_uploads/results'

    os.makedirs(app.config['UPLOAD_INPUT_FOLDER'],  exist_ok=True)
    os.makedirs(app.config['UPLOAD_OUTPUT_FOLDER'], exist_ok=True)


    csrf = CSRFProtect(app)  
    # csrf.exempt(auth_bp)
    csrf.exempt(tools_bp)

    limiter.init_app(app)
    os.makedirs(app.instance_path, exist_ok=True)
    jwt = JWTManager(app)
    
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)


    init_mail(app)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(tools_bp, url_prefix='/tools')

    init_jwt_manager(app, jwt)

    # ── Security headers ─────────────────────────────────────────
    @app.after_request
    def set_security_headers(resp):
        # Clickjacking & MIME sniffing
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        resp.headers['Permissions-Policy'] = "camera=(), microphone=(), geolocation=()"

        # HSTS only when HTTPS (or if you set FORCE_HTTPS=True in config)
        if request.is_secure or app.config.get('FORCE_HTTPS'):
            resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        # CSP (safe defaults for current setup)
        # Note: allows inline handlers for now ('unsafe-inline'); tighten later.
        resp.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com https://challenges.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "frame-src https://accounts.google.com https://challenges.cloudflare.com;"
        )
        return resp
    
    @app.route('/')
    def index():
        return render_template('landing_page.html')
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
