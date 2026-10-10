"""Persist planning unit progress and per-request provider audit."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_planning_progress"
down_revision = "0008_research_scope_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_runs", sa.Column("planning_progress", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_runs", "planning_progress")
