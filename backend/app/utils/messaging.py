"""
Who can message whom (spec section 56: "Messages must respect
permissions. A teacher should not automatically be able to privately
message every parent in the school.").

Rules, in order:
1. A wildcard-permission account (school_owner, school_administrator) can
   message anyone in the school, they're the school's own operators.
2. Staff can always message other staff (ordinary internal coordination).
3. A student or guardian can always message staff, a family reaching out
   to the school is never restricted.
4. Staff can message a student or guardian ONLY if that student is
   currently enrolled in a class the staff member has a TeacherAssignment
   for. This is the actual guardrail: it ties "can this teacher message
   this parent" to "does this teacher actually teach this parent's child"
   rather than leaving it open by default.
5. Anything else (student-to-student, guardian-to-guardian, guardian to
   an unrelated student) is refused.
"""

from app.models import User, Student, Guardian, StudentGuardian, TeacherAssignment, Enrollment, Staff


def _is_staff_account(user):
    from app.models.people import Staff as StaffModel
    return StaffModel.query.filter_by(user_id=user.id, school_id=user.school_id).first() is not None


def _linked_student(user):
    return Student.query.filter_by(user_id=user.id, school_id=user.school_id).first()


def _linked_guardian(user):
    return Guardian.query.filter_by(user_id=user.id, school_id=user.school_id).first()


def _linked_staff(user):
    return Staff.query.filter_by(user_id=user.id, school_id=user.school_id).first()


def _teacher_teaches_student(staff_record, student_id):
    enrollment = Enrollment.query.filter_by(student_id=student_id, status="active").first()
    if not enrollment:
        return False
    return TeacherAssignment.query.filter_by(
        staff_id=staff_record.id, class_id=enrollment.class_id
    ).first() is not None


def can_message(sender: User, recipient: User) -> bool:
    if sender.id == recipient.id:
        return False
    if sender.school_id != recipient.school_id:
        return False

    if sender.has_permission("*"):
        return True

    sender_staff = _linked_staff(sender)
    recipient_staff = _linked_staff(recipient)

    # staff <-> staff
    if sender_staff and recipient_staff:
        return True

    # student/guardian -> staff: always allowed
    if recipient_staff and (_linked_student(sender) or _linked_guardian(sender)):
        return True

    # staff -> student/guardian: only if the staff member actually teaches that student
    if sender_staff:
        recipient_student = _linked_student(recipient)
        if recipient_student:
            return _teacher_teaches_student(sender_staff, recipient_student.id)

        recipient_guardian = _linked_guardian(recipient)
        if recipient_guardian:
            child_ids = [sg.student_id for sg in recipient_guardian.students]
            return any(_teacher_teaches_student(sender_staff, cid) for cid in child_ids)

    return False
