from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import GradeScale
from app.utils.tenancy import current_school_id, permission_required, scoped_query
from app.utils.grading import DEFAULT_GRADE_SCALE, ensure_default_grade_scale

bp = Blueprint("grading", __name__, url_prefix="/api/grading")


@bp.get("/scale")
@permission_required("exams.view")
def get_grade_scale():
    school_id = current_school_id()
    ensure_default_grade_scale(school_id)
    db.session.commit()
    scale = scoped_query(GradeScale).order_by(GradeScale.min_score.desc()).all()
    return jsonify([s.to_dict() for s in scale])


@bp.post("/scale")
@permission_required("grading.manage")
def create_grade_band():
    data = request.get_json(silent=True) or {}
    required = ["grade", "min_score", "max_score"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    band = GradeScale(
        school_id=current_school_id(), grade=data["grade"],
        min_score=data["min_score"], max_score=data["max_score"],
        grade_point=data.get("grade_point"), description=data.get("description"),
        is_pass=data.get("is_pass", True),
    )
    db.session.add(band)
    db.session.commit()
    return jsonify(band.to_dict()), 201


@bp.patch("/scale/<band_id>")
@permission_required("grading.manage")
def update_grade_band(band_id):
    band = scoped_query(GradeScale).filter_by(id=band_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["grade", "min_score", "max_score", "grade_point", "description", "is_pass"]:
        if field in data:
            setattr(band, field, data[field])
    db.session.commit()
    return jsonify(band.to_dict())


@bp.delete("/scale/<band_id>")
@permission_required("grading.manage")
def delete_grade_band(band_id):
    band = scoped_query(GradeScale).filter_by(id=band_id).first_or_404()
    db.session.delete(band)
    db.session.commit()
    return jsonify({"message": "Grade band removed"})
