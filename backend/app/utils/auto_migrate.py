"""
Lightweight auto-migration for SQLite dev databases.

This project doesn't use Alembic (kept dependencies minimal for an
easy Windows setup), which means every time a column was added to a
model in code, an already-existing `dev.db` silently fell out of sync
with it -- every query touching that table would 500 with
"no such column: ...", and there was no way to know except by reading
a server traceback. That's a real, repeatedly-hit problem, not a
one-off: relying on someone to remember to delete `dev.db` after every
update isn't realistic.

This runs once per app startup: for every model, compare its declared
columns against what SQLite's `dev.db` actually has, and `ALTER TABLE
... ADD COLUMN` anything missing. SQLite only supports adding nullable
columns (or ones with a constant default) this way -- which matches
every column this project has ever added after the fact, since a
brand-new column on an existing table can never be NOT NULL without a
default anyway (existing rows wouldn't have a value for it).
"""
from sqlalchemy import inspect, text
from sqlalchemy.types import String, Text, Integer, Float, Boolean, Date, DateTime, Time


def _column_ddl_type(sa_type, dialect_name="sqlite"):
    if isinstance(sa_type, Boolean):
        return "BOOLEAN"
    if isinstance(sa_type, Integer):
        return "INTEGER"
    if isinstance(sa_type, Float):
        return "FLOAT"
    if isinstance(sa_type, DateTime):
        # SQLite has no real DATETIME type (it's stored as TEXT either way,
        # column affinity is purely advisory) but Postgres does, and
        # Postgres has no type literally named DATETIME, so this would
        # raise "type \"datetime\" does not exist" the first time this ran
        # against Supabase/any real Postgres DATABASE_URL.
        return "DATETIME" if dialect_name == "sqlite" else "TIMESTAMP"
    if isinstance(sa_type, Date):
        return "DATE"
    if isinstance(sa_type, Time):
        return "TIME"
    if isinstance(sa_type, Text):
        return "TEXT"
    if isinstance(sa_type, String):
        length = getattr(sa_type, "length", None)
        return "VARCHAR(%d)" % length if length else "VARCHAR"
    return "TEXT"


def run_auto_migration(db):
    """
    Safe to call every time the app starts -- a no-op once schemas match.

    Works against Postgres too (e.g. Supabase in production), not just
    SQLite, but for a real production database, treat this the way its
    docstring above describes it: a stopgap for solo-dev convenience, not
    a substitute for reviewed migrations. It has no rollback and no history.
    Once this project has paying users relying on that data, introducing
    Flask-Migrate/Alembic for schema changes is the safer long-term path;
    this can keep running alongside it for the SQLite dev workflow.
    """
    engine = db.engine
    dialect_name = engine.dialect.name  # 'sqlite' or 'postgresql'
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    added = []
    with engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in actual_columns:
                    continue
                ddl_type = _column_ddl_type(column.type, dialect_name)
                conn.execute(text('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table.name, column.name, ddl_type)))
                added.append("%s.%s" % (table.name, column.name))

    if added:
        import logging
        logging.getLogger(__name__).warning(
            "Auto-migration added %d missing column(s): %s", len(added), ", ".join(added)
        )

    # One-off data backfill: announcements.audience_types replaced the old
    # single audience_type column. A row that predates this column would
    # otherwise silently default to "school" and stop showing up for its
    # real (possibly non-school) audience the moment this code runs against
    # an existing dev.db. Re-deriving it from the still-present audience_type
    # column is safe to run every startup (idempotent, a row already
    # correctly backfilled is just overwritten with the same value).
    if "announcements.audience_types" in added:
        with engine.begin() as conn:
            conn.execute(text(
                'UPDATE announcements SET audience_types = \',\' || audience_type || \',\' '
                'WHERE audience_types IS NULL OR audience_types = \'\' OR audience_types = \'school\''
            ))

    return added
