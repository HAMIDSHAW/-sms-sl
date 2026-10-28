import uuid
from datetime import datetime, timezone

from app.extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)


class TenantMixin:
    """
    Every school-owned row carries a school_id. This is the single most
    important rule in the whole schema: cross-school access must be
    impossible through normal application queries, so every query in every
    route MUST filter by the current user's school_id (see
    app/utils/tenancy.py: scoped_query()). Never trust a school_id passed in
    from the client, always take it from the authenticated user's token.
    """

    @staticmethod
    def school_fk():
        return db.Column(
            db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
        )
