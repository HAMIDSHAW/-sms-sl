from datetime import date

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Supplier, InventoryItem, MaintenanceRecord, Staff
from app.utils.tenancy import current_school_id, current_user, permission_required, scoped_query

bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


def _caller_staff():
    user = current_user()
    return Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()


# --- Suppliers --------------------------------------------------------------

@bp.get("/suppliers")
@permission_required("inventory.view")
def list_suppliers():
    return jsonify([s.to_dict() for s in scoped_query(Supplier).filter_by(is_active=True).all()])


@bp.post("/suppliers")
@permission_required("inventory.manage")
def create_supplier():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    supplier = Supplier(
        school_id=current_school_id(), name=data["name"], contact_person=data.get("contact_person"),
        phone=data.get("phone"), email=data.get("email"), address=data.get("address"),
    )
    db.session.add(supplier)
    db.session.commit()
    return jsonify(supplier.to_dict()), 201


# --- Inventory items (spec section 62) --------------------------------------

@bp.get("/items")
@permission_required("inventory.view")
def list_items():
    query = scoped_query(InventoryItem).filter_by(is_active=True)
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(InventoryItem.name.ilike(f"%{q}%"))
    category = request.args.get("category")
    if category:
        query = query.filter_by(category=category)

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(InventoryItem.name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [i.to_dict() for i in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.post("/items")
@permission_required("inventory.manage")
def create_item():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    school_id = current_school_id()
    supplier_id = data.get("supplier_id")
    if supplier_id and not Supplier.query.filter_by(id=supplier_id, school_id=school_id).first():
        return jsonify({"error": "supplier_id does not belong to this school"}), 404

    item = InventoryItem(
        school_id=school_id, name=data["name"], category=data.get("category"), supplier_id=supplier_id,
        quantity=data.get("quantity", 1), unit_cost=data.get("unit_cost"), location=data.get("location"),
        status=data.get("status", "in_use"),
        purchase_date=date.fromisoformat(data["purchase_date"]) if data.get("purchase_date") else None,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@bp.patch("/items/<item_id>")
@permission_required("inventory.manage")
def update_item(item_id):
    item = scoped_query(InventoryItem).filter_by(id=item_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["name", "category", "quantity", "unit_cost", "location", "status", "is_active"]:
        if field in data:
            setattr(item, field, data[field])
    db.session.commit()
    return jsonify(item.to_dict())


# --- Maintenance (spec section 62) ------------------------------------------

@bp.get("/items/<item_id>/maintenance")
@permission_required("inventory.view")
def list_maintenance(item_id):
    item = scoped_query(InventoryItem).filter_by(id=item_id).first_or_404()
    records = scoped_query(MaintenanceRecord).filter_by(item_id=item.id).order_by(MaintenanceRecord.performed_date.desc()).all()
    return jsonify([r.to_dict() for r in records])


@bp.post("/items/<item_id>/maintenance")
@permission_required("inventory.manage")
def create_maintenance(item_id):
    """Logging a maintenance event also flips the item to 'under_maintenance', a maintenance record with no
    effect on the item's own status would be easy to overlook when checking what's actually usable right now."""
    item = scoped_query(InventoryItem).filter_by(id=item_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if not data.get("description"):
        return jsonify({"error": "description is required"}), 400

    record = MaintenanceRecord(
        school_id=current_school_id(), item_id=item.id, description=data["description"],
        cost=data.get("cost"), performed_date=date.fromisoformat(data["performed_date"]) if data.get("performed_date") else date.today(),
        recorded_by_staff_id=_caller_staff().id if _caller_staff() else None,
    )
    db.session.add(record)
    item.status = "under_maintenance"
    db.session.commit()
    return jsonify(record.to_dict()), 201


@bp.post("/items/<item_id>/restore")
@permission_required("inventory.manage")
def restore_item(item_id):
    """Mark an item back in service after maintenance, closing any open maintenance records."""
    item = scoped_query(InventoryItem).filter_by(id=item_id).first_or_404()
    data = request.get_json(silent=True) or {}
    item.status = data.get("status") if data.get("status") in ("in_use", "in_stock", "damaged", "disposed") else "in_use"
    for record in MaintenanceRecord.query.filter_by(item_id=item.id, completed_date=None).all():
        record.completed_date = date.today()
        if data.get("cost") is not None and record.cost is None:
            record.cost = data["cost"]
    db.session.commit()
    return jsonify(item.to_dict())


@bp.delete("/items/<item_id>")
@permission_required("inventory.manage")
def delete_item(item_id):
    """Remove an item from the active inventory (hidden, not erased, so its history is kept)."""
    item = scoped_query(InventoryItem).filter_by(id=item_id).first_or_404()
    item.is_active = False
    db.session.commit()
    return jsonify({"message": "Item removed"})
