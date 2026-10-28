from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin, SoftDeleteMixin


class Student(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "students"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student_number = db.Column(db.String(50), nullable=False)  # e.g. STU-2026-00001, unique per school
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # optional login

    first_name = db.Column(db.String(120), nullable=False)
    middle_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)

    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    nationality = db.Column(db.String(80), nullable=True)

    # Sierra Leone realities: many addresses are landmark-based rather than
    # street/number, so this is a free-text field, not structured street
    # fields that would force an unnatural format on the user.
    address = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)

    admission_date = db.Column(db.Date, nullable=True)
    admission_number = db.Column(db.String(50), nullable=True)

    emergency_contact_name = db.Column(db.String(120), nullable=True)
    emergency_contact_phone = db.Column(db.String(50), nullable=True)

    status = db.Column(
        db.String(30), nullable=False, default="active"
    )  # active, inactive, graduated, transferred, suspended, withdrawn

    custom_fields = db.Column(db.JSON, nullable=True)  # school-defined extra fields (spec section 12)

    guardians = db.relationship("StudentGuardian", back_populates="student", cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("school_id", "student_number", name="uq_student_school_number"),)

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    def to_dict(self):
        return {
            "id": self.id,
            "student_number": self.student_number,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "photo_url": self.photo_url,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender": self.gender,
            "nationality": self.nationality,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "admission_date": self.admission_date.isoformat() if self.admission_date else None,
            "status": self.status,
            "guardians": [g.to_dict() for g in self.guardians],
        }


class Guardian(db.Model, TimestampMixin):
    """A parent or guardian account. One guardian can have many children (students)."""

    __tablename__ = "guardians"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)

    phone = db.Column(db.String(50), nullable=True)  # primary channel for SMS notifications
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(500), nullable=True)
    occupation = db.Column(db.String(120), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    students = db.relationship("StudentGuardian", back_populates="guardian", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "photo_url": self.photo_url,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "occupation": self.occupation,
        }


class StudentGuardian(db.Model):
    """Join table: which guardians belong to which student, and how (relationship, primary contact)."""

    __tablename__ = "student_guardians"

    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    guardian_id = db.Column(db.String(36), db.ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)

    relationship_type = db.Column(db.String(50), nullable=False, default="parent")  # parent, guardian, relative
    is_primary_contact = db.Column(db.Boolean, nullable=False, default=False)
    is_emergency_contact = db.Column(db.Boolean, nullable=False, default=False)
    can_pickup = db.Column(db.Boolean, nullable=False, default=True)

    student = db.relationship("Student", back_populates="guardians")
    guardian = db.relationship("Guardian", back_populates="students")

    def to_dict(self):
        return {
            "guardian_id": self.guardian_id,
            "guardian": self.guardian.to_dict() if self.guardian else None,
            "relationship_type": self.relationship_type,
            "is_primary_contact": self.is_primary_contact,
            "is_emergency_contact": self.is_emergency_contact,
        }


class Staff(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Covers teachers, administrators, and support staff, one table with a
    `staff_type` discriminator, since the spec's fields overlap heavily
    (employee ID, department, position, qualifications, subjects/classes
    only apply meaningfully to teachers but the rest is shared).
    """

    __tablename__ = "staff"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    employee_number = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(10), nullable=True)  # Mr, Mrs, Miss, Dr, Madam, etc.
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)

    staff_type = db.Column(db.String(30), nullable=False, default="teacher")  # teacher, administrator, support
    department = db.Column(db.String(120), nullable=True)
    position = db.Column(db.String(120), nullable=True)
    qualifications = db.Column(db.Text, nullable=True)

    employment_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="active")  # active, on_leave, terminated

    # Where the staff member lives (landmark style is fine), so the school
    # knows how to reach or find them. Editable by the staff member on their
    # own profile and by HR/admin.
    address = db.Column(db.String(500), nullable=True)
    base_salary = db.Column(db.Float, nullable=True)  # used to pre-fill payroll runs; never sent in staff lists

    __table_args__ = (
        db.UniqueConstraint("school_id", "employee_number", name="uq_staff_school_number"),
    )

    @property
    def full_name(self):
        prefix = f"{self.title} " if self.title else ""
        return f"{prefix}{self.first_name} {self.last_name}"

    def to_dict(self, include_salary=False):
        data = self._base_dict()
        if include_salary:
            data["base_salary"] = self.base_salary
        return data

    def _base_dict(self):
        return {
            "id": self.id,
            "employee_number": self.employee_number,
            "title": self.title,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "photo_url": self.photo_url,
            "staff_type": self.staff_type,
            "department": self.department,
            "position": self.position,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "user_id": self.user_id,
            "status": self.status,
        }
