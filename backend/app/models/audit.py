from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin


class AuditLog(db.Model, TimestampMixin):
    """
    Records sensitive actions (spec section 75). Deliberately append-only -
    nothing in the codebase should ever update or delete a row here.
    Wired into the highest-value actions for now (see app/utils/audit.py
    call sites): student/staff deletion, school settings changes, role
    assignment, password resets. NOT yet wired into every single mutating
    endpoint, see README "honest gaps".
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    action = db.Column(db.String(100), nullable=False)  # e.g. "student.delete", "school.settings.update"
    module = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.String(36), nullable=True)

    before_value = db.Column(db.JSON, nullable=True)
    after_value = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id, "action": self.action, "module": self.module,
            "entity_type": self.entity_type, "entity_id": self.entity_id,
            "before_value": self.before_value, "after_value": self.after_value,
            "created_at": self.created_at.isoformat(),
        }
