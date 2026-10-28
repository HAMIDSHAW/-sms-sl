from datetime import datetime, date

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Driver, Vehicle, TransportRoute, RouteStop, TransportAssignment, Student
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query,
    linked_student_id, linked_guardian_children_ids,
)

bp = Blueprint("transport", __name__, url_prefix="/api/transport")


def _t(value):
    return datetime.strptime(value, "%H:%M").time() if value else None


def _d(value):
    return date.fromisoformat(value) if value else None


# --- Drivers -----------------------------------------------------------

@bp.get("/drivers")
@permission_required("transport.view")
def list_drivers():
    return jsonify([d.to_dict() for d in scoped_query(Driver).filter_by(is_active=True).all()])


@bp.get("/drivers/<driver_id>")
@permission_required("transport.view")
def get_driver(driver_id):
    driver = scoped_query(Driver).filter_by(id=driver_id).first_or_404()
    data = driver.to_dict()
    routes = TransportRoute.query.filter_by(school_id=current_school_id(), driver_id=driver.id, is_active=True).all()
    data["routes"] = [r.to_dict() for r in routes]
    return jsonify(data)


@bp.patch("/drivers/<driver_id>")
@permission_required("transport.manage")
def update_driver(driver_id):
    driver = scoped_query(Driver).filter_by(id=driver_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["full_name", "phone", "license_number", "address", "photo_url", "is_active"]:
        if field in data:
            setattr(driver, field, data[field])
    db.session.commit()
    return jsonify(driver.to_dict())


@bp.post("/drivers")
@permission_required("transport.manage")
def create_driver():
    data = request.get_json(silent=True) or {}
    if not data.get("full_name"):
        return jsonify({"error": "full_name is required"}), 400

    school_id = current_school_id()
    staff_id = data.get("staff_id")
    if staff_id:
        from app.models import Staff
        if not Staff.query.filter_by(id=staff_id, school_id=school_id).first():
            return jsonify({"error": "staff_id does not belong to this school"}), 404

    driver = Driver(
        school_id=school_id, staff_id=staff_id, full_name=data["full_name"],
        phone=data.get("phone"), license_number=data.get("license_number"),
        address=data.get("address"), photo_url=data.get("photo_url"),
    )
    db.session.add(driver)
    db.session.commit()
    return jsonify(driver.to_dict()), 201


# --- Vehicles ------------------------------------------------------------

@bp.get("/vehicles")
@permission_required("transport.view")
def list_vehicles():
    return jsonify([v.to_dict() for v in scoped_query(Vehicle).all()])


@bp.post("/vehicles")
@permission_required("transport.manage")
def create_vehicle():
    data = request.get_json(silent=True) or {}
    if not data.get("vehicle_number"):
        return jsonify({"error": "vehicle_number is required"}), 400

    school_id = current_school_id()
    driver_id = data.get("driver_id")
    if driver_id and not Driver.query.filter_by(id=driver_id, school_id=school_id).first():
        return jsonify({"error": "driver_id does not belong to this school"}), 404

    vehicle = Vehicle(
        school_id=school_id, vehicle_number=data["vehicle_number"], registration=data.get("registration"),
        vehicle_type=data.get("vehicle_type"), capacity=data.get("capacity"), driver_id=driver_id,
        insurance_expiry=_d(data.get("insurance_expiry")), next_maintenance_date=_d(data.get("next_maintenance_date")),
        status=data.get("status", "active"),
    )
    db.session.add(vehicle)
    db.session.commit()
    return jsonify(vehicle.to_dict()), 201


@bp.patch("/vehicles/<vehicle_id>")
@permission_required("transport.manage")
def update_vehicle(vehicle_id):
    vehicle = scoped_query(Vehicle).filter_by(id=vehicle_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["registration", "vehicle_type", "capacity", "driver_id", "status"]:
        if field in data:
            setattr(vehicle, field, data[field])
    if "insurance_expiry" in data:
        vehicle.insurance_expiry = _d(data["insurance_expiry"])
    if "next_maintenance_date" in data:
        vehicle.next_maintenance_date = _d(data["next_maintenance_date"])
    db.session.commit()
    return jsonify(vehicle.to_dict())


# --- Routes + Stops --------------------------------------------------------

@bp.get("/routes")
@permission_required("transport.view")
def list_routes():
    return jsonify([r.to_dict() for r in scoped_query(TransportRoute).filter_by(is_active=True).all()])


@bp.post("/routes")
@permission_required("transport.manage")
def create_route():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    school_id = current_school_id()
    for field, model in [("vehicle_id", Vehicle), ("driver_id", Driver)]:
        value = data.get(field)
        if value and not model.query.filter_by(id=value, school_id=school_id).first():
            return jsonify({"error": f"{field} does not belong to this school"}), 404

    route = TransportRoute(
        school_id=school_id, name=data["name"], vehicle_id=data.get("vehicle_id"),
        driver_id=data.get("driver_id"), departure_time=_t(data.get("departure_time")),
    )
    db.session.add(route)
    db.session.commit()
    return jsonify(route.to_dict()), 201


@bp.post("/routes/<route_id>/stops")
@permission_required("transport.manage")
def add_stop(route_id):
    route = scoped_query(TransportRoute).filter_by(id=route_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    stop = RouteStop(
        school_id=current_school_id(), route_id=route.id, name=data["name"],
        order_index=data.get("order_index", len(route.stops)), arrival_time=_t(data.get("arrival_time")),
    )
    db.session.add(stop)
    db.session.commit()
    return jsonify(stop.to_dict()), 201


# --- Student assignments (spec section 64) ----------------------------

@bp.get("/assignments")
@permission_required("transport.view")
def list_assignments():
    """Transport manager sees everyone (filterable). A student/guardian sees only their own (or their child's)."""
    query = scoped_query(TransportAssignment)

    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()

    if student_scope:
        query = query.filter(TransportAssignment.student_id == student_scope)
    elif guardian_children:
        query = query.filter(TransportAssignment.student_id.in_(guardian_children))
    else:
        route_id = request.args.get("route_id")
        if route_id:
            query = query.filter_by(route_id=route_id)

    return jsonify([a.to_dict() for a in query.all()])


@bp.post("/assignments")
@permission_required("transport.manage")
def create_assignment():
    data = request.get_json(silent=True) or {}
    required = ["student_id", "route_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school_id = current_school_id()
    student = Student.query.filter_by(id=data["student_id"], school_id=school_id).first()
    if not student:
        return jsonify({"error": "student_id does not belong to this school"}), 404

    route = TransportRoute.query.filter_by(id=data["route_id"], school_id=school_id).first()
    if not route:
        return jsonify({"error": "route_id does not belong to this school"}), 404

    stop_id = data.get("stop_id")
    if stop_id and not RouteStop.query.filter_by(id=stop_id, route_id=route.id).first():
        return jsonify({"error": "stop_id does not belong to this route"}), 404

    existing = TransportAssignment.query.filter_by(student_id=student.id, route_id=route.id).first()
    if existing:
        return jsonify({"error": "Student is already assigned to this route"}), 400

    assignment = TransportAssignment(
        school_id=school_id, student_id=student.id, route_id=route.id, stop_id=stop_id,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment.to_dict()), 201
