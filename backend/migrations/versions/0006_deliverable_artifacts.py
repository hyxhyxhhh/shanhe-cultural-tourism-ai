"""Persist versioned generated deliverable files."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_deliverables"
down_revision: Union[str, Sequence[str], None] = "0005_search_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deliverable_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version >= 1", name="ck_deliverable_artifacts_version"),
        sa.UniqueConstraint(
            "activity_id",
            "filename",
            "version",
            name="uq_deliverable_artifacts_activity_filename_version",
        ),
    )
    op.create_index(
        "ix_deliverable_artifacts_activity",
        "deliverable_artifacts",
        ["activity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_deliverable_artifacts_activity", table_name="deliverable_artifacts")
    op.drop_table("deliverable_artifacts")
