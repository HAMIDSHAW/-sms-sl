from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

VEHICLE_STATUSES = ["active", "in_maintenance", "retired"]


class Driver(db.Model, TimestampMixin):
    """
    A driver record (spec section 9.11, 64). Kept separate from Staff
    rather than folded in, a driver isn't always a payrolled staff
    member (some schools contract this out), so `staff_id` is optional,
    not assumed.
    """

    __tablename__ = "drivers"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    full_name = db.Column(db.String(255), nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    license_number = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id, "staff_id": self.staff_id, "full_name": self.full_name,
            "photo_url": self.photo_url, "phone": self.phone, "license_number": self.license_number,
            "address": self.address, "is_active": self.is_active,
        }


class Vehicle(db.Model, TimestampMixin):
    """spec section 65."""

    __tablename__ = "vehicles"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    vehicle_number = db.Column(db.String(50), nullable=False)
    registration = db.Column(db.String(50), nullable=True)
    vehicle_type = db.Column(db.String(50), nullable=True)  # bus, van, etc.
    capacity = db.Column(db.Integer, nullable=True)
    driver_id = db.Column(db.String(36), db.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)

    insurance_expiry = db.Column(db.Date, nullable=True)
    next_maintenance_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")

    __table_args__ = (db.UniqueConstraint("school_id", "vehicle_number", name="uq_vehicle_school_number"),)

    def to_dict(self):
        return {
            "id": self.id, "vehicle_number": self.vehicle_number, "registration": self.registration,
            "vehicle_type": self.vehicle_type, "capacity": self.capacity, "driver_id": self.driver_id,
            "insurance_expiry": self.insurance_expiry.isoformat() if self.insurance_expiry else None,
            "next_maintenance_date": self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            "status": self.status,
        }


class TransportRoute(db.Model, TimestampMixin):
    """spec section 66. Named 'TransportRoute' to avoid clashing with Flask's own 'route' terminology in this codebase."""

    __tablename__ = "transport_routes"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    vehicle_id = db.Column(db.String(36), db.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    driver_id = db.Column(db.String(36), db.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
    departure_time = db.Column(db.Time, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    stops = db.relationship("RouteStop", back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.order_index")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "vehicle_id": self.vehicle_id, "driver_id": self.driver_id,
            "departure_time": self.departure_time.strftime("%H:%M") if self.departure_time else None,
            "is_active": self.is_active,
            "stops": [s.to_dict() for s in self.stops],
        }


class RouteStop(db.Model, TimestampMixin):
    __tablename__ = "route_stops"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = db.Column(db.String(36), db.ForeignKey("transport_routes.id", ondelete="CASCADE"), nullable=False)

    name = db.Column(db.String(255), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    arrival_time = db.Column(db.Time, nullable=True)

    route = db.relationship("TransportRoute", back_populates="stops")

    def to_dict(self):
        return {
            "id": self.id, "route_id": self.route_id, "name": self.name, "order_index": self.order_index,
            "arrival_time": self.arrival_time.strftime("%H:%M") if self.arrival_time else None,
        }


class TransportAssignment(db.Model, TimestampMixin):
    """Which route/stop a student uses (spec section 64: 'Student Assignments')."""

    __tablename__ = "transport_assignments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    route_id = db.Column(db.String(36), db.ForeignKey("transport_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id = db.Column(db.String(36), db.ForeignKey("route_stops.id", ondelete="SET NULL"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint("student_id", "route_id", name="uq_transport_assignment_student_route"),
    )

    def to_dict(self):
        from app.models import Student
        student = Student.query.get(self.student_id)
        return {
            "id": self.id, "student_id": self.student_id, "route_id": self.route_id,
            "stop_id": self.stop_id, "is_active": self.is_active,
            "student_name": student.full_name if student else None,
            "student_photo_url": student.photo_url if student else None,
        }
