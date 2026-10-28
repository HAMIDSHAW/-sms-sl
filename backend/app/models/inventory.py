from datetime import date

from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

ASSET_STATUSES = ["in_use", "in_storage", "under_maintenance", "disposed"]


class Supplier(db.Model, TimestampMixin):
    __tablename__ = "suppliers"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "contact_person": self.contact_person,
            "phone": self.phone, "email": self.email, "address": self.address, "is_active": self.is_active,
        }


class InventoryItem(db.Model, TimestampMixin):
    """A tracked asset (spec section 62), furniture, equipment, etc. Quantity-based, not per-serial-number."""

    __tablename__ = "inventory_items"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120), nullable=True)
    supplier_id = db.Column(db.String(36), db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_cost = db.Column(db.Float, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="in_use")
    purchase_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "category": self.category, "supplier_id": self.supplier_id,
            "quantity": self.quantity, "unit_cost": self.unit_cost, "location": self.location,
            "status": self.status, "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "is_active": self.is_active,
        }


class MaintenanceRecord(db.Model, TimestampMixin):
    """A maintenance event against an inventory item (spec section 62: Maintenance)."""

    __tablename__ = "maintenance_records"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    item_id = db.Column(db.String(36), db.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    cost = db.Column(db.Float, nullable=True)
    performed_date = db.Column(db.Date, nullable=False, default=date.today)
    recorded_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    completed_date = db.Column(db.Date, nullable=True)  # set when the item is returned to service

    def to_dict(self):
        return {
            "id": self.id, "item_id": self.item_id, "description": self.description, "cost": self.cost,
            "performed_date": self.performed_date.isoformat(),
            "completed_date": self.completed_date.isoformat() if self.completed_date else None,
            "status": "completed" if self.completed_date else "open",
        }
