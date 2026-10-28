"""
School setup wizard + settings (spec section 6 and section 100).

Everything about "which school this is" lives here and only here, name,
logo, address, currency, terminology, student ID format. A school admin can
change every one of these fields at any time; nothing elsewhere in the
codebase assumes a particular school's identity.
"""

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import School
from app.utils.tenancy import current_school_id, permission_required, jwt_required_scoped
from app.utils.audit import record_audit

bp = Blueprint("schools", __name__, url_prefix="/api/school")

EDITABLE_FIELDS = [
    "name", "short_name", "logo_url", "motto", "description",
    "address", "city", "district", "country", "phone", "email", "website",
    "currency", "timezone", "language", "terminology",
    "student_id_prefix", "student_id_format",
]


@bp.get("")
@jwt_required_scoped
def get_my_school():
    school = School.query.get_or_404(current_school_id())
    return jsonify(school.to_dict())


@bp.patch("")
@permission_required("school.settings.manage")
def update_my_school():
    school = School.query.get_or_404(current_school_id())
    data = request.get_json(silent=True) or {}

    before = {f: getattr(school, f) for f in EDITABLE_FIELDS if f in data}
    for field in EDITABLE_FIELDS:
        if field in data:
            setattr(school, field, data[field])

    db.session.commit()
    record_audit("school.settings.update", "school", "school", school.id, before=before, after={f: data[f] for f in data if f in EDITABLE_FIELDS})
    db.session.commit()
    return jsonify(school.to_dict())


@bp.post("/complete-setup")
@permission_required("school.settings.manage")
def complete_setup():
    """Marks the first-run setup wizard as done (spec section 6)."""
    school = School.query.get_or_404(current_school_id())
    school.setup_completed = True
    db.session.commit()
    return jsonify(school.to_dict())
