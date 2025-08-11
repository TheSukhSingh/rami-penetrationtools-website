# from .models import db, Role
# from app import create_app  

# ROLE_DEFINITIONS = [
#     # Admin Panel Access Roles
#     ('admin_view',    'Can view admin panel'),
#     ('admin_modify',  'Can create/edit admin resources'),
#     ('admin_delete',  'Can delete admin resources'),

#     # User - Regular
#     ('user',          'Regular user'),

#     # Blog Roles
#     ('blog_creator',  'Can create blog posts'),
#     ('blog_editor',   'Can edit any blog post'),
#     ('blog_deletor',  'Can delete blog posts'),
# ]

# def seed_roles():
#     for name, desc in ROLE_DEFINITIONS:
#         if not Role.query.filter_by(name=name).first():
#             db.session.add(Role(name=name, description=desc))
#     db.session.commit()
#     print("✅ Roles seeded.")

# if __name__ == '__main__':
#     app = create_app()                  
#     with app.app_context():             
#         seed_roles()



from app import create_app
from extensions import db
from auth.models import Role  

ALL_SCOPES = {
    # Users
    "users.read", "users.write", "users.delete",
    # Scans
    "scans.read", "scans.delete",
    # Tools catalog/config
    "tools.read", "tools.write", "tools.delete",
    # Settings
    "settings.read", "settings.write",
    # Audit
    "audit.read",
}

ROLE_DEFINITIONS = {
    # Full control over admin + settings + tools + users
    "admin_owner": {
        "description": "Full admin access",
        "scopes": sorted(list(ALL_SCOPES)),
    },

    # Day-to-day operations (manage users, read scans, tweak tools), but no delete role
    "admin_ops": {
        "description": "Operate admin functions (no deletes, limited risk)",
        "scopes": sorted([
            "users.read", "users.write",
            "scans.read",
            "tools.read", "tools.write",
            "audit.read",
            "settings.read",
        ]),
    },

    "admin_ops_delete": {
        "description": "Operational admin with delete powers",
        "scopes": sorted([
            "users.read", "users.write", "users.delete",
            "scans.read", "scans.delete",
            "tools.read", "tools.write", "tools.delete",
            "settings.read",
            "audit.read",
        ]),
    },

    # Support staff: read-only visibility
    "admin_support": {
        "description": "Read-only admin visibility",
        "scopes": sorted([
            "users.read",
            "scans.read",
            "tools.read",
            "audit.read",
            "settings.read",
        ]),
    },

    # Regular user: no admin scopes
    "user": {
        "description": "Regular user",
        "scopes": [],
    },
}

def seed_roles():
    created, updated = 0, 0
    for name, payload in ROLE_DEFINITIONS.items():
        role = Role.query.filter_by(name=name).first()
        if role is None:
            db.session.add(Role(
                name=name,
                description=payload["description"],
                scopes=payload["scopes"],
            ))
            created += 1
        else:
            dirty = False
            if role.description != payload["description"]:
                role.description = payload["description"]; dirty = True
            new_scopes = sorted(set(payload["scopes"]))
            cur_scopes = sorted(set(role.scopes or []))
            if cur_scopes != new_scopes:
                role.scopes = new_scopes; dirty = True
            if dirty: updated += 1
    db.session.commit()
    print(f"✅ Roles seeded. Created: {created}, Updated: {updated}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_roles()