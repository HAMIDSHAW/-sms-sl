import click

from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create all tables from the SQLAlchemy models (dev/SQLite convenience).
    For SQL Server in production, prefer running sql/schema.sql via SSMS or
    a proper migration tool (Alembic) instead of this."""
    db.create_all()
    click.echo("Tables created.")


@app.cli.command("create-superadmin")
@click.option("--email", prompt="Super admin email", help="The login email for the platform super admin.")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="Leave this out and you will be asked, so it never ends up in your shell history.")
def create_superadmin(email, password):
    """Create the platform super admin and nothing else: no demo school, no sample accounts.

    This is how a real deployment gets its first login. The super admin then creates the
    real school from the Platform Admin screen. Run it once, from your own computer, with
    DATABASE_URL pointing at the production database, after the first deploy has created
    the tables."""
    from app.models import User
    from app.utils.passwords import validate_password
    from app.utils.rbac_seed import ensure_super_admin_role

    email = email.strip().lower()
    problem = validate_password(password, email)
    if problem:
        raise click.ClickException(problem)
    if User.query.filter(db.func.lower(User.email) == email).first():
        raise click.ClickException("That email already has an account.")

    user = User(school_id=None, email=email, first_name="Platform", last_name="Admin", must_change_password=False)
    user.set_password(password)
    user.roles.append(ensure_super_admin_role())
    db.session.add(user)
    db.session.commit()
    click.echo(f"Platform super admin created: {email}")


@app.cli.command("seed-demo")
def seed_demo():
    """Seed one demo tenant school with realistic Sierra Leone data, so the
    UI has something real to render immediately. Uses Kenema Government
    Secondary School as a real-world reference, the admin can rename,
    re-logo, and re-brand it to any school from the settings screen at any
    time; nothing about this seed is hard-coded elsewhere in the app."""
    from seed import run_seed
    run_seed()
    click.echo("Demo school seeded.")


if __name__ == "__main__":
    # Debug mode (auto reload, interactive error page) is for a developer's own machine only.
    from app.utils.security import is_deployment
    app.run(debug=not is_deployment())
