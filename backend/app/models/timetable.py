from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class TimetableEntry(db.Model, TimestampMixin):
    """
    One scheduled period (spec section 33). Conflict detection (section 34)
    lives in app/routes/timetable.py rather than here, since it needs to
    query sibling rows before allowing a save.
    """

    __tablename__ = "timetable_entries"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="CASCADE"), nullable=True)
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)  # teacher

    day_of_week = db.Column(db.String(10), nullable=False)  # monday..sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(100), nullable=True)

    subject = db.relationship("Subject", lazy="joined")
    staff = db.relationship("Staff", lazy="joined")
    school_class = db.relationship("SchoolClass", lazy="joined")

    def to_dict(self):
        # Denormalized names so the frontend never has to cross-reference a
        # separate subjects/staff list it might not have permission to fetch
        # (e.g. a teacher or student viewing a class timetable has no
        # staff.view permission, so a client-side staff lookup silently
        # comes back empty and used to render as "N/A").
        subject = getattr(self, "subject", None)
        staff = getattr(self, "staff", None)
        klass = getattr(self, "school_class", None)
        return {
            "id": self.id,
            "academic_year_id": self.academic_year_id,
            "class_id": self.class_id,
            "class_name": klass.name if klass else None,
            "section_id": self.section_id,
            "subject_id": self.subject_id,
            "subject_name": subject.name if subject else None,
            "staff_id": self.staff_id,
            "staff_name": staff.full_name if staff else None,
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "room": self.room,
        }
