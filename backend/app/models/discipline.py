from datetime import datetime, timezone

from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

DISCIPLINE_CATEGORIES = ["warning", "incident", "suspension", "positive_recognition"]
DISCIPLINE_SEVERITIES = ["low", "medium", "high"]
DISCIPLINE_STATUSES = ["open", "resolved", "follow_up_needed"]


class DisciplinaryRecord(db.Model, TimestampMixin):
    """
    A discipline entry for a student (spec section 59/108). Deliberately
    supports 'positive_recognition' as a category, not just infractions -
    the spec calls for the system to "support positive recognition rather
    than only punishment," and a category field that can only express
    negative events wouldn't allow that.
    """

    __tablename__ = "disciplinary_records"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reported_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(30), nullable=False, default="incident")
    severity = db.Column(db.String(20), nullable=True)  # null for positive_recognition
    description = db.Column(db.Text, nullable=False)
    action_taken = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="open")
    follow_up_note = db.Column(db.String(500), nullable=True)
    follow_up_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        from app.models import Student, Staff
        student = Student.query.get(self.student_id)
        reporter = Staff.query.get(self.reported_by_staff_id) if self.reported_by_staff_id else None
        return {
            "id": self.id, "student_id": self.student_id, "reported_by_staff_id": self.reported_by_staff_id,
            "date": self.date.isoformat(), "category": self.category, "severity": self.severity,
            "description": self.description, "action_taken": self.action_taken,
            "status": self.status, "follow_up_note": self.follow_up_note,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
            "student_name": student.full_name if student else None,
            "student_photo_url": student.photo_url if student else None,
            "student_number": student.student_number if student else None,
            "reported_by_name": reporter.full_name if reporter else None,
        }
