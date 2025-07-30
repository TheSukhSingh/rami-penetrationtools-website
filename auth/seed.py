from .models import db, Role

for name, desc in [
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
]:
    if not Role.query.filter_by(name=name).first():
        db.session.add(Role(name=name, description=desc))
db.session.commit()
