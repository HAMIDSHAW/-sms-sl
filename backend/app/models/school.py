from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin


class School(db.Model, TimestampMixin):
    """
    The tenant root. Everything else in the system hangs off a school_id.

    Every field here is admin-editable after creation via the school setup
    wizard / settings screen (name, logo, currency, terminology, etc.) -
    nothing about a specific school is hard-coded anywhere else in the app.
    """

    __tablename__ = "schools"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)

    # --- Identity (step 1 of setup wizard) ---
    name = db.Column(db.String(255), nullable=False)
    short_name = db.Column(db.String(50), nullable=True)  # used in generated IDs, e.g. "KGSS"
    logo_url = db.Column(db.String(500), nullable=True)
    motto = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    address = db.Column(db.String(500), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    district = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=False, default="Sierra Leone")
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)

    # --- Localization ---
    currency = db.Column(db.String(10), nullable=False, default="SLE")
    timezone = db.Column(db.String(64), nullable=False, default="Africa/Freetown")
    language = db.Column(db.String(10), nullable=False, default="en")

    # --- Terminology overrides (schools name things differently) ---
    # e.g. {"class": "Grade", "section": "Stream"}, falls back to defaults
    # in the UI layer if a school hasn't customized a given term.
    terminology = db.Column(db.JSON, nullable=True)

    # --- Student ID generation rule ---
    student_id_prefix = db.Column(db.String(20), nullable=True)  # e.g. "STU"
    student_id_format = db.Column(db.String(50), nullable=False, default="{prefix}-{year}-{seq:05d}")
    next_student_seq = db.Column(db.Integer, nullable=False, default=1)

    # --- Library policy (set by the principal; a book can override both) ---
    library_loan_days = db.Column(db.Integer, nullable=True)
    library_daily_fine = db.Column(db.Float, nullable=True)

    # --- Lifecycle ---
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    setup_completed = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<School {self.short_name or self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "logo_url": self.logo_url,
            "motto": self.motto,
            "description": self.description,
            "address": self.address,
            "city": self.city,
            "district": self.district,
            "country": self.country,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "currency": self.currency,
            "timezone": self.timezone,
            "language": self.language,
            "terminology": self.terminology or {},
            "is_active": self.is_active,
            "setup_completed": self.setup_completed,
        }
