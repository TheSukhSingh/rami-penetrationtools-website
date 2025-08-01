import os
from flask import Flask, render_template
from flask_migrate      import Migrate
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from datetime import timedelta
from flask_jwt_extended import JWTManager
from flask_wtf import CSRFProtect

# from admin import admin_bp
from auth import auth_bp
from auth.models import db, bcrypt
from auth.utils import login_required, init_mail, init_jwt_manager, init_mail
from tools import tools_bp

# load .env variables
load_dotenv()


# create Flask extensions (they'll be initialized in create_app)

migrate = Migrate()


# from extensions import limiter, csrf


def create_app():
    app = Flask(__name__, instance_relative_config=True, template_folder='templates', static_folder='static')
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # mail settings
        MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER'),
        JWT_SECRET_KEY =os.getenv('JWT_SECRET_KEY'),
        JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15),
        JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7),
    )
    app.config['UPLOAD_FOLDER'] = '/tmp/recon_uploads'

    csrf = CSRFProtect(app)  
    csrf.exempt(auth_bp)
    csrf.exempt(tools_bp)

    os.makedirs(app.instance_path, exist_ok=True)
    jwt = JWTManager(app)
    
    db.init_app(app)
    bcrypt.init_app(app)
    init_mail(app)
    migrate.init_app(app, db)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    # app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(tools_bp, url_prefix='/tools')

    init_jwt_manager(app, jwt)


    @app.route('/')
    def index():
        return render_template('landing_page.html')
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
