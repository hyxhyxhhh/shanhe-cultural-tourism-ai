"""Associate annual plan items with separately editable single activities."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_annual_plan_item_activities"
down_revision = "0009_planning_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annual_plan_item_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("annual_activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(80), nullable=False),
        sa.Column("child_activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_step_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("annual_activity_id", "event_id", name="uq_annual_plan_item_activity_source"),
        sa.UniqueConstraint("child_activity_id", name="uq_annual_plan_item_activity_child"),
        sa.CheckConstraint("source_step_version >= 1", name="ck_annual_plan_item_activity_version"),
        sa.CheckConstraint("annual_activity_id <> child_activity_id", name="ck_annual_plan_item_activity_distinct"),
    )


def downgrade() -> None:
    op.drop_table("annual_plan_item_activities")
