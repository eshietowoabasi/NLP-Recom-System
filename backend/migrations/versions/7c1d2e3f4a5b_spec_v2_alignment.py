"""Spec v2 alignment: remove Viewer role and Flagged decision, CSV documents,
one mapping per recommendation, longer course codes, system settings.

Revision ID: 7c1d2e3f4a5b
Revises: 49eb1962fdba
Create Date: 2026-09-24

"""
import sqlalchemy as sa
from alembic import op

revision = "7c1d2e3f4a5b"
down_revision = "49eb1962fdba"
branch_labels = None
depends_on = None


def _replace_check(table, name, condition):
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(op.f(name), type_="check")
        batch.create_check_constraint(op.f(name), condition)


def upgrade():
    # Roles: Admin and Curriculum Planner only (existing viewers become planners).
    op.execute("UPDATE users SET role = 'Curriculum Planner' WHERE role = 'Viewer'")
    _replace_check("users", "ck_users_user_role", "role IN ('Admin', 'Curriculum Planner')")

    # Decisions: pending (NULL), Accepted or Rejected (flagged ones go back to pending).
    op.execute("UPDATE recommendations SET planner_decision = NULL WHERE planner_decision = 'Flagged'")
    _replace_check("recommendations", "ck_recommendations_planner_decision",
                   "planner_decision IN ('Accepted', 'Rejected')")

    # CSV documents (e.g. the core-curriculum course list).
    _replace_check("documents", "ck_documents_file_type", "file_type IN ('pdf', 'docx', 'txt', 'csv')")

    # One mapping per recommendation: keep the oldest if several exist.
    op.execute(
        "DELETE FROM curriculum_maps WHERE map_id NOT IN "
        "(SELECT MIN(map_id) FROM curriculum_maps GROUP BY rec_id)"
    )
    with op.batch_alter_table("curriculum_maps") as batch:
        batch.alter_column("course_code", existing_type=sa.String(16), type_=sa.String(20), existing_nullable=False)
        batch.drop_index("ix_curriculum_maps_rec_id")
        batch.create_unique_constraint(op.f("uq_curriculum_maps_rec_id"), ["rec_id"])

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name=op.f("fk_system_settings_updated_by_users")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_settings")),
    )


def downgrade():
    op.drop_table("system_settings")
    with op.batch_alter_table("curriculum_maps") as batch:
        batch.drop_constraint(op.f("uq_curriculum_maps_rec_id"), type_="unique")
        batch.create_index("ix_curriculum_maps_rec_id", ["rec_id"], unique=False)
        batch.alter_column("course_code", existing_type=sa.String(20), type_=sa.String(16), existing_nullable=False)
    op.execute("DELETE FROM documents WHERE file_type = 'csv'")
    _replace_check("documents", "ck_documents_file_type", "file_type IN ('pdf', 'docx', 'txt')")
    _replace_check("recommendations", "ck_recommendations_planner_decision",
                   "planner_decision IN ('Accepted', 'Rejected', 'Flagged')")
    _replace_check("users", "ck_users_user_role", "role IN ('Admin', 'Curriculum Planner', 'Viewer')")
