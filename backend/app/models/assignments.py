from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

# spec section 36
ASSIGNMENT_STATUSES = ["draft", "published", "closed"]
# spec section 37 - status of a specific student's submission
SUBMISSION_STATUSES = ["not_submitted", "submitted", "late", "graded"]


class Assignment(db.Model, TimestampMixin):
    __tablename__ = "assignments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)  # creator
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    term_id = db.Column(db.String(36), db.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)

    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False, default=100)
    attachment_url = db.Column(db.String(500), nullable=True)
    submission_type = db.Column(db.String(30), nullable=False, default="file")  # file, text, both

    status = db.Column(db.String(20), nullable=False, default="draft")

    # Who actually set it. Normally the teacher themself (== staff_id); differs only when an
    # administrator set it on a teacher's behalf. Either of the two may then manage it.
    created_by_user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # First deadline, kept once the owner extends it so the change stays visible.
    original_due_date = db.Column(db.Date, nullable=True)

    @property
    def is_closed(self):
        """Closed once the owner closes it, or the day after the deadline. Extending the deadline reopens it."""
        from datetime import date
        return self.status == "closed" or bool(self.due_date and date.today() > self.due_date)

    def to_dict(self):
        from app.models import Staff, Subject, SchoolClass
        teacher = Staff.query.get(self.staff_id)
        subject = Subject.query.get(self.subject_id)
        school_class = SchoolClass.query.get(self.class_id)
        return {
            "teacher_name": teacher.full_name if teacher else None,
            "teacher_photo_url": teacher.photo_url if teacher else None,
            "teacher_position": teacher.position if teacher else None,
            "teacher_phone": teacher.phone if teacher else None,
            "subject_name": subject.name if subject else None,
            "class_name": school_class.name if school_class else None,
            "id": self.id, "subject_id": self.subject_id, "class_id": self.class_id,
            "section_id": self.section_id, "staff_id": self.staff_id,
            "academic_year_id": self.academic_year_id, "term_id": self.term_id,
            "title": self.title, "description": self.description, "instructions": self.instructions,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat(), "max_marks": self.max_marks,
            "attachment_url": self.attachment_url, "submission_type": self.submission_type,
            "status": self.status, "is_closed": self.is_closed,
            "original_due_date": self.original_due_date.isoformat() if self.original_due_date else None,
            "extended": bool(self.original_due_date and self.original_due_date != self.due_date),
        }


class AssignmentSubmission(db.Model, TimestampMixin):
    """
    One row per student per assignment (spec section 37-38). Created lazily
    on first submission, a student who hasn't submitted yet simply has no
    row, rather than a pre-created 'pending' row for every enrolled student,
    since class rosters change and we don't want stale placeholder rows.
    """

    __tablename__ = "assignment_submissions"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    assignment_id = db.Column(db.String(36), db.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    submitted_at = db.Column(db.DateTime, nullable=True)
    content_text = db.Column(db.Text, nullable=True)
    attachment_url = db.Column(db.String(500), nullable=True)

    marks_obtained = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="not_submitted")

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),
    )

    def to_dict(self):
        from app.models import Student, Enrollment, SchoolClass, Staff
        student = Student.query.get(self.student_id)
        enrollment = Enrollment.query.filter_by(student_id=self.student_id, status="active").first()
        school_class = SchoolClass.query.get(enrollment.class_id) if enrollment else None
        grader = Staff.query.get(self.graded_by_staff_id) if self.graded_by_staff_id else None
        return {
            "student_name": student.full_name if student else None,
            "student_number": student.student_number if student else None,
            "student_photo_url": student.photo_url if student else None,
            "class_name": school_class.name if school_class else None,
            "graded_by_name": grader.full_name if grader else None,
            "id": self.id, "assignment_id": self.assignment_id, "student_id": self.student_id,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "content_text": self.content_text, "attachment_url": self.attachment_url,
            "marks_obtained": self.marks_obtained, "feedback": self.feedback,
            "graded_at": self.graded_at.isoformat() if self.graded_at else None,
            "status": self.status,
        }
