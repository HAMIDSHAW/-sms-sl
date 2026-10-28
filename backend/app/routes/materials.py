from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import LearningMaterial, Enrollment, Staff
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, any_permission_required, scoped_query,
    linked_student_id, linked_staff_id, resolve_guardian_selected_child, has_permission,
)

bp = Blueprint("materials", __name__, url_prefix="/api/materials")


@bp.get("")
@permission_required("materials.view")
def list_materials():
    """
    Students see their own class; a parent sees the SELECTED child's class.
    Staff can filter by class/subject/category and search by title or description.
    Each row says whether the caller may delete it (owner, admin or principal).
    """
    query = scoped_query(LearningMaterial).filter_by(is_active=True)

    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()
    subject_student = student_id or child_id

    if subject_student:
        enrollment = Enrollment.query.filter_by(student_id=subject_student, status="active").first()
        if not enrollment:
            return jsonify([])
        query = query.filter(LearningMaterial.class_id == enrollment.class_id)
    else:
        for field in ["class_id", "section_id", "subject_id", "staff_id", "category"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(LearningMaterial, field) == value)

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            LearningMaterial.title.ilike(like), LearningMaterial.description.ilike(like),
            LearningMaterial.category.ilike(like),
        ))

    my_staff = linked_staff_id()
    moderator = has_permission("materials.moderate")
    items = []
    for m in query.order_by(LearningMaterial.created_at.desc()).all():
        d = m.to_dict()
        d["can_delete"] = bool(moderator or (my_staff and m.staff_id == my_staff))
        items.append(d)
    return jsonify(items)


@bp.post("")
@permission_required("materials.manage")
def create_material():
    data = request.get_json(silent=True) or {}
    required = ["subject_id", "class_id", "academic_year_id", "title"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # Same rule as assignment authorship (found missing here during a gap
    # audit, materials had never gotten this fix even though assignments
    # and marks did): staff_id is derived from the caller's own linked
    # staff record whenever one exists, not trusted from the request body.
    school_id = current_school_id()
    caller_staff = Staff.query.filter_by(user_id=current_user().id, school_id=school_id).first()
    staff_id = caller_staff.id if caller_staff else data.get("staff_id")
    if not staff_id:
        return jsonify({"error": "staff_id is required when the caller has no linked staff record"}), 400

    material = LearningMaterial(
        school_id=school_id,
        subject_id=data["subject_id"], class_id=data["class_id"], section_id=data.get("section_id"),
        staff_id=staff_id, academic_year_id=data["academic_year_id"],
        title=data["title"], description=data.get("description"), category=data.get("category"),
        material_type=data.get("material_type", "pdf"),
        file_url=data.get("file_url"), external_link=data.get("external_link"),
    )
    db.session.add(material)
    db.session.commit()
    return jsonify(material.to_dict()), 201


@bp.patch("/<material_id>")
@permission_required("materials.manage")
def update_material(material_id):
    material = scoped_query(LearningMaterial).filter_by(id=material_id).first_or_404()

    if not has_permission("*") and material.staff_id != linked_staff_id():
        return jsonify({"error": "You can only edit your own materials"}), 403

    data = request.get_json(silent=True) or {}
    for field in ["title", "description", "category", "material_type", "file_url", "external_link", "is_active"]:
        if field in data:
            setattr(material, field, data[field])
    db.session.commit()
    return jsonify(material.to_dict())


@bp.delete("/<material_id>")
@any_permission_required("materials.manage", "materials.moderate")
def delete_material(material_id):
    material = scoped_query(LearningMaterial).filter_by(id=material_id).first_or_404()

    # Same ownership gap as assignments (materials.manage is shared by
    # every teacher): without this, any teacher with materials.manage
    # could archive any other teacher's material, not just their own.
    # Teachers may only remove what they shared; admin and principal
    # (materials.moderate) may remove anything.
    if not has_permission("materials.moderate") and material.staff_id != linked_staff_id():
        return jsonify({"error": "You can only delete materials you added"}), 403

    material.is_active = False
    db.session.commit()
    return jsonify({"message": "Material archived"})
