"""Add step version history, confirmations, and model run metadata."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_activity_step_history"
down_revision: Union[str, Sequence[str], None] = "0002_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_step_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("changed_by", sa.String(200), nullable=False),
        sa.Column("change_type", sa.String(40), nullable=False),
        sa.Column("change_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "activity_id",
            "step_no",
            "version",
            name="uq_activity_step_versions_activity_step_version",
        ),
    )
    op.create_index(
        "ix_activity_step_versions_activity_step",
        "activity_step_versions",
        ["activity_id", "step_no"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO activity_step_versions
                (id, activity_id, step_no, version, input_json, output_json, status,
                 changed_by, change_type)
            SELECT gen_random_uuid(), s.activity_id, s.step_no, s.version,
                   s.input_json, s.output_json, s.status, a.created_by, 'initial'
            FROM activity_steps AS s
            JOIN activities AS a ON a.id = s.activity_id
            """
        )
    )
    op.create_table(
        "activity_step_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.String(200), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "activity_id",
            "step_no",
            "version",
            name="uq_activity_step_confirmations_activity_step_version",
        ),
        sa.ForeignKeyConstraint(
            ["activity_id", "step_no", "version"],
            [
                "activity_step_versions.activity_id",
                "activity_step_versions.step_no",
                "activity_step_versions.version",
            ],
            name="fk_activity_step_confirmations_version",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_activity_step_confirmations_activity_step",
        "activity_step_confirmations",
        ["activity_id", "step_no"],
    )
    op.create_table(
        "model_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="ccode"),
        sa.Column("model", sa.String(200)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("provider_request_id", sa.String(300)),
        sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("generation_id", name="uq_model_runs_generation_id"),
    )
    op.create_index("ix_model_runs_activity_step", "model_runs", ["activity_id", "step_no"])
    op.create_index("ix_model_runs_status", "model_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_model_runs_status", table_name="model_runs")
    op.drop_index("ix_model_runs_activity_step", table_name="model_runs")
    op.drop_table("model_runs")
    op.drop_index(
        "ix_activity_step_confirmations_activity_step",
        table_name="activity_step_confirmations",
    )
    op.drop_table("activity_step_confirmations")
    op.drop_index("ix_activity_step_versions_activity_step", table_name="activity_step_versions")
    op.drop_table("activity_step_versions")
