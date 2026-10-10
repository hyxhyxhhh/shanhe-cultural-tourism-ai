"""Persist per-scope research generation progress and provider audit."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_research_scope_progress"
down_revision = "0007_execution_task_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_runs", sa.Column("scope_progress", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_runs", "scope_progress")
