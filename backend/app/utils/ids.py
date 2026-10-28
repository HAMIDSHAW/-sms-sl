from datetime import date

from app.extensions import db


def generate_student_number(school):
    """
    Generate the next student ID for a school using its configured format,
    e.g. "STU-2026-00001". Prevents duplicate IDs (spec section 102) by
    atomically incrementing the school's counter.
    """
    prefix = school.student_id_prefix or (school.short_name or "STU")
    year = date.today().year
    seq = school.next_student_seq
    school.next_student_seq = seq + 1
    db.session.add(school)

    fmt = school.student_id_format or "{prefix}-{year}-{seq:05d}"
    return fmt.format(prefix=prefix, year=year, seq=seq)
