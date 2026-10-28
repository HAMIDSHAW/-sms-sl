from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

# Default statuses seeded per school (spec section 30). Schools can add
# their own via POST /api/attendance/statuses, this list is just the
# starting set, not a hard-coded enum.
DEFAULT_ATTENDANCE_STATUSES = [
    {"code": "present", "label": "Present", "counts_as_present": True},
    {"code": "absent", "label": "Absent", "counts_as_present": False},
    {"code": "late", "label": "Late", "counts_as_present": True},
    {"code": "excused", "label": "Excused", "counts_as_present": False},
    {"code": "leave", "label": "Leave", "counts_as_present": False},
]


class AttendanceStatus(db.Model, TimestampMixin):
    __tablename__ = "attendance_statuses"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    code = db.Column(db.String(30), nullable=False)
    label = db.Column(db.String(50), nullable=False)
    counts_as_present = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("school_id", "code", name="uq_attendance_status_school_code"),)

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "label": self.label,
            "counts_as_present": self.counts_as_present, "is_active": self.is_active,
        }


class Attendance(db.Model, TimestampMixin):
    """
    One row per student per date (+ optional subject/period, for schools
    that take attendance per-period rather than once a day). Recorded
    fields (teacher, date, time, status, note) follow spec section 31.
    """

    __tablename__ = "attendance"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    term_id = db.Column(db.String(36), db.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True)

    date = db.Column(db.Date, nullable=False)
    status_id = db.Column(db.String(36), db.ForeignKey("attendance_statuses.id"), nullable=False)
    marked_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    note = db.Column(db.String(500), nullable=True)

    status = db.relationship("AttendanceStatus")

    __table_args__ = (
        # One record per student per date per subject (NULL subject = daily attendance).
        db.UniqueConstraint("student_id", "date", "subject_id", name="uq_attendance_student_date_subject"),
    )

    def to_dict(self):
        from app.models import Student, Staff, Subject, SchoolClass
        student = Student.query.get(self.student_id)
        subject = Subject.query.get(self.subject_id) if self.subject_id else None
        school_class = SchoolClass.query.get(self.class_id)
        marker = Staff.query.get(self.marked_by_staff_id) if self.marked_by_staff_id else None
        return {
            "id": self.id,
            "student_id": self.student_id,
            "class_id": self.class_id,
            "section_id": self.section_id,
            "subject_id": self.subject_id,
            "subject_name": subject.name if subject else None,
            "class_name": school_class.name if school_class else None,
            "student_number": student.student_number if student else None,
            "kind": "period" if self.subject_id else "whole_day",
            "date": self.date.isoformat(),
            "status_id": self.status_id,
            "status_code": self.status.code if self.status else None,
            "status_label": self.status.label if self.status else None,
            "status_counts_as_present": self.status.counts_as_present if self.status else None,
            "marked_by_staff_id": self.marked_by_staff_id,
            "note": self.note,
            "student_name": student.full_name if student else None,
            "student_photo_url": student.photo_url if student else None,
            "marked_by_name": marker.full_name if marker else None,
        }
