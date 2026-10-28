from app.extensions import db
from app.models.auth import Permission, Role, DEFAULT_PERMISSIONS, DEFAULT_ROLES


def ensure_global_permissions():
    """Idempotently make sure every permission code in DEFAULT_PERMISSIONS exists as a row."""
    existing = {p.code for p in Permission.query.all()}
    for code in DEFAULT_PERMISSIONS:
        if code not in existing:
            db.session.add(Permission(code=code, description=code.replace(".", " ").replace("_", " ")))
    db.session.commit()


def ensure_system_roles(school):
    """
    Create (or SYNC) the standard system roles for a school. Every call
    re-applies the current DEFAULT_ROLES permission set onto each role,
    even ones that already existed, this used to only happen at
    creation time, which meant a permission fix made to the codebase
    later never actually reached an already-seeded database. Found as a
    real, repeatedly-hit bug: every mid-conversation permission fix in
    this project required a full dev.db wipe to actually take effect,
    which isn't realistic to expect from someone just running the app.
    Safe to call every time the app starts.
    """
    ensure_global_permissions()
    all_permissions = {p.code: p for p in Permission.query.all()}

    roles_by_name = {}
    for name, spec in DEFAULT_ROLES.items():
        if name == "super_admin":
            continue  # platform-level, not per-school

        role = Role.query.filter_by(school_id=school.id, name=name).first()
        if not role:
            role = Role(school_id=school.id, name=name, is_system=True)
            db.session.add(role)

        if spec["permissions"] == "*":
            role.permissions = list(all_permissions.values())
        else:
            role.permissions = [all_permissions[c] for c in spec["permissions"] if c in all_permissions]

        roles_by_name[name] = role

    db.session.commit()
    return roles_by_name


def ensure_super_admin_role():
    """Platform-level role, school_id = NULL. Idempotent, and re-syncs
    permissions on every call for the same reason as ensure_system_roles."""
    ensure_global_permissions()
    all_permissions = {p.code: p for p in Permission.query.all()}
    spec = DEFAULT_ROLES["super_admin"]
    role = Role.query.filter_by(school_id=None, name="super_admin").first()
    if not role:
        role = Role(school_id=None, name="super_admin", is_system=True)
        db.session.add(role)
    role.permissions = [all_permissions[c] for c in spec["permissions"] if c in all_permissions]
    db.session.commit()
    return role
