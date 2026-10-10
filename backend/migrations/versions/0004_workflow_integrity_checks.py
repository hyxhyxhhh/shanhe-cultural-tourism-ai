"""Add database checks for workflow identity and state values."""
from typing import Sequence, Union

from alembic import op


revision: str = "0004_workflow_integrity_checks"
down_revision: Union[str, Sequence[str], None] = "0003_activity_step_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_activities_status",
        "activities",
        "status IN ('draft', 'running', 'paused', 'completed', 'failed', 'archived')",
    )
    op.create_check_constraint(
        "ck_activities_current_step", "activities", "current_step BETWEEN 1 AND 9"
    )

    op.create_check_constraint(
        "ck_activity_steps_step_no", "activity_steps", "step_no BETWEEN 1 AND 9"
    )
    op.create_check_constraint(
        "ck_activity_steps_step_key",
        "activity_steps",
        "step_key IN ('brief', 'research', 'theme', 'content_space', 'budget', 'promotion', 'execution_plan', 'channel_business', 'review')",
    )
    op.create_check_constraint(
        "ck_activity_steps_status",
        "activity_steps",
        "status IN ('locked', 'draft', 'generating', 'review', 'confirmed', 'needs_review', 'failed')",
    )
    op.create_check_constraint("ck_activity_steps_version", "activity_steps", "version >= 1")
    op.create_check_constraint(
        "ck_activity_steps_step_identity",
        "activity_steps",
        "(step_no = 1 AND step_key = 'brief') OR "
        "(step_no = 2 AND step_key = 'research') OR "
        "(step_no = 3 AND step_key = 'theme') OR "
        "(step_no = 4 AND step_key = 'content_space') OR "
        "(step_no = 5 AND step_key = 'budget') OR "
        "(step_no = 6 AND step_key = 'promotion') OR "
        "(step_no = 7 AND step_key = 'execution_plan') OR "
        "(step_no = 8 AND step_key = 'channel_business') OR "
        "(step_no = 9 AND step_key = 'review')",
    )

    op.create_check_constraint(
        "ck_activity_step_versions_step_no",
        "activity_step_versions",
        "step_no BETWEEN 1 AND 9",
    )
    op.create_check_constraint(
        "ck_activity_step_versions_version", "activity_step_versions", "version >= 1"
    )
    op.create_check_constraint(
        "ck_activity_step_versions_status",
        "activity_step_versions",
        "status IN ('locked', 'draft', 'generating', 'review', 'confirmed', 'needs_review', 'failed')",
    )

    op.create_check_constraint(
        "ck_activity_step_confirmations_step_no",
        "activity_step_confirmations",
        "step_no BETWEEN 1 AND 9",
    )
    op.create_check_constraint(
        "ck_activity_step_confirmations_version",
        "activity_step_confirmations",
        "version >= 1",
    )

    op.create_check_constraint("ck_model_runs_step_no", "model_runs", "step_no BETWEEN 1 AND 9")
    op.create_check_constraint(
        "ck_model_runs_status", "model_runs", "status IN ('running', 'completed', 'failed')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_model_runs_status", "model_runs", type_="check")
    op.drop_constraint("ck_model_runs_step_no", "model_runs", type_="check")
    op.drop_constraint("ck_activity_step_confirmations_version", "activity_step_confirmations", type_="check")
    op.drop_constraint("ck_activity_step_confirmations_step_no", "activity_step_confirmations", type_="check")
    op.drop_constraint("ck_activity_step_versions_status", "activity_step_versions", type_="check")
    op.drop_constraint("ck_activity_step_versions_version", "activity_step_versions", type_="check")
    op.drop_constraint("ck_activity_step_versions_step_no", "activity_step_versions", type_="check")
    op.drop_constraint("ck_activity_steps_step_identity", "activity_steps", type_="check")
    op.drop_constraint("ck_activity_steps_version", "activity_steps", type_="check")
    op.drop_constraint("ck_activity_steps_status", "activity_steps", type_="check")
    op.drop_constraint("ck_activity_steps_step_key", "activity_steps", type_="check")
    op.drop_constraint("ck_activity_steps_step_no", "activity_steps", type_="check")
    op.drop_constraint("ck_activities_current_step", "activities", type_="check")
    op.drop_constraint("ck_activities_status", "activities", type_="check")
