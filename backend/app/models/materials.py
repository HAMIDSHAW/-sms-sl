from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

MATERIAL_TYPES = ["pdf", "docx", "pptx", "xlsx", "image", "video", "link"]


class LearningMaterial(db.Model, TimestampMixin):
    """Teacher-uploaded resources for a class/subject (spec section 39)."""

    __tablename__ = "learning_materials"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)  # uploader
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    material_type = db.Column(db.String(20), nullable=False, default="pdf")
    file_url = db.Column(db.String(500), nullable=True)
    external_link = db.Column(db.String(500), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        from app.models import Staff, Subject, SchoolClass
        uploader = Staff.query.get(self.staff_id)
        subject = Subject.query.get(self.subject_id)
        school_class = SchoolClass.query.get(self.class_id)
        return {
            "staff_name": uploader.full_name if uploader else None,
            "subject_name": subject.name if subject else None,
            "class_name": school_class.name if school_class else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "id": self.id, "subject_id": self.subject_id, "class_id": self.class_id,
            "section_id": self.section_id, "staff_id": self.staff_id,
            "title": self.title, "description": self.description, "category": self.category,
            "material_type": self.material_type, "file_url": self.file_url,
            "external_link": self.external_link, "is_active": self.is_active,
        }
