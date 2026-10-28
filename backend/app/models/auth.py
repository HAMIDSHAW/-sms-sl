from datetime import datetime, timedelta, timezone

from app.extensions import db, bcrypt
from app.models.base import gen_uuid, TimestampMixin

# Granular permission strings, following the pattern from the master spec
# (section 73): "<module>.<action>". Seeded by seed.py; schools can be
# granted custom roles built from any combination of these.
DEFAULT_PERMISSIONS = [
    # Users & roles
    "users.view", "users.create", "users.update", "users.delete", "users.assign_role",
    "roles.manage",
    # Students
    "students.view", "students.create", "students.update", "students.delete", "students.export",
    "students.documents.view", "students.documents.upload",
    # Parents
    "parents.view", "parents.create", "parents.update", "parents.delete",
    # Staff
    "staff.view", "staff.create", "staff.update", "staff.delete",
    # Academics
    "academics.view", "academics.manage",  # academic years, terms, classes, sections, subjects
    "enrollment.view", "enrollment.manage",
    # Attendance
    "attendance.view", "attendance.create", "attendance.update",
    # Timetable
    "timetable.view", "timetable.manage",
    # Assignments & materials
    "assignments.view", "assignments.create", "assignments.update", "assignments.delete",
    "assignments.grade", "assignments.submit",
    "materials.view", "materials.manage", "materials.moderate",
    # Exams & results
    "exams.view", "exams.create", "exams.update", "exams.schedule",
    "exams.mark", "results.view", "results.submit", "results.review", "results.approve", "results.publish",
    "grading.manage",
    # Finance
    "finance.view", "finance.manage", "finance.payment.create", "finance.refund", "finance.expenses.manage",
    # Communication
    "messages.send", "announcements.create",
    # HR / Payroll
    "hr.leave.view", "hr.leave.request", "hr.leave.approve", "hr.payroll.manage", "hr.payroll.view",
    # Discipline
    "discipline.view", "discipline.create", "discipline.update", "discipline.resolve",
    # Library
    "library.view", "library.manage", "library.circulation", "library.policy",
    # Analytics
    "analytics.view",
    # Inventory
    "inventory.view", "inventory.manage",
    # Transport
    "transport.view", "transport.manage",
    # Audit
    "audit.view",
    # School settings
    "school.settings.manage",
    # Platform-level (super admin only)
    "platform.schools.manage", "platform.subscriptions.manage",
]

# Starter roles. "permissions": "*" means all permissions in that school.
DEFAULT_ROLES = {
    "super_admin": {"permissions": ["platform.schools.manage", "platform.subscriptions.manage"], "school_scoped": False},
    "school_owner": {"permissions": "*", "school_scoped": True},
    "school_administrator": {"permissions": "*", "school_scoped": True},
    "principal": {
        "permissions": [
            "students.view", "staff.view", "parents.view", "academics.view", "academics.manage", "enrollment.view", "enrollment.manage",
            "attendance.view", "timetable.view", "timetable.manage", "exams.view", "results.view",
            "results.review", "results.approve", "results.publish", "finance.view",
            "messages.send", "announcements.create", "hr.leave.view", "hr.leave.approve", "hr.leave.request", "hr.payroll.view",
            "discipline.view", "discipline.create", "discipline.update", "discipline.resolve",
            "analytics.view", "materials.view", "materials.moderate", "assignments.view", "library.view", "library.policy", "inventory.view", "transport.view",
            "audit.view",
        ],
        "school_scoped": True,
    },
    "exam_officer": {
        "permissions": [
            "exams.view", "exams.create", "exams.update", "exams.schedule", "academics.view",
            "results.view", "results.review", "grading.manage", "analytics.view", "hr.leave.request",
            "library.view", "messages.send",
            "timetable.view",  # needed to schedule exams without clashing with the regular class timetable
        ],
        "school_scoped": True,
    },
    "hr_officer": {
        "permissions": [
            "staff.view", "staff.create", "staff.update", "academics.view",
            "hr.leave.view", "hr.leave.approve", "hr.payroll.manage", "hr.payroll.view", "hr.leave.request",
            "library.view", "messages.send",
        ],
        "school_scoped": True,
    },
    "librarian": {
        "permissions": ["library.view", "library.manage", "library.circulation", "academics.view", "students.view", "hr.leave.request", "messages.send"],
        "school_scoped": True,
    },
    "inventory_manager": {
        "permissions": ["inventory.view", "inventory.manage", "hr.leave.request", "library.view", "messages.send"],
        "school_scoped": True,
    },
    "transport_manager": {
        "permissions": ["transport.view", "transport.manage", "academics.view", "students.view", "hr.leave.request", "library.view", "messages.send"],
        "school_scoped": True,
    },
    "teacher": {
        "permissions": [
            "students.view", "attendance.view", "attendance.create", "timetable.view", "enrollment.view",
            "academics.view", "assignments.view", "assignments.create", "assignments.update", "assignments.grade",
            "assignments.delete",  # a teacher can create/update their own assignments, so delete is symmetric
            "materials.view", "materials.manage",
            "exams.view", "exams.mark", "results.view", "results.submit",
            "messages.send", "hr.leave.request",
            "discipline.view", "discipline.create", "library.view",
        ],
        "school_scoped": True,
    },
    "accountant": {
        "permissions": [
            "students.view", "parents.view", "finance.view", "finance.manage", "academics.view",
            "finance.payment.create", "finance.refund", "finance.expenses.manage", "messages.send", "hr.leave.request",
            "library.view",
        ],
        "school_scoped": True,
    },
    "student": {
        "permissions": [
            "assignments.view", "assignments.submit", "materials.view", "timetable.view", "academics.view",
            "attendance.view", "results.view", "exams.view", "finance.view", "messages.send", "library.view",
        ],
        "school_scoped": True,
    },
    "parent": {
        "permissions": [
            "assignments.view", "materials.view", "attendance.view", "results.view", "exams.view",
            "academics.view", "timetable.view", "finance.view", "messages.send",
        ],
        "school_scoped": True,
    },
}


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    code = db.Column(db.String(100), unique=True, nullable=False)  # e.g. "students.view"
    description = db.Column(db.String(255), nullable=True)


role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.String(36), db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.String(36), db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    # NULL school_id => platform-level role (e.g. super_admin) or a system
    # template role available to every school. Schools can also define
    # their own custom roles scoped to their own school_id.
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)  # e.g. "school_administrator"
    description = db.Column(db.String(255), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)  # seeded, not user-deletable

    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")

    __table_args__ = (db.UniqueConstraint("school_id", "name", name="uq_role_school_name"),)

    def permission_codes(self):
        return {p.code for p in self.permissions}


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.String(36), db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(db.Model, TimestampMixin):
    """
    A login account. NULL school_id = platform-level account (super admin).
    Every other user belongs to exactly one school. A parent with children
    at two different (participating) schools would need two accounts -
    cross-school identity merging is out of scope for phase 1.
    """

    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)

    email = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_email_verified = db.Column(db.Boolean, nullable=False, default=False)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    # Any token issued before this moment is rejected (set on password reset or change), so a
    # stolen or forgotten login stops working as soon as the password is changed.
    password_changed_at = db.Column(db.DateTime, nullable=True)

    roles = db.relationship("Role", secondary=user_roles, backref="users")

    __table_args__ = (
        db.UniqueConstraint("school_id", "email", name="uq_user_school_email"),
    )

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    def invalidate_sessions(self):
        """Make every token issued before now unusable (they carry the old token_version)."""
        self.password_changed_at = datetime.now(timezone.utc)

    def token_version(self):
        """"0" until the password is first changed or reset, then the change time in milliseconds.
        Every token carries this value; a token whose value no longer matches is dead."""
        if self.password_changed_at is None:
            return "0"
        moment = self.password_changed_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return str(int(moment.timestamp() * 1000))

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def all_permissions(self):
        perms = set()
        for role in self.roles:
            codes = role.permission_codes()
            if "*" in codes or getattr(role, "_all_permissions", False):
                return {"*"}
            perms |= codes
        return perms

    def has_permission(self, code):
        perms = self.all_permissions()
        return "*" in perms or code in perms

    def to_dict(self):
        return {
            "id": self.id,
            "school_id": self.school_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "photo_url": self.photo_url,
            "is_active": self.is_active,
            "roles": [r.name for r in self.roles],
        }


class PasswordResetToken(db.Model, TimestampMixin):
    """
    One-time token for forgot-password / reset-password (spec section 5).
    No email provider is wired up yet (see README), the token is created
    here and handed back to whatever sends it (email/SMS integration is a
    follow-up task), so the *mechanism* is real even though delivery isn't.
    """

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def hash_token(raw_token):
        return bcrypt.generate_password_hash(raw_token).decode("utf-8")

    def is_valid(self, raw_token):
        if self.used_at is not None:
            return False
        if datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc):
            return False
        return bcrypt.check_password_hash(self.token_hash, raw_token)

    @staticmethod
    def default_expiry():
        return datetime.now(timezone.utc) + timedelta(hours=1)


class RevokedToken(db.Model):
    """JWT blocklist entry (spec section 5: session management / logout).
    A logged-out or force-logged-out token's jti lands here; the JWT
    callback in app/__init__.py checks this table on every request."""

    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(36), primary_key=True)
    revoked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class UserSession(db.Model, TimestampMixin):
    """
    One row per issued refresh token, so a user (or an admin) can see
    active sessions and revoke a specific one (spec section 71: "Force
    logout", "View sessions"). Access tokens are short-lived (8h) and not
    tracked individually here, revoking the session's refresh token stops
    it from being renewed, which is the meaningful control point.
    """

    __tablename__ = "user_sessions"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_jti = db.Column(db.String(36), nullable=False, unique=True)
    user_agent = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "user_agent": self.user_agent, "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(), "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class EmailVerificationToken(db.Model, TimestampMixin):
    """Same one-time-token pattern as PasswordResetToken, for spec section 5's Email Verification."""

    __tablename__ = "email_verification_tokens"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def hash_token(raw_token):
        return bcrypt.generate_password_hash(raw_token).decode("utf-8")

    def is_valid(self, raw_token):
        if self.used_at is not None:
            return False
        if datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc):
            return False
        return bcrypt.check_password_hash(self.token_hash, raw_token)

    @staticmethod
    def default_expiry():
        return datetime.now(timezone.utc) + timedelta(hours=24)
