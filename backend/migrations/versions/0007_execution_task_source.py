"""Link generated execution tasks to the confirmed step version."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_execution_task_source"
down_revision: Union[str, Sequence[str], None] = "0006_deliverables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("execution_tasks", sa.Column("source_step_version", sa.Integer()))
    op.add_column("execution_tasks", sa.Column("source_task_index", sa.Integer()))
    op.create_check_constraint(
        "ck_execution_tasks_generated_source",
        "execution_tasks",
        "(source_step_version IS NULL AND source_task_index IS NULL) OR "
        "(source_step_version >= 1 AND source_task_index >= 0)",
    )
    op.create_unique_constraint(
        "uq_execution_tasks_generated_source",
        "execution_tasks",
        ["activity_id", "source_step_version", "source_task_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_execution_tasks_generated_source", "execution_tasks", type_="unique"
    )
    op.drop_constraint(
        "ck_execution_tasks_generated_source", "execution_tasks", type_="check"
    )
    op.drop_column("execution_tasks", "source_task_index")
    op.drop_column("execution_tasks", "source_step_version")
