-- =====================================================================
-- School Management Platform, Phase 1 schema (SQL Server / T-SQL)
-- Run this directly in SSMS against a fresh database if you'd rather not
-- rely on db.create_all() / Alembic. Matches app/models/*.py exactly.
-- Updated October 2026: added every column the models gained since this file was first
-- written (payroll salary, library fines, class master, assignment ownership and more).
-- Already have a database made from an older copy of this file? Run upgrade_2026_10.sql on it.
-- Two foreign keys (classes.class_master_staff_id, assignments.created_by_user_id) deliberately use
-- the default NO ACTION rather than ON DELETE SET NULL, because SQL Server refuses a second
-- cascading path to a table that already cascades from schools. Staff and users are never hard
-- deleted by the app (staff are archived, accounts are deactivated), so nothing is lost by this.
-- =====================================================================

IF DB_ID('SchoolPlatform') IS NULL
BEGIN
    CREATE DATABASE SchoolPlatform;
END
GO
USE SchoolPlatform;
GO

-- ---------------------------------------------------------------------
-- Tenant root
-- ---------------------------------------------------------------------
CREATE TABLE schools (
    id                  CHAR(36)        NOT NULL PRIMARY KEY,
    name                NVARCHAR(255)   NOT NULL,
    short_name          NVARCHAR(50)    NULL,
    logo_url            NVARCHAR(500)   NULL,
    motto               NVARCHAR(255)   NULL,
    description         NVARCHAR(MAX)   NULL,
    address             NVARCHAR(500)   NULL,
    city                NVARCHAR(120)   NULL,
    district            NVARCHAR(120)   NULL,
    country             NVARCHAR(120)   NOT NULL DEFAULT 'Sierra Leone',
    phone               NVARCHAR(50)    NULL,
    email               NVARCHAR(255)   NULL,
    website             NVARCHAR(255)   NULL,
    currency            NVARCHAR(10)    NOT NULL DEFAULT 'SLE',
    timezone            NVARCHAR(64)    NOT NULL DEFAULT 'Africa/Freetown',
    language            NVARCHAR(10)    NOT NULL DEFAULT 'en',
    terminology         NVARCHAR(MAX)   NULL,      -- JSON
    student_id_prefix   NVARCHAR(20)    NULL,
    student_id_format   NVARCHAR(50)    NOT NULL DEFAULT '{prefix}-{year}-{seq:05d}',
    next_student_seq    INT             NOT NULL DEFAULT 1,
    is_active           BIT             NOT NULL DEFAULT 1,
    setup_completed     BIT             NOT NULL DEFAULT 0,
    library_loan_days       INT NULL,
    library_daily_fine      FLOAT NULL,
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ---------------------------------------------------------------------
-- RBAC
-- ---------------------------------------------------------------------
CREATE TABLE permissions (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    code        NVARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(255) NULL
);
GO

CREATE TABLE roles (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    school_id   CHAR(36)      NULL REFERENCES schools(id) ON DELETE CASCADE,
    name        NVARCHAR(100) NOT NULL,
    description NVARCHAR(255) NULL,
    is_system   BIT           NOT NULL DEFAULT 0,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_role_school_name UNIQUE (school_id, name)
);
GO

CREATE TABLE role_permissions (
    role_id       CHAR(36) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id CHAR(36) NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
GO

CREATE TABLE users (
    id                    CHAR(36)      NOT NULL PRIMARY KEY,
    school_id             CHAR(36)      NULL REFERENCES schools(id) ON DELETE CASCADE,
    email                 NVARCHAR(255) NOT NULL,
    username              NVARCHAR(120) NULL,
    phone                 NVARCHAR(50)  NULL,
    password_hash         NVARCHAR(255) NOT NULL,
    first_name            NVARCHAR(120) NOT NULL,
    last_name             NVARCHAR(120) NOT NULL,
    photo_url             NVARCHAR(500) NULL,
    is_active             BIT           NOT NULL DEFAULT 1,
    is_email_verified     BIT           NOT NULL DEFAULT 0,
    must_change_password  BIT           NOT NULL DEFAULT 0,
    last_login_at         DATETIME2     NULL,
    password_changed_at     DATETIME2 NULL,
    created_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_user_school_email UNIQUE (school_id, email)
);
GO

CREATE TABLE user_roles (
    user_id CHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id CHAR(36) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
GO

-- ---------------------------------------------------------------------
-- Academic structure
-- ---------------------------------------------------------------------
CREATE TABLE academic_years (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    school_id   CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name        NVARCHAR(50)  NOT NULL,
    start_date  DATE          NOT NULL,
    end_date    DATE          NOT NULL,
    is_current  BIT           NOT NULL DEFAULT 0,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_year_school_name UNIQUE (school_id, name)
);
GO

CREATE TABLE terms (
    id                CHAR(36)     NOT NULL PRIMARY KEY,
    school_id         CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    academic_year_id  CHAR(36)     NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name              NVARCHAR(50) NOT NULL,
    start_date        DATE         NOT NULL,
    end_date          DATE         NOT NULL,
    is_current        BIT          NOT NULL DEFAULT 0,
    created_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE classes (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name        NVARCHAR(80) NOT NULL,
    order_index INT          NOT NULL DEFAULT 0,
    is_active   BIT          NOT NULL DEFAULT 1,
    class_master_staff_id   CHAR(36) NULL REFERENCES staff(id),
    created_at  DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_class_school_name UNIQUE (school_id, name)
);
GO

CREATE TABLE staff (
    id               CHAR(36)      NOT NULL PRIMARY KEY,
    school_id        CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    user_id          CHAR(36)      NULL REFERENCES users(id) ON DELETE SET NULL,
    employee_number  NVARCHAR(50)  NOT NULL,
    first_name       NVARCHAR(120) NOT NULL,
    last_name        NVARCHAR(120) NOT NULL,
    photo_url        NVARCHAR(500) NULL,
    phone            NVARCHAR(50)  NULL,
    email            NVARCHAR(255) NULL,
    staff_type       NVARCHAR(30)  NOT NULL DEFAULT 'teacher',
    department       NVARCHAR(120) NULL,
    position         NVARCHAR(120) NULL,
    qualifications   NVARCHAR(MAX) NULL,
    employment_date  DATE          NULL,
    status           NVARCHAR(30)  NOT NULL DEFAULT 'active',
    is_deleted       BIT           NOT NULL DEFAULT 0,
    deleted_at       DATETIME2     NULL,
    title                   NVARCHAR(10) NULL,
    address                 NVARCHAR(500) NULL,
    base_salary             FLOAT NULL,
    created_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_staff_school_number UNIQUE (school_id, employee_number)
);
GO

CREATE TABLE sections (
    id                      CHAR(36)     NOT NULL PRIMARY KEY,
    school_id               CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    class_id                CHAR(36)     NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    name                    NVARCHAR(50) NOT NULL,
    capacity                INT          NULL,
    class_teacher_staff_id  CHAR(36)     NULL REFERENCES staff(id) ON DELETE SET NULL,
    created_at              DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at              DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_section_class_name UNIQUE (class_id, name)
);
GO

CREATE TABLE subjects (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    school_id   CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name        NVARCHAR(120) NOT NULL,
    code        NVARCHAR(30)  NULL,
    department  NVARCHAR(120) NULL,
    max_marks   INT           NOT NULL DEFAULT 100,
    pass_mark   INT           NOT NULL DEFAULT 50,
    is_active   BIT           NOT NULL DEFAULT 1,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_subject_school_code UNIQUE (school_id, code)
);
GO

CREATE TABLE teacher_assignments (
    id                CHAR(36) NOT NULL PRIMARY KEY,
    school_id         CHAR(36) NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    staff_id          CHAR(36) NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    subject_id        CHAR(36) NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id          CHAR(36) NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id        CHAR(36) NULL REFERENCES sections(id) ON DELETE CASCADE,
    academic_year_id  CHAR(36) NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    created_at        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_teacher_assignment_no_dupe UNIQUE (staff_id, subject_id, class_id, section_id, academic_year_id)
);
GO

-- ---------------------------------------------------------------------
-- People: students, guardians
-- ---------------------------------------------------------------------
CREATE TABLE students (
    id                       CHAR(36)      NOT NULL PRIMARY KEY,
    school_id                CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_number           NVARCHAR(50)  NOT NULL,
    user_id                  CHAR(36)      NULL REFERENCES users(id) ON DELETE SET NULL,
    first_name               NVARCHAR(120) NOT NULL,
    middle_name              NVARCHAR(120) NULL,
    last_name                NVARCHAR(120) NOT NULL,
    photo_url                NVARCHAR(500) NULL,
    date_of_birth            DATE          NULL,
    gender                   NVARCHAR(20)  NULL,
    nationality              NVARCHAR(80)  NULL,
    address                  NVARCHAR(500) NULL,
    phone                    NVARCHAR(50)  NULL,
    email                    NVARCHAR(255) NULL,
    admission_date           DATE          NULL,
    admission_number         NVARCHAR(50)  NULL,
    emergency_contact_name   NVARCHAR(120) NULL,
    emergency_contact_phone  NVARCHAR(50)  NULL,
    status                   NVARCHAR(30)  NOT NULL DEFAULT 'active',
    custom_fields            NVARCHAR(MAX) NULL,   -- JSON
    is_deleted               BIT           NOT NULL DEFAULT 0,
    deleted_at               DATETIME2     NULL,
    created_at               DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at               DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_student_school_number UNIQUE (school_id, student_number)
);
GO

CREATE TABLE guardians (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    school_id   CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    user_id     CHAR(36)      NULL REFERENCES users(id) ON DELETE SET NULL,
    first_name  NVARCHAR(120) NOT NULL,
    last_name   NVARCHAR(120) NOT NULL,
    photo_url   NVARCHAR(500) NULL,
    phone       NVARCHAR(50)  NULL,
    email       NVARCHAR(255) NULL,
    address     NVARCHAR(500) NULL,
    occupation  NVARCHAR(120) NULL,
    is_active   BIT           NOT NULL DEFAULT 1,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE student_guardians (
    student_id            CHAR(36)     NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    guardian_id            CHAR(36)     NOT NULL REFERENCES guardians(id) ON DELETE CASCADE,
    relationship_type      NVARCHAR(50) NOT NULL DEFAULT 'parent',
    is_primary_contact     BIT          NOT NULL DEFAULT 0,
    is_emergency_contact   BIT          NOT NULL DEFAULT 0,
    can_pickup             BIT          NOT NULL DEFAULT 1,
    PRIMARY KEY (student_id, guardian_id)
);
GO

CREATE TABLE enrollments (
    id                CHAR(36)     NOT NULL PRIMARY KEY,
    school_id         CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id        CHAR(36)     NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    academic_year_id  CHAR(36)     NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    class_id          CHAR(36)     NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id        CHAR(36)     NULL REFERENCES sections(id) ON DELETE SET NULL,
    enrollment_date   DATE         NOT NULL,
    status            NVARCHAR(30) NOT NULL DEFAULT 'active',
    created_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_enrollment_student_year UNIQUE (student_id, academic_year_id)
);
GO

-- ---------------------------------------------------------------------
-- Indexes on frequently queried tenant-scoped columns (spec section 97)
-- ---------------------------------------------------------------------
CREATE INDEX ix_students_school ON students(school_id);
CREATE INDEX ix_staff_school ON staff(school_id);
CREATE INDEX ix_guardians_school ON guardians(school_id);
CREATE INDEX ix_users_school ON users(school_id);
CREATE INDEX ix_enrollments_school ON enrollments(school_id);
CREATE INDEX ix_enrollments_class ON enrollments(class_id);
GO

-- ---------------------------------------------------------------------
-- Phase 2: Attendance
-- ---------------------------------------------------------------------
CREATE TABLE attendance_statuses (
    id                 CHAR(36)     NOT NULL PRIMARY KEY,
    school_id          CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    code               NVARCHAR(30) NOT NULL,
    label              NVARCHAR(50) NOT NULL,
    counts_as_present  BIT          NOT NULL DEFAULT 1,
    is_active          BIT          NOT NULL DEFAULT 1,
    created_at         DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at         DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_attendance_status_school_code UNIQUE (school_id, code)
);
GO

CREATE TABLE attendance (
    id                   CHAR(36)  NOT NULL PRIMARY KEY,
    school_id            CHAR(36)  NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id           CHAR(36)  NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id             CHAR(36)  NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id           CHAR(36)  NULL REFERENCES sections(id) ON DELETE SET NULL,
    subject_id           CHAR(36)  NULL REFERENCES subjects(id) ON DELETE SET NULL,
    academic_year_id     CHAR(36)  NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id              CHAR(36)  NULL REFERENCES terms(id) ON DELETE SET NULL,
    date                 DATE      NOT NULL,
    status_id            CHAR(36)  NOT NULL REFERENCES attendance_statuses(id),
    marked_by_staff_id   CHAR(36)  NULL REFERENCES staff(id) ON DELETE SET NULL,
    note                 NVARCHAR(500) NULL,
    created_at           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_attendance_student_date_subject UNIQUE (student_id, date, subject_id)
);
GO
CREATE INDEX ix_attendance_school ON attendance(school_id);
CREATE INDEX ix_attendance_class_date ON attendance(class_id, date);
GO

-- ---------------------------------------------------------------------
-- Phase 2: Timetable
-- ---------------------------------------------------------------------
CREATE TABLE timetable_entries (
    id                CHAR(36)     NOT NULL PRIMARY KEY,
    school_id         CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    academic_year_id  CHAR(36)     NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    class_id          CHAR(36)     NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id        CHAR(36)     NULL REFERENCES sections(id) ON DELETE CASCADE,
    subject_id        CHAR(36)     NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    staff_id          CHAR(36)     NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    day_of_week       NVARCHAR(10) NOT NULL,
    start_time        TIME         NOT NULL,
    end_time          TIME         NOT NULL,
    room              NVARCHAR(100) NULL,
    created_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_timetable_school ON timetable_entries(school_id);
CREATE INDEX ix_timetable_staff_day ON timetable_entries(staff_id, day_of_week);
GO

-- ---------------------------------------------------------------------
-- Phase 1 gap fix: password reset tokens
-- ---------------------------------------------------------------------
CREATE TABLE password_reset_tokens (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    user_id     CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  NVARCHAR(255) NOT NULL,
    expires_at  DATETIME2     NOT NULL,
    used_at     DATETIME2     NULL,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ---------------------------------------------------------------------
-- Phase 3: Assignments + Submissions
-- ---------------------------------------------------------------------
CREATE TABLE assignments (
    id                 CHAR(36)      NOT NULL PRIMARY KEY,
    school_id          CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    subject_id         CHAR(36)      NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id           CHAR(36)      NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id         CHAR(36)      NULL REFERENCES sections(id) ON DELETE SET NULL,
    staff_id           CHAR(36)      NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    academic_year_id   CHAR(36)      NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id            CHAR(36)      NULL REFERENCES terms(id) ON DELETE SET NULL,
    title              NVARCHAR(255) NOT NULL,
    description        NVARCHAR(MAX) NULL,
    instructions       NVARCHAR(MAX) NULL,
    start_date         DATE          NULL,
    due_date           DATE          NOT NULL,
    max_marks          INT           NOT NULL DEFAULT 100,
    attachment_url     NVARCHAR(500) NULL,
    submission_type    NVARCHAR(30)  NOT NULL DEFAULT 'file',
    status             NVARCHAR(20)  NOT NULL DEFAULT 'draft',
    created_by_user_id      CHAR(36) NULL REFERENCES users(id),
    original_due_date       DATE NULL,
    created_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_assignments_school ON assignments(school_id);
CREATE INDEX ix_assignments_class ON assignments(class_id, status);
GO

CREATE TABLE assignment_submissions (
    id                   CHAR(36)      NOT NULL PRIMARY KEY,
    school_id            CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    assignment_id        CHAR(36)      NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id           CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    submitted_at         DATETIME2     NULL,
    content_text         NVARCHAR(MAX) NULL,
    attachment_url       NVARCHAR(500) NULL,
    marks_obtained       INT           NULL,
    feedback             NVARCHAR(MAX) NULL,
    graded_by_staff_id   CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    graded_at            DATETIME2     NULL,
    status               NVARCHAR(20)  NOT NULL DEFAULT 'not_submitted',
    created_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_submission_assignment_student UNIQUE (assignment_id, student_id)
);
GO
CREATE INDEX ix_submissions_school ON assignment_submissions(school_id);
GO

-- ---------------------------------------------------------------------
-- Phase 3: Learning Materials
-- ---------------------------------------------------------------------
CREATE TABLE learning_materials (
    id                 CHAR(36)      NOT NULL PRIMARY KEY,
    school_id          CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    subject_id         CHAR(36)      NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id           CHAR(36)      NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id         CHAR(36)      NULL REFERENCES sections(id) ON DELETE SET NULL,
    staff_id           CHAR(36)      NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    academic_year_id   CHAR(36)      NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    title              NVARCHAR(255) NOT NULL,
    description        NVARCHAR(MAX) NULL,
    category           NVARCHAR(100) NULL,
    material_type      NVARCHAR(20)  NOT NULL DEFAULT 'pdf',
    file_url           NVARCHAR(500) NULL,
    external_link      NVARCHAR(500) NULL,
    is_active          BIT           NOT NULL DEFAULT 1,
    created_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_materials_school ON learning_materials(school_id);
CREATE INDEX ix_materials_class ON learning_materials(class_id);
GO

-- ---------------------------------------------------------------------
-- Phase 1-3 gap fixes: session management, audit logs, email verification
-- ---------------------------------------------------------------------
CREATE TABLE revoked_tokens (
    jti         CHAR(36)  NOT NULL PRIMARY KEY,
    revoked_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE user_sessions (
    id           CHAR(36)      NOT NULL PRIMARY KEY,
    user_id      CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_jti  CHAR(36)      NOT NULL UNIQUE,
    user_agent   NVARCHAR(255) NULL,
    ip_address   NVARCHAR(64)  NULL,
    revoked_at   DATETIME2     NULL,
    created_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_sessions_user ON user_sessions(user_id);
GO

CREATE TABLE email_verification_tokens (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    user_id     CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  NVARCHAR(255) NOT NULL,
    expires_at  DATETIME2     NOT NULL,
    used_at     DATETIME2     NULL,
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE audit_logs (
    id            CHAR(36)      NOT NULL PRIMARY KEY,
    school_id     CHAR(36)      NULL REFERENCES schools(id) ON DELETE CASCADE,
    user_id       CHAR(36)      NULL REFERENCES users(id) ON DELETE SET NULL,
    action        NVARCHAR(100) NOT NULL,
    module        NVARCHAR(50)  NOT NULL,
    entity_type   NVARCHAR(50)  NULL,
    entity_id     CHAR(36)      NULL,
    before_value  NVARCHAR(MAX) NULL,  -- JSON
    after_value   NVARCHAR(MAX) NULL,  -- JSON
    ip_address    NVARCHAR(64)  NULL,
    created_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_audit_school ON audit_logs(school_id);
CREATE INDEX ix_audit_entity ON audit_logs(entity_type, entity_id);
GO

-- ---------------------------------------------------------------------
-- Phase 4: Exams, Grading, Marks, Results
-- ---------------------------------------------------------------------
CREATE TABLE examinations (
    id                CHAR(36)      NOT NULL PRIMARY KEY,
    school_id         CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name              NVARCHAR(255) NOT NULL,
    academic_year_id  CHAR(36)      NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id           CHAR(36)      NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    start_date        DATE          NOT NULL,
    end_date          DATE          NOT NULL,
    instructions      NVARCHAR(MAX) NULL,
    status            NVARCHAR(20)  NOT NULL DEFAULT 'draft',
    created_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_examinations_school ON examinations(school_id);
GO

CREATE TABLE exam_schedules (
    id                    CHAR(36)      NOT NULL PRIMARY KEY,
    school_id             CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    examination_id        CHAR(36)      NOT NULL REFERENCES examinations(id) ON DELETE CASCADE,
    subject_id            CHAR(36)      NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id              CHAR(36)      NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    section_id            CHAR(36)      NULL REFERENCES sections(id) ON DELETE SET NULL,
    date                  DATE          NOT NULL,
    start_time            TIME          NOT NULL,
    end_time              TIME          NOT NULL,
    room                  NVARCHAR(100) NULL,
    invigilator_staff_id  CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    max_marks             INT           NOT NULL DEFAULT 100,
    created_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_exam_schedules_school ON exam_schedules(school_id);
GO

CREATE TABLE grade_scales (
    id           CHAR(36)      NOT NULL PRIMARY KEY,
    school_id    CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    grade        NVARCHAR(10)  NOT NULL,
    min_score    FLOAT         NOT NULL,
    max_score    FLOAT         NOT NULL,
    grade_point  FLOAT         NULL,
    description  NVARCHAR(100) NULL,
    is_pass      BIT           NOT NULL DEFAULT 1,
    created_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE marks (
    id                   CHAR(36)      NOT NULL PRIMARY KEY,
    school_id            CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    exam_schedule_id     CHAR(36)      NOT NULL REFERENCES exam_schedules(id) ON DELETE CASCADE,
    student_id           CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    obtained_marks       FLOAT         NULL,
    is_absent            BIT           NOT NULL DEFAULT 0,
    comment              NVARCHAR(255) NULL,
    entered_by_staff_id  CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    created_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_mark_schedule_student UNIQUE (exam_schedule_id, student_id)
);
GO
CREATE INDEX ix_marks_school ON marks(school_id);
GO

CREATE TABLE results (
    id                    CHAR(36)      NOT NULL PRIMARY KEY,
    school_id             CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    examination_id        CHAR(36)      NOT NULL REFERENCES examinations(id) ON DELETE CASCADE,
    student_id            CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    total_marks           FLOAT         NULL,
    total_max_marks       FLOAT         NULL,
    average_percentage    FLOAT         NULL,
    overall_grade         NVARCHAR(10)  NULL,
    overall_grade_point   FLOAT         NULL,
    is_pass               BIT           NULL,
    subject_position      INT           NULL,
    overall_position      INT           NULL,
    teacher_remark        NVARCHAR(500) NULL,
    principal_remark      NVARCHAR(500) NULL,
    status                NVARCHAR(30)  NOT NULL DEFAULT 'draft',
    created_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_result_examination_student UNIQUE (examination_id, student_id)
);
GO
CREATE INDEX ix_results_school ON results(school_id);
CREATE INDEX ix_results_status ON results(status);
GO

-- ---------------------------------------------------------------------
-- Phase 5: Finance
-- ---------------------------------------------------------------------
CREATE TABLE fee_categories (
    id           CHAR(36)      NOT NULL PRIMARY KEY,
    school_id    CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name         NVARCHAR(120) NOT NULL,
    description  NVARCHAR(255) NULL,
    is_active    BIT           NOT NULL DEFAULT 1,
    created_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_fee_category_school_name UNIQUE (school_id, name)
);
GO

CREATE TABLE fee_structures (
    id                CHAR(36)      NOT NULL PRIMARY KEY,
    school_id         CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name              NVARCHAR(255) NOT NULL,
    academic_year_id  CHAR(36)      NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id           CHAR(36)      NULL REFERENCES terms(id) ON DELETE SET NULL,
    class_id          CHAR(36)      NULL REFERENCES classes(id) ON DELETE SET NULL,
    fee_category_id   CHAR(36)      NOT NULL REFERENCES fee_categories(id) ON DELETE CASCADE,
    amount            FLOAT         NOT NULL,
    due_date          DATE          NULL,
    late_fee          FLOAT         NOT NULL DEFAULT 0,
    is_mandatory      BIT           NOT NULL DEFAULT 1,
    created_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_fee_structures_school ON fee_structures(school_id);
GO

CREATE TABLE invoices (
    id                 CHAR(36)      NOT NULL PRIMARY KEY,
    school_id          CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    invoice_number     NVARCHAR(50)  NOT NULL,
    student_id         CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    fee_structure_id   CHAR(36)      NULL REFERENCES fee_structures(id) ON DELETE SET NULL,
    description        NVARCHAR(255) NOT NULL,
    amount             FLOAT         NOT NULL,
    due_date           DATE          NULL,
    status             NVARCHAR(30)  NOT NULL DEFAULT 'unpaid',
    created_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at         DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_invoice_school_number UNIQUE (school_id, invoice_number)
);
GO
CREATE INDEX ix_invoices_school ON invoices(school_id);
CREATE INDEX ix_invoices_student ON invoices(student_id);
GO

CREATE TABLE payments (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    school_id              CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    invoice_id             CHAR(36)      NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    student_id             CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    amount                 FLOAT         NOT NULL,
    payment_method         NVARCHAR(30)  NOT NULL DEFAULT 'cash',
    reference              NVARCHAR(120) NULL,
    received_by_staff_id   CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    notes                  NVARCHAR(255) NULL,
    status                 NVARCHAR(30)  NOT NULL DEFAULT 'successful',
    receipt_number         NVARCHAR(50)  NULL,
    paid_at                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    payer_name              NVARCHAR(160) NULL,
    payer_phone             NVARCHAR(50) NULL,
    payer_relationship      NVARCHAR(50) NULL,
    created_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_payments_school ON payments(school_id);
CREATE INDEX ix_payments_student ON payments(student_id);
GO

CREATE TABLE expenses (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    school_id              CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    category               NVARCHAR(120) NOT NULL,
    description            NVARCHAR(255) NULL,
    amount                 FLOAT         NOT NULL,
    expense_date           DATE          NOT NULL,
    recorded_by_staff_id   CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    created_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_expenses_school ON expenses(school_id);
GO

-- ---------------------------------------------------------------------
-- Phase 6: Communication
-- ---------------------------------------------------------------------
CREATE TABLE messages (
    id                   CHAR(36)      NOT NULL PRIMARY KEY,
    school_id            CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    sender_user_id       CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_user_id    CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject              NVARCHAR(255) NULL,
    body                 NVARCHAR(MAX) NOT NULL,
    read_at              DATETIME2     NULL,
    is_anonymous            BIT NOT NULL DEFAULT 0,
    created_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at           DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_messages_school ON messages(school_id);
CREATE INDEX ix_messages_recipient ON messages(recipient_user_id);
GO

CREATE TABLE announcements (
    id                    CHAR(36)      NOT NULL PRIMARY KEY,
    school_id             CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    author_user_id        CHAR(36)      NULL REFERENCES users(id) ON DELETE SET NULL,
    title                 NVARCHAR(255) NOT NULL,
    body                  NVARCHAR(MAX) NOT NULL,
    audience_type         NVARCHAR(20)  NOT NULL DEFAULT 'school',
    audience_class_id     CHAR(36)      NULL REFERENCES classes(id) ON DELETE CASCADE,
    audience_section_id   CHAR(36)      NULL REFERENCES sections(id) ON DELETE CASCADE,
    audience_types          NVARCHAR(120) NOT NULL DEFAULT 'school',
    created_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at            DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_announcements_school ON announcements(school_id);
GO

CREATE TABLE notifications (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    school_id              CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    user_id                CHAR(36)      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                   NVARCHAR(50)  NOT NULL,
    title                  NVARCHAR(255) NOT NULL,
    body                   NVARCHAR(500) NULL,
    related_entity_type    NVARCHAR(50)  NULL,
    related_entity_id      CHAR(36)      NULL,
    is_read                BIT           NOT NULL DEFAULT 0,
    created_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_notifications_user ON notifications(user_id, is_read);
GO

-- ---------------------------------------------------------------------
-- Phase 7: HR / Payroll
-- ---------------------------------------------------------------------
CREATE TABLE leave_requests (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    school_id              CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    staff_id               CHAR(36)      NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    leave_type             NVARCHAR(50)  NOT NULL DEFAULT 'annual',
    start_date             DATE          NOT NULL,
    end_date               DATE          NOT NULL,
    reason                 NVARCHAR(500) NULL,
    status                 NVARCHAR(20)  NOT NULL DEFAULT 'pending',
    reviewed_by_staff_id   CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    review_note            NVARCHAR(500) NULL,
    reviewed_at            DATETIME2     NULL,
    created_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_leave_school ON leave_requests(school_id);
CREATE INDEX ix_leave_staff ON leave_requests(staff_id);
GO

CREATE TABLE payroll_runs (
    id             CHAR(36)     NOT NULL PRIMARY KEY,
    school_id      CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    period_label   NVARCHAR(50) NOT NULL,
    period_start   DATE         NOT NULL,
    period_end     DATE         NOT NULL,
    status         NVARCHAR(20) NOT NULL DEFAULT 'draft',
    processed_at   DATETIME2    NULL,
    created_at     DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at     DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_payroll_runs_school ON payroll_runs(school_id);
GO

CREATE TABLE payslips (
    id                 CHAR(36)     NOT NULL PRIMARY KEY,
    school_id          CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    payroll_run_id     CHAR(36)     NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    staff_id           CHAR(36)     NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    base_salary        FLOAT        NOT NULL DEFAULT 0,
    allowances         FLOAT        NOT NULL DEFAULT 0,
    bonuses            FLOAT        NOT NULL DEFAULT 0,
    deductions         FLOAT        NOT NULL DEFAULT 0,
    taxes              FLOAT        NOT NULL DEFAULT 0,
    other_deductions   FLOAT        NOT NULL DEFAULT 0,
    status             NVARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at         DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at         DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_payslip_run_staff UNIQUE (payroll_run_id, staff_id)
);
GO
CREATE INDEX ix_payslips_school ON payslips(school_id);
GO

-- ---------------------------------------------------------------------
-- Phase 8: Discipline
-- ---------------------------------------------------------------------
CREATE TABLE disciplinary_records (
    id                        CHAR(36)      NOT NULL PRIMARY KEY,
    school_id                 CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id                CHAR(36)      NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    reported_by_staff_id      CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    date                      DATE          NOT NULL,
    category                  NVARCHAR(30)  NOT NULL DEFAULT 'incident',
    severity                  NVARCHAR(20)  NULL,
    description               NVARCHAR(MAX) NOT NULL,
    action_taken              NVARCHAR(500) NULL,
    status                    NVARCHAR(20)  NOT NULL DEFAULT 'open',
    follow_up_note            NVARCHAR(500) NULL,
    follow_up_by_staff_id     CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    resolved_at               DATETIME2     NULL,
    created_at                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_discipline_school ON disciplinary_records(school_id);
CREATE INDEX ix_discipline_student ON disciplinary_records(student_id);
GO

-- ---------------------------------------------------------------------
-- Phase 9: Library
-- ---------------------------------------------------------------------
CREATE TABLE books (
    id                CHAR(36)      NOT NULL PRIMARY KEY,
    school_id         CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    title             NVARCHAR(255) NOT NULL,
    author            NVARCHAR(255) NULL,
    publisher         NVARCHAR(255) NULL,
    isbn              NVARCHAR(50)  NULL,
    category          NVARCHAR(120) NULL,
    total_copies      INT           NOT NULL DEFAULT 1,
    available_copies  INT           NOT NULL DEFAULT 1,
    is_active         BIT           NOT NULL DEFAULT 1,
    loan_days               INT NULL,
    daily_fine              FLOAT NULL,
    created_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_books_school ON books(school_id);
GO

CREATE TABLE borrow_records (
    id                    CHAR(36)     NOT NULL PRIMARY KEY,
    school_id             CHAR(36)     NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    book_id               CHAR(36)     NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    student_id            CHAR(36)     NULL REFERENCES students(id) ON DELETE CASCADE,
    staff_id              CHAR(36)     NULL REFERENCES staff(id) ON DELETE CASCADE,
    borrowed_date         DATE         NOT NULL,
    due_date              DATE         NOT NULL,
    returned_date         DATE         NULL,
    status                NVARCHAR(20) NOT NULL DEFAULT 'borrowed',
    fine_amount           FLOAT        NOT NULL DEFAULT 0,
    issued_by_staff_id    CHAR(36)     NULL REFERENCES staff(id) ON DELETE SET NULL,
    daily_fine_rate         FLOAT NULL,
    fine_calculated         FLOAT NULL,
    fine_note               NVARCHAR(255) NULL,
    created_at            DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at            DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_borrow_school ON borrow_records(school_id);
CREATE INDEX ix_borrow_status_due ON borrow_records(status, due_date);
GO

-- ---------------------------------------------------------------------
-- Phase 11: Inventory
-- ---------------------------------------------------------------------
CREATE TABLE suppliers (
    id               CHAR(36)      NOT NULL PRIMARY KEY,
    school_id        CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name             NVARCHAR(255) NOT NULL,
    contact_person   NVARCHAR(120) NULL,
    phone            NVARCHAR(50)  NULL,
    email            NVARCHAR(255) NULL,
    address          NVARCHAR(500) NULL,
    is_active        BIT           NOT NULL DEFAULT 1,
    created_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_suppliers_school ON suppliers(school_id);
GO

CREATE TABLE inventory_items (
    id              CHAR(36)      NOT NULL PRIMARY KEY,
    school_id       CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            NVARCHAR(255) NOT NULL,
    category        NVARCHAR(120) NULL,
    supplier_id     CHAR(36)      NULL REFERENCES suppliers(id) ON DELETE SET NULL,
    quantity        INT           NOT NULL DEFAULT 1,
    unit_cost       FLOAT         NULL,
    location        NVARCHAR(255) NULL,
    status          NVARCHAR(20)  NOT NULL DEFAULT 'in_use',
    purchase_date   DATE          NULL,
    is_active       BIT           NOT NULL DEFAULT 1,
    created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_inventory_school ON inventory_items(school_id);
GO

CREATE TABLE maintenance_records (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    school_id              CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    item_id                CHAR(36)      NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    description            NVARCHAR(500) NOT NULL,
    cost                   FLOAT         NULL,
    performed_date         DATE          NOT NULL,
    recorded_by_staff_id   CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    completed_date          DATE NULL,
    created_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_maintenance_school ON maintenance_records(school_id);
GO

-- ---------------------------------------------------------------------
-- Phase 12: Transport
-- ---------------------------------------------------------------------
CREATE TABLE drivers (
    id               CHAR(36)      NOT NULL PRIMARY KEY,
    school_id        CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    staff_id         CHAR(36)      NULL REFERENCES staff(id) ON DELETE SET NULL,
    full_name        NVARCHAR(255) NOT NULL,
    phone            NVARCHAR(50)  NULL,
    license_number   NVARCHAR(50)  NULL,
    is_active        BIT           NOT NULL DEFAULT 1,
    photo_url               NVARCHAR(500) NULL,
    address                 NVARCHAR(255) NULL,
    created_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_drivers_school ON drivers(school_id);
GO

CREATE TABLE vehicles (
    id                        CHAR(36)      NOT NULL PRIMARY KEY,
    school_id                 CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    vehicle_number            NVARCHAR(50)  NOT NULL,
    registration              NVARCHAR(50)  NULL,
    vehicle_type              NVARCHAR(50)  NULL,
    capacity                  INT           NULL,
    driver_id                 CHAR(36)      NULL REFERENCES drivers(id) ON DELETE SET NULL,
    insurance_expiry          DATE          NULL,
    next_maintenance_date     DATE          NULL,
    status                    NVARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_vehicle_school_number UNIQUE (school_id, vehicle_number)
);
GO
CREATE INDEX ix_vehicles_school ON vehicles(school_id);
GO

CREATE TABLE transport_routes (
    id                CHAR(36)      NOT NULL PRIMARY KEY,
    school_id         CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name              NVARCHAR(255) NOT NULL,
    vehicle_id        CHAR(36)      NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    driver_id         CHAR(36)      NULL REFERENCES drivers(id) ON DELETE SET NULL,
    departure_time    TIME          NULL,
    is_active         BIT           NOT NULL DEFAULT 1,
    created_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_routes_school ON transport_routes(school_id);
GO

CREATE TABLE route_stops (
    id             CHAR(36)      NOT NULL PRIMARY KEY,
    school_id      CHAR(36)      NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    route_id       CHAR(36)      NOT NULL REFERENCES transport_routes(id) ON DELETE CASCADE,
    name           NVARCHAR(255) NOT NULL,
    order_index    INT           NOT NULL DEFAULT 0,
    arrival_time   TIME          NULL,
    created_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_stops_route ON route_stops(route_id);
GO

CREATE TABLE transport_assignments (
    id           CHAR(36)  NOT NULL PRIMARY KEY,
    school_id    CHAR(36)  NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id   CHAR(36)  NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    route_id     CHAR(36)  NOT NULL REFERENCES transport_routes(id) ON DELETE CASCADE,
    stop_id      CHAR(36)  NULL REFERENCES route_stops(id) ON DELETE SET NULL,
    is_active    BIT       NOT NULL DEFAULT 1,
    created_at   DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at   DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_transport_assignment_student_route UNIQUE (student_id, route_id)
);
GO
CREATE INDEX ix_transport_assignments_school ON transport_assignments(school_id);
GO
