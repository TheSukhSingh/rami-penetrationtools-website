# auth/seed.py
from .models import db, Role
from app import create_app    # ← import your app-factory

ROLE_DEFINITIONS = [
    # Admin Panel Access Roles
    ('admin_view',    'Can view admin panel'),
    ('admin_modify',  'Can create/edit admin resources'),
    ('admin_delete',  'Can delete admin resources'),

    # User - Regular
    ('user',          'Regular user'),

    # Blog Roles
    ('blog_creator',  'Can create blog posts'),
    ('blog_editor',   'Can edit any blog post'),
    ('blog_deletor',  'Can delete blog posts'),
]

def seed_roles():
    for name, desc in ROLE_DEFINITIONS:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=desc))
    db.session.commit()
    print("✅ Roles seeded.")

if __name__ == '__main__':
    app = create_app()                  
    with app.app_context():             
        seed_roles()
