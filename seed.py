
from app import create_app
from extensions import db
from auth.models import Role  

ALL_SCOPES = {
    # Users
    "admin.users.read", "admin.users.write", "admin.users.delete",
    # Scans
    "admin.scans.read", "admin.scans.delete",
    # Tools catalog/config
    "admin.tools.read", "admin.tools.write", "admin.tools.delete",
    # Settings
    "admin.settings.read", "admin.settings.write",
    # Blog
    "blog.write", "blog.delete"
    # Audit
    "admin.audit.read",
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
            "admin.users.read", "admin.users.write",
            "admin.scans.read",
            "admin.tools.read", "admin.tools.write",
            "admin.audit.read",
            "admin.settings.read",
        ]),
    },

    "admin_ops_delete": {
        "description": "Operational admin with delete powers",
        "scopes": sorted([
            "admin.users.read", "admin.users.write", "admin.users.delete",
            "admin.scans.read", "admin.scans.delete",
            "admin.tools.read", "admin.tools.write", "admin.tools.delete",
            "admin.settings.read",
            "admin.audit.read",
        ]),
    },

    # Support staff: read-only visibility
    "admin_support": {
        "description": "Read-only admin visibility",
        "scopes": sorted([
            "admin.users.read",
            "admin.scans.read",
            "admin.tools.read",
            "admin.audit.read",
            "admin.settings.read",
        ]),
    },

    # Regular user: no admin scopes
    "user": {
        "description": "Regular user",
        "scopes": [],
    },

    # Blogger: 
    "blogger": {
        "description": "Blogger",
        "scopes": sorted([
            "blog.write",
            "blog.delete",
        ]),
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