-- =====================================================================
-- Upgrade an EXISTING SQL Server database made from an older sql/schema.sql.
-- Safe to run more than once: each column is only added if it is missing.
-- Run in SSMS against the SchoolPlatform database (take a backup first).
-- Do not run this on a database you just created from the current schema.sql.
-- =====================================================================
USE SchoolPlatform;
GO

IF COL_LENGTH('schools', 'library_loan_days') IS NULL
    ALTER TABLE schools ADD library_loan_days INT NULL;
GO
IF COL_LENGTH('schools', 'library_daily_fine') IS NULL
    ALTER TABLE schools ADD library_daily_fine FLOAT NULL;
GO
IF COL_LENGTH('books', 'loan_days') IS NULL
    ALTER TABLE books ADD loan_days INT NULL;
GO
IF COL_LENGTH('books', 'daily_fine') IS NULL
    ALTER TABLE books ADD daily_fine FLOAT NULL;
GO
IF COL_LENGTH('users', 'password_changed_at') IS NULL
    ALTER TABLE users ADD password_changed_at DATETIME2 NULL;
GO
IF COL_LENGTH('messages', 'is_anonymous') IS NULL
    ALTER TABLE messages ADD is_anonymous BIT NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('staff', 'title') IS NULL
    ALTER TABLE staff ADD title NVARCHAR(10) NULL;
GO
IF COL_LENGTH('staff', 'address') IS NULL
    ALTER TABLE staff ADD address NVARCHAR(500) NULL;
GO
IF COL_LENGTH('staff', 'base_salary') IS NULL
    ALTER TABLE staff ADD base_salary FLOAT NULL;
GO
IF COL_LENGTH('borrow_records', 'daily_fine_rate') IS NULL
    ALTER TABLE borrow_records ADD daily_fine_rate FLOAT NULL;
GO
IF COL_LENGTH('borrow_records', 'fine_calculated') IS NULL
    ALTER TABLE borrow_records ADD fine_calculated FLOAT NULL;
GO
IF COL_LENGTH('borrow_records', 'fine_note') IS NULL
    ALTER TABLE borrow_records ADD fine_note NVARCHAR(255) NULL;
GO
IF COL_LENGTH('classes', 'class_master_staff_id') IS NULL
    ALTER TABLE classes ADD class_master_staff_id CHAR(36) NULL CONSTRAINT fk_classes_class_master_staff_id REFERENCES staff(id);
GO
IF COL_LENGTH('drivers', 'photo_url') IS NULL
    ALTER TABLE drivers ADD photo_url NVARCHAR(500) NULL;
GO
IF COL_LENGTH('drivers', 'address') IS NULL
    ALTER TABLE drivers ADD address NVARCHAR(255) NULL;
GO
IF COL_LENGTH('maintenance_records', 'completed_date') IS NULL
    ALTER TABLE maintenance_records ADD completed_date DATE NULL;
GO
IF COL_LENGTH('announcements', 'audience_types') IS NULL
    ALTER TABLE announcements ADD audience_types NVARCHAR(120) NOT NULL DEFAULT 'school';
GO
IF COL_LENGTH('assignments', 'created_by_user_id') IS NULL
    ALTER TABLE assignments ADD created_by_user_id CHAR(36) NULL CONSTRAINT fk_assignments_created_by_user_id REFERENCES users(id);
GO
IF COL_LENGTH('assignments', 'original_due_date') IS NULL
    ALTER TABLE assignments ADD original_due_date DATE NULL;
GO
IF COL_LENGTH('payments', 'payer_name') IS NULL
    ALTER TABLE payments ADD payer_name NVARCHAR(160) NULL;
GO
IF COL_LENGTH('payments', 'payer_phone') IS NULL
    ALTER TABLE payments ADD payer_phone NVARCHAR(50) NULL;
GO
IF COL_LENGTH('payments', 'payer_relationship') IS NULL
    ALTER TABLE payments ADD payer_relationship NVARCHAR(50) NULL;
GO

PRINT 'Upgrade finished.';
GO
