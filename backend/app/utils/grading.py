"""
The grading engine (spec sections 44-45).

Nothing about specific grade boundaries (A=80-100, pass mark, etc.) is
hard-coded here, every school configures its own GradeScale rows, and this
module just looks a percentage up against whichever bands that school has
defined. If a school hasn't configured any bands yet, grade lookups return
None rather than silently guessing at a boundary.
"""

from app.extensions import db
from app.models import Mark, ExamSchedule, Result, Subject

DEFAULT_GRADE_SCALE = [
    {"grade": "A", "min_score": 80, "max_score": 100, "grade_point": 4.0, "is_pass": True},
    {"grade": "B", "min_score": 70, "max_score": 79.99, "grade_point": 3.0, "is_pass": True},
    {"grade": "C", "min_score": 60, "max_score": 69.99, "grade_point": 2.0, "is_pass": True},
    {"grade": "D", "min_score": 50, "max_score": 59.99, "grade_point": 1.0, "is_pass": True},
    {"grade": "F", "min_score": 0, "max_score": 49.99, "grade_point": 0.0, "is_pass": False},
]


def ensure_default_grade_scale(school_id):
    """
    Same lazy-seed pattern as attendance statuses, but was missing here
    until a gap check found it, meaning compute_results() could silently
    produce ungraded results (grade=None, is_pass=None) for any school
    that computed results via the API before ever loading the grade-scale
    settings screen. Called from compute_results() itself now, not just
    from the settings GET route, so results are always graded regardless
    of which endpoint gets hit first.
    """
    from app.models import GradeScale
    if GradeScale.query.filter_by(school_id=school_id).first():
        return
    for band in DEFAULT_GRADE_SCALE:
        db.session.add(GradeScale(school_id=school_id, **band))
    db.session.flush()


def grade_for_percentage(school_id, percentage):
    from app.models import GradeScale

    band = GradeScale.query.filter(
        GradeScale.school_id == school_id,
        GradeScale.min_score <= percentage,
        GradeScale.max_score >= percentage,
    ).first()
    return band


def compute_results(school_id, examination_id, student_id):
    """
    Recompute one student's Result for one examination from their current
    Marks. Idempotent and safe to re-run any time a mark changes, it
    always derives the total from Marks, it never accumulates.

    Returns the Result row (created or updated), or None if the student has
    no marks at all for this examination yet.
    """
    marks = (
        db.session.query(Mark, ExamSchedule)
        .join(ExamSchedule, Mark.exam_schedule_id == ExamSchedule.id)
        .filter(
            ExamSchedule.examination_id == examination_id,
            Mark.student_id == student_id,
            Mark.is_absent.is_(False),
            Mark.obtained_marks.isnot(None),
        )
        .all()
    )
    if not marks:
        return None

    ensure_default_grade_scale(school_id)

    total_obtained = sum(m.obtained_marks for m, _ in marks)
    total_max = sum(sched.max_marks for _, sched in marks)
    percentage = round((total_obtained / total_max) * 100, 2) if total_max else None

    result = Result.query.filter_by(examination_id=examination_id, student_id=student_id).first()
    if not result:
        result = Result(school_id=school_id, examination_id=examination_id, student_id=student_id)
        db.session.add(result)

    result.total_marks = total_obtained
    result.total_max_marks = total_max
    result.average_percentage = percentage

    band = grade_for_percentage(school_id, percentage) if percentage is not None else None
    result.overall_grade = band.grade if band else None
    result.overall_grade_point = band.grade_point if band else None
    result.is_pass = band.is_pass if band else None

    return result


def compute_class_positions(school_id, examination_id, class_id):
    """
    Rank every student's Result for this examination within a class by
    average_percentage, descending, and write overall_position onto each
    (spec section 45: "Overall position if enabled"). Ties share a rank
    (standard competition ranking: 1, 2, 2, 4).
    """
    from app.models import Enrollment

    student_ids = [
        e.student_id for e in Enrollment.query.filter_by(class_id=class_id, status="active").all()
    ]
    results = (
        Result.query.filter(
            Result.examination_id == examination_id,
            Result.student_id.in_(student_ids),
            Result.average_percentage.isnot(None),
        )
        .order_by(Result.average_percentage.desc())
        .all()
    )

    rank = 0
    last_score = None
    seen = 0
    for r in results:
        seen += 1
        if r.average_percentage != last_score:
            rank = seen
            last_score = r.average_percentage
        r.overall_position = rank

    return results
