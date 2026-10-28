"""
Multi-tenancy + RBAC enforcement.

Rule (see models/base.py TenantMixin docstring, and spec section 89):
cross-school access must be impossible through normal application requests.
Every query for a school-owned model MUST go through scoped_query() or
manually filter by current_school_id(), never trust a school_id in the
request body/query string.
"""

from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models import User


def current_school_id():
    claims = get_jwt()
    return claims.get("school_id")


def current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(user_id)


def scoped_query(model):
    """Return a query for `model` pre-filtered to the caller's school."""
    school_id = current_school_id()
    if school_id is None:
        # Platform-level (super admin) caller with no school context -
        # calling code must handle this explicitly rather than silently
        # returning everything.
        raise PermissionError("No school context for this request")
    return model.query.filter_by(school_id=school_id)


def _check_must_change_password():
    """
    Enforce spec section 5's "Change Password" requirement for real: a user
    flagged must_change_password (set on creation / after an admin reset)
    is blocked from every endpoint except /api/auth/change-password and
    /api/auth/me until they change it. Returns a Flask response tuple to
    short-circuit with, or None if the caller is clear to proceed.
    """
    user = current_user()
    if user is not None and user.must_change_password:
        return jsonify({
            "error": "Password change required before continuing",
            "code": "PASSWORD_CHANGE_REQUIRED",
        }), 403
    return None


def jwt_required_scoped(fn):
    """Require a valid JWT AND that it carries a school_id (i.e. not a bare super-admin token)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if current_school_id() is None:
            return jsonify({"error": "This endpoint requires a school-scoped account"}), 403
        blocked = _check_must_change_password()
        if blocked:
            return blocked
        return fn(*args, **kwargs)

    return wrapper


def _log_denied(needed):
    from app.utils.security import log_security_event
    log_security_event("permission_denied", user_id=get_jwt_identity(), path=request.path, method=request.method, needed=needed)


def permission_required(code):
    """
    Require the caller's JWT-scoped user to hold a specific permission code
    (e.g. "students.create"). Wildcard ("*") roles, school_owner,
    school_administrator, pass every check.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            blocked = _check_must_change_password()
            if blocked:
                return blocked
            claims = get_jwt()
            perms = set(claims.get("permissions", []))
            if "*" not in perms and code not in perms:
                _log_denied(code)
                return jsonify({"error": f"Missing permission: {code}"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def has_role(name):
    """True if the caller holds the named role (read from their token)."""
    return name in set(get_jwt().get("roles", []))


def has_permission(code):
    """True if the caller's token carries `code` (or the "*" wildcard)."""
    perms = set(get_jwt().get("permissions", []))
    return "*" in perms or code in perms


def any_permission_required(*codes):
    """Like permission_required, but passes if the caller holds ANY of the codes."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            blocked = _check_must_change_password()
            if blocked:
                return blocked
            perms = set(get_jwt().get("permissions", []))
            if "*" not in perms and not any(c in perms for c in codes):
                _log_denied(" or ".join(codes))
                return jsonify({"error": f"Missing permission: {' or '.join(codes)}"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def class_master_class_ids():
    """Ids of the classes whose class master (head teacher) is the caller."""
    from app.models import SchoolClass

    staff_id = linked_staff_id()
    if not staff_id:
        return []
    rows = SchoolClass.query.filter_by(school_id=current_school_id(), class_master_staff_id=staff_id).all()
    return [c.id for c in rows]


def linked_student_id():
    """
    If the caller's account is linked to a Student record (Student.user_id),
    return that student's id, used to scope 'my assignments' / 'my
    submissions' style endpoints so a student can only ever see their own
    data, never a classmate's, regardless of what id is passed in the URL.
    """
    from app.models import Student

    user = current_user()
    if user is None:
        return None
    student = Student.query.filter_by(user_id=user.id, school_id=current_school_id()).first()
    return student.id if student else None


def linked_staff_id():
    """
    If the caller's account is linked to a Staff record (Staff.user_id),
    return that staff member's id, used so a teacher marking attendance
    is always attributed as themself (never a spoofed staff_id), and so
    "my periods today" style endpoints know whose schedule to return.
    """
    from app.models import Staff

    user = current_user()
    if user is None:
        return None
    staff = Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()
    return staff.id if staff else None


def linked_guardian_children_ids():
    """Student ids belonging to the caller's own children, if the caller is a linked guardian account."""
    from app.models import Guardian

    user = current_user()
    if user is None:
        return []
    guardian = Guardian.query.filter_by(user_id=user.id, school_id=current_school_id()).first()
    if not guardian:
        return []
    return [sg.student_id for sg in guardian.students]


def resolve_guardian_selected_child():
    """
    For a guardian with more than one child, resolve which child's data
    the caller is asking about, via an optional ?student_id= query
    param, always validated against the caller's OWN children so a
    parent can never see another family's child by guessing an id.
    Defaults to the first child if no student_id is given or it doesn't
    belong to this guardian. Returns None if the caller isn't a linked
    guardian at all.
    """
    children = linked_guardian_children_ids()
    if not children:
        return None
    requested = request.args.get("student_id")
    if requested and requested in children:
        return requested
    return children[0]


def super_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if "platform.schools.manage" not in set(claims.get("permissions", [])):
            return jsonify({"error": "Super admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper
