from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

ANNOUNCEMENT_AUDIENCES = ["school", "teachers", "students", "parents", "staff", "class", "section"]
NOTIFICATION_TYPES = [
    "assignment_published", "assignment_graded", "attendance_absent", "exam_scheduled",
    "result_published", "fee_due", "payment_successful", "payment_failed", "announcement_published", "message_received",
    "leave_decided", "invoice_created", "period_starting_soon",
]


class Message(db.Model, TimestampMixin):
    """
    Direct message between two users (spec section 56). Who is ALLOWED to
    message whom is enforced in app/utils/messaging.py:can_message() at
    send time, not here, this table just stores whatever was already
    approved to be sent.
    """

    __tablename__ = "messages"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    sender_user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    subject = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)

    sender = db.relationship("User", foreign_keys=[sender_user_id], lazy="joined")

    def to_dict(self, viewer_id=None):
        # Identity is shown by default so a recipient always knows who
        # they're talking to, a sender has to explicitly opt into hiding
        # it (is_anonymous), and even then only the recipient's own copy is
        # masked; the sender still sees their own name on messages they
        # sent, in their own "sent" list.
        hide_identity = self.is_anonymous and viewer_id != self.sender_user_id
        return {
            "id": self.id, "sender_user_id": self.sender_user_id, "recipient_user_id": self.recipient_user_id,
            "sender_name": "Anonymous" if hide_identity else (self.sender.full_name if self.sender else None),
            "is_anonymous": self.is_anonymous,
            "subject": self.subject, "body": self.body,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat(),
        }


class Announcement(db.Model, TimestampMixin):
    """
    Broadcast to an audience (spec section 57): the whole school, a role
    group, or a specific class/section. Visibility is resolved per-caller
    in app/routes/announcements.py, not stored per-recipient, an
    announcement to 'school' is one row, not one row per user.
    """

    __tablename__ = "announcements"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    author_user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # audience_type stays for backward compatibility (older rows, and any
    # consumer that only reads a single value) and is kept as the first
    # entry of audience_types. audience_types is the real field going
    # forward and holds a comma-separated list so an announcement can
    # target e.g. "teachers,parents" in one post instead of requiring one
    # post per audience.
    audience_type = db.Column(db.String(20), nullable=False, default="school")
    audience_types = db.Column(db.String(120), nullable=False, default="school")
    audience_class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=True)
    audience_section_id = db.Column(db.String(36), db.ForeignKey("sections.id", ondelete="CASCADE"), nullable=True)

    def to_dict(self):
        types = [t for t in (self.audience_types or self.audience_type or "school").strip(",").split(",") if t]
        return {
            "id": self.id, "author_user_id": self.author_user_id, "title": self.title, "body": self.body,
            "audience_type": types[0] if types else "school", "audience_types": types,
            "audience_class_id": self.audience_class_id,
            "audience_section_id": self.audience_section_id, "created_at": self.created_at.isoformat(),
        }


class Notification(db.Model, TimestampMixin):
    """
    Per-user, event-triggered notification (spec section 58/90). Created
    by app/utils/notify.py helper calls from wherever the triggering event
    happens (e.g. a result being published), never hand-inserted from the
    frontend.
    """

    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.String(500), nullable=True)
    related_entity_type = db.Column(db.String(50), nullable=True)
    related_entity_id = db.Column(db.String(36), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id, "type": self.type, "title": self.title, "body": self.body,
            "related_entity_type": self.related_entity_type, "related_entity_id": self.related_entity_id,
            "is_read": self.is_read, "created_at": self.created_at.isoformat(),
        }
