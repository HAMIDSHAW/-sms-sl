from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

EXAM_STATUSES = ["draft", "scheduled", "in_progress", "completed"]
# spec section 46: the approval chain a result set moves through
RESULT_WORKFLOW_STATES = ["draft", "teacher_submitted", "exam_officer_review", "principal_approved", "published"]


class Examination(db.Model, TimestampMixin):
    """An exam sitting (spec section 41), e.g. 'First Term Examination'."""

    __tablename__ = "examinations"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    term_id = db.Column(db.String(36), db.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "academic_year_id": self.academic_year_id,
            "term_id": self.term_id, "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(), "instructions": self.instructions, "status": self.status,
        }


class ExamSchedule(db.Model, TimestampMixin):
    """One subject's sitting within an examination (spec section 42)."""

    __tablename__ = "exam_schedules"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    examination_id = db.Column(db.String(36), db.ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)

    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(100), nullable=True)
    invigilator_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    max_marks = db.Column(db.Integer, nullable=False, default=100)

    def to_dict(self):
        return {
            "id": self.id, "examination_id": self.examination_id, "subject_id": self.subject_id,
            "class_id": self.class_id, "section_id": self.section_id, "date": self.date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M"), "end_time": self.end_time.strftime("%H:%M"),
            "room": self.room, "invigilator_staff_id": self.invigilator_staff_id, "max_marks": self.max_marks,
        }


class GradeScale(db.Model, TimestampMixin):
    """
    School-configurable grading bands (spec section 44), e.g. A: 80-100.
    The grading engine (app/utils/grading.py) looks up the matching band
    for a percentage score, nothing about specific grade boundaries is
    hard-coded anywhere else in the app.
    """

    __tablename__ = "grade_scales"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    grade = db.Column(db.String(10), nullable=False)  # "A", "B+", "1", etc.
    min_score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    grade_point = db.Column(db.Float, nullable=True)
    description = db.Column(db.String(100), nullable=True)
    is_pass = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id, "grade": self.grade, "min_score": self.min_score, "max_score": self.max_score,
            "grade_point": self.grade_point, "description": self.description, "is_pass": self.is_pass,
        }


class Mark(db.Model, TimestampMixin):
    """One student's raw score for one exam-schedule entry (spec section 43)."""

    __tablename__ = "marks"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    exam_schedule_id = db.Column(db.String(36), db.ForeignKey("exam_schedules.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    obtained_marks = db.Column(db.Float, nullable=True)  # null = absent/not yet entered
    is_absent = db.Column(db.Boolean, nullable=False, default=False)
    comment = db.Column(db.String(255), nullable=True)
    entered_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("exam_schedule_id", "student_id", name="uq_mark_schedule_student"),
    )

    def to_dict(self):
        return {
            "id": self.id, "exam_schedule_id": self.exam_schedule_id, "student_id": self.student_id,
            "obtained_marks": self.obtained_marks, "is_absent": self.is_absent, "comment": self.comment,
        }


class Result(db.Model, TimestampMixin):
    """
    One student's computed result for one examination, aggregated across
    all subjects sat (spec sections 45-46). Computed by
    app/utils/grading.py:compute_results(), never hand-entered, so the
    numbers always trace back to the underlying Marks.
    """

    __tablename__ = "results"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    examination_id = db.Column(db.String(36), db.ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    total_marks = db.Column(db.Float, nullable=True)
    total_max_marks = db.Column(db.Float, nullable=True)
    average_percentage = db.Column(db.Float, nullable=True)
    overall_grade = db.Column(db.String(10), nullable=True)
    overall_grade_point = db.Column(db.Float, nullable=True)
    is_pass = db.Column(db.Boolean, nullable=True)
    subject_position = db.Column(db.Integer, nullable=True)  # reserved for future subject-level ranking
    overall_position = db.Column(db.Integer, nullable=True)

    teacher_remark = db.Column(db.String(500), nullable=True)
    principal_remark = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(30), nullable=False, default="draft")  # RESULT_WORKFLOW_STATES

    __table_args__ = (
        db.UniqueConstraint("examination_id", "student_id", name="uq_result_examination_student"),
    )

    def to_dict(self):
        return {
            "id": self.id, "examination_id": self.examination_id, "student_id": self.student_id,
            "total_marks": self.total_marks, "total_max_marks": self.total_max_marks,
            "average_percentage": self.average_percentage, "overall_grade": self.overall_grade,
            "overall_grade_point": self.overall_grade_point, "is_pass": self.is_pass,
            "overall_position": self.overall_position,
            "teacher_remark": self.teacher_remark, "principal_remark": self.principal_remark,
            "status": self.status,
        }
