from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin


class AcademicYear(db.Model, TimestampMixin):
    __tablename__ = "academic_years"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(50), nullable=False)  # e.g. "2026/2027"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False)

    terms = db.relationship("Term", back_populates="academic_year", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("school_id", "name", name="uq_year_school_name"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_current": self.is_current,
        }


class Term(db.Model, TimestampMixin):
    __tablename__ = "terms"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)

    name = db.Column(db.String(50), nullable=False)  # "First Term", "Term 1"...
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False)

    academic_year = db.relationship("AcademicYear", back_populates="terms")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_current": self.is_current,
        }


class SchoolClass(db.Model, TimestampMixin):
    """
    A 'class' in the SIS sense, an academic level (Grade 1, JSS 1, SSS 2...).
    Named SchoolClass to avoid clashing with the Python keyword.
    """

    __tablename__ = "classes"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(80), nullable=False)  # school defines its own naming (spec section 24)
    order_index = db.Column(db.Integer, nullable=False, default=0)  # for sorting Grade 1 before Grade 2, etc.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    class_master_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    sections = db.relationship("Section", back_populates="school_class", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("school_id", "name", name="uq_class_school_name"),)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "order_index": self.order_index, "is_active": self.is_active,
            "class_master_staff_id": self.class_master_staff_id,
        }


class Section(db.Model, TimestampMixin):
    __tablename__ = "sections"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)

    name = db.Column(db.String(50), nullable=False)  # "A", "B", "North"...
    capacity = db.Column(db.Integer, nullable=True)
    class_teacher_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    school_class = db.relationship("SchoolClass", back_populates="sections")

    __table_args__ = (db.UniqueConstraint("class_id", "name", name="uq_section_class_name"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "class_id": self.class_id,
            "capacity": self.capacity,
            "class_teacher_staff_id": self.class_teacher_staff_id,
        }


class Subject(db.Model, TimestampMixin):
    __tablename__ = "subjects"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    max_marks = db.Column(db.Integer, nullable=False, default=100)
    pass_mark = db.Column(db.Integer, nullable=False, default=50)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("school_id", "code", name="uq_subject_school_code"),)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code, "department": self.department,
            "max_marks": self.max_marks, "pass_mark": self.pass_mark, "is_active": self.is_active,
        }


class TeacherAssignment(db.Model, TimestampMixin):
    """Which teacher teaches which subject, to which class/section, in which term."""

    __tablename__ = "teacher_assignments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="CASCADE"), nullable=True)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "staff_id", "subject_id", "class_id", "section_id", "academic_year_id",
            name="uq_teacher_assignment_no_dupe",
        ),
    )


class Enrollment(db.Model, TimestampMixin):
    """
    The record that determines which class/section a student belongs to for
    a given academic year. This is the pivot the whole spec depends on
    (section 2): everything downstream, timetable, attendance, exams -
    is derived from a student's current enrollment.
    """

    __tablename__ = "enrollments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)

    enrollment_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="active")  # active, promoted, transferred, withdrawn

    student = db.relationship("Student", back_populates="enrollments")

    __table_args__ = (
        db.UniqueConstraint("student_id", "academic_year_id", name="uq_enrollment_student_year"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "academic_year_id": self.academic_year_id,
            "class_id": self.class_id,
            "section_id": self.section_id,
            "enrollment_date": self.enrollment_date.isoformat(),
            "status": self.status,
        }
