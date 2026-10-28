from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import FeeCategory, FeeStructure
from app.utils.tenancy import current_school_id, permission_required, scoped_query

bp = Blueprint("fee_structures", __name__, url_prefix="/api/finance")


# --- Fee categories (spec section 50) --------------------------------------

@bp.get("/categories")
@permission_required("finance.view")
def list_categories():
    return jsonify([c.to_dict() for c in scoped_query(FeeCategory).filter_by(is_active=True).all()])


@bp.post("/categories")
@permission_required("finance.manage")
def create_category():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    category = FeeCategory(school_id=current_school_id(), name=data["name"], description=data.get("description"))
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


# --- Fee structures (spec section 49) --------------------------------------

@bp.get("/structures")
@permission_required("finance.view")
def list_structures():
    query = scoped_query(FeeStructure)
    for field in ["academic_year_id", "term_id", "class_id"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(FeeStructure, field) == value)
    return jsonify([s.to_dict() for s in query.all()])


@bp.post("/structures")
@permission_required("finance.manage")
def create_structure():
    data = request.get_json(silent=True) or {}
    required = ["name", "academic_year_id", "fee_category_id", "amount"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    from datetime import datetime
    structure = FeeStructure(
        school_id=current_school_id(), name=data["name"],
        academic_year_id=data["academic_year_id"], term_id=data.get("term_id"), class_id=data.get("class_id"),
        fee_category_id=data["fee_category_id"], amount=data["amount"],
        due_date=datetime.strptime(data["due_date"], "%Y-%m-%d").date() if data.get("due_date") else None,
        late_fee=data.get("late_fee", 0), is_mandatory=data.get("is_mandatory", True),
    )
    db.session.add(structure)
    db.session.commit()
    return jsonify(structure.to_dict()), 201
