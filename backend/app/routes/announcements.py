from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Announcement, Enrollment
from app.models.communication import ANNOUNCEMENT_AUDIENCES
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query, jwt_required_scoped,
    linked_student_id, linked_guardian_children_ids,
)
from app.utils.notify import notify, notify_guardians_of_student

bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")


def _my_class_ids(student_id=None, children_ids=None):
    ids = []
    if student_id:
        e = Enrollment.query.filter_by(student_id=student_id, status="active").first()
        if e:
            ids.append(e.class_id)
    for cid in (children_ids or []):
        e = Enrollment.query.filter_by(student_id=cid, status="active").first()
        if e:
            ids.append(e.class_id)
    return ids


@bp.get("")
@jwt_required_scoped
def list_announcements():
    """
    Resolves visibility per-caller rather than storing one row per
    recipient (spec section 57): everyone sees 'school'-wide posts; role-
    matched audiences (teachers/students/parents/staff) are shown based on
    the caller's own roles; class/section audiences are shown only to
    students/guardians whose (child's) current enrollment matches.
    """
    user = current_user()
    query = scoped_query(Announcement)

    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()
    my_class_ids = _my_class_ids(student_scope, guardian_children)
    role_names = [r.name for r in user.roles]

    role_audiences = ["school"]
    if user.has_permission("*") or "principal" in role_names:
        role_audiences.append("staff")
    if "teacher" in role_names:
        role_audiences.append("teachers")
    if student_scope:
        role_audiences.append("students")
    if guardian_children:
        role_audiences.append("parents")

    # audience_types is a comma-separated list; match if it contains ANY
    # audience the caller belongs to (an announcement posted to
    # "teachers,parents" should reach both groups, not require an exact
    # match on the whole string).
    # Delimiter-padded containment check (",teachers,") rather than a bare
    # substring match, so e.g. "students" can never accidentally match
    # inside a longer audience name.
    conditions = [db.or_(*[Announcement.audience_types.contains(f",{a},") for a in role_audiences])]
    if my_class_ids:
        conditions.append(Announcement.audience_class_id.in_(my_class_ids))

    announcements = query.filter(db.or_(*conditions)).order_by(Announcement.created_at.desc()).all()
    return jsonify([a.to_dict() for a in announcements])


@bp.post("")
@permission_required("announcements.create")
def create_announcement():
    data = request.get_json(silent=True) or {}
    # Accept either the new multi-select audience_types (a list) or the
    # older single audience_type (a string), so nothing that already calls
    # this endpoint with the old shape breaks.
    types = data.get("audience_types")
    if not types:
        single = data.get("audience_type")
        types = [single] if single else []
    types = [t for t in types if t in ANNOUNCEMENT_AUDIENCES]

    if not (data.get("title") and data.get("body") and types):
        missing = [f for f in ["title", "body"] if not data.get(f)]
        if not types:
            missing.append("audience_types")
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    user = current_user()
    school_id = current_school_id()

    announcement = Announcement(
        school_id=school_id, author_user_id=user.id, title=data["title"], body=data["body"],
        audience_type=types[0], audience_types="," + ",".join(types) + ",",
        audience_class_id=data.get("audience_class_id"),
        audience_section_id=data.get("audience_section_id"),
    )
    db.session.add(announcement)
    db.session.flush()

    # Fan out a notification to guardians/students in the target class, if class-scoped.
    if announcement.audience_class_id:
        for e in Enrollment.query.filter_by(class_id=announcement.audience_class_id, status="active").all():
            notify_guardians_of_student(
                school_id, e.student_id, "announcement_published", announcement.title,
                announcement.body[:200], related_entity_type="announcement", related_entity_id=announcement.id,
            )

    db.session.commit()
    return jsonify(announcement.to_dict()), 201
