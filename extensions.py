from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt     import Bcrypt
from flask_migrate    import Migrate

db      = SQLAlchemy()
bcrypt  = Bcrypt()
migrate = Migrate()


csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
