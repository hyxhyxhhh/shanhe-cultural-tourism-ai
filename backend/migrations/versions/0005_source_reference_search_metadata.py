"""Preserve public-search provenance on source references."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_search_metadata"
down_revision: Union[str, Sequence[str], None] = "0004_workflow_integrity_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("source_references", sa.Column("published_at", sa.String(200)))
    op.add_column("source_references", sa.Column("site_name", sa.String(300)))
    op.add_column("source_references", sa.Column("authority_level", sa.String(24)))
    op.add_column("source_references", sa.Column("rank", sa.Integer()))
    op.add_column("source_references", sa.Column("provider_request_id", sa.String(300)))
    op.add_column("source_references", sa.Column("scope", sa.String(40)))
    op.create_check_constraint(
        "ck_source_references_authority_level",
        "source_references",
        "authority_level IS NULL OR authority_level IN ('very_high', 'high', 'normal')",
    )
    op.create_check_constraint(
        "ck_source_references_rank",
        "source_references",
        "rank IS NULL OR rank >= 0",
    )
    op.create_check_constraint(
        "ck_source_references_scope",
        "source_references",
        "scope IS NULL OR scope IN ('weather', 'holiday', 'similar_events', 'public_trend')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_source_references_scope", "source_references", type_="check")
    op.drop_constraint("ck_source_references_rank", "source_references", type_="check")
    op.drop_constraint("ck_source_references_authority_level", "source_references", type_="check")
    op.drop_column("source_references", "scope")
    op.drop_column("source_references", "provider_request_id")
    op.drop_column("source_references", "rank")
    op.drop_column("source_references", "authority_level")
    op.drop_column("source_references", "site_name")
    op.drop_column("source_references", "published_at")
