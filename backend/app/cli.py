import click

from .extensions import db
from .models import Role, User


def register_cli(app):
    from .evaluation.cli import eval_cli

    app.cli.add_command(eval_cli)

    @app.cli.command("create-user")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--role", type=click.Choice([r.value for r in Role]), default=Role.ADMIN.value, show_default=True)
    @click.password_option()
    def create_user(username, email, role, password):
        """Create a user (use this to bootstrap the first Admin)."""
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters")
        if db.session.execute(db.select(User).filter((User.username == username) | (User.email == email))).first():
            raise click.ClickException("A user with that username or email already exists")
        user = User(username=username, email=email, role=Role(role))
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created {role} '{username}' (id={user.user_id})")

    @app.cli.command("fail-stale-runs")
    @click.option("--minutes", type=int, help="Heartbeat age that counts as stale (default: STALE_RUN_MINUTES).")
    def fail_stale_runs_command(minutes):
        """Mark analyses whose worker stopped responding as Failed (so they can be retried)."""
        from .services.analysis import fail_stale_runs

        failed = fail_stale_runs(minutes or app.config["STALE_RUN_MINUTES"])
        click.echo(f"Marked {len(failed)} stale session(s) as failed" + (f": {failed}" if failed else ""))

    @app.cli.command("seed-core")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--title", help="Document title (default: file name).")
    @click.option("--admin", "admin_username", help="Admin to record as uploader (default: first active Admin).")
    def seed_core(path, title, admin_username):
        """Load the NUC core curriculum (CSV course list, PDF, DOCX or TXT) as a NUC Core Reference."""
        from pathlib import Path

        from .models import SourceCategory
        from .services.ingestion.library import add_document
        from .utils.errors import ApiError

        query = db.select(User).filter_by(role=Role.ADMIN, is_active=True).order_by(User.user_id)
        if admin_username:
            query = query.filter_by(username=admin_username)
        admin = db.session.execute(query).scalars().first()
        if admin is None:
            raise click.ClickException("No active Admin found; create one with `flask create-user --role Admin`")
        try:
            document = add_document(Path(path).read_bytes(), Path(path).name, SourceCategory.NUC_CORE,
                                    admin.user_id, title)
        except ApiError as exc:
            raise click.ClickException(exc.message)
        if document.processing_status.value != "Parsed":
            raise click.ClickException(f"Stored, but text extraction failed: {document.error_message}")
        click.echo(f"Loaded '{document.title}' as NUC Core Reference (id={document.document_id}, "
                   f"{document.word_count} words)")
