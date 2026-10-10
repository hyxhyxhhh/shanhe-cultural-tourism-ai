"""Platform-internal execution task routes with no external side effects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from backend.auth import CurrentSession, DbSession
from backend.models import Activity, ActivityStep, ExecutionTask


class ExecutionTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    owner: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = Field(default=None, alias="dueAt")
    attachment_file_ids: list[str] = Field(default_factory=list, alias="attachmentFileIds")


class ExecutionTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    owner: str | None = Field(default=None, min_length=1, max_length=200)
    due_at: datetime | None = Field(default=None, alias="dueAt")
    status: Literal["draft", "pending_confirmation", "ready", "in_progress", "blocked", "completed"] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> ExecutionTaskUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one execution task field is required")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        if self.due_at is not None and self.due_at.utcoffset() is None:
            raise ValueError("dueAt must include a timezone")
        return self


router = APIRouter(
    prefix="/api/activities/{activity_id}/execution-tasks",
    tags=["execution"],
)


def _owned_activity(activity_id: UUID, current, db) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.created_by == str(current.user_id))
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _serialize(task: ExecutionTask) -> dict[str, object]:
    return {
        "id": str(task.id),
        "activityId": str(task.activity_id),
        "stepNo": task.step_no,
        "title": task.title,
        "description": task.description,
        "owner": task.owner,
        "dueAt": task.due_at.isoformat() if task.due_at else None,
        "status": task.status,
        "attachmentFileIds": task.attachment_file_ids,
    }


def _require_execution_prerequisites(activity: Activity, db) -> None:
    steps = db.scalars(
        select(ActivityStep).where(
            ActivityStep.activity_id == activity.id,
            ActivityStep.step_no.in_([5, 6]),
        )
    ).all()
    statuses = {step.step_no: step.status for step in steps}
    if statuses.get(5) != "confirmed" or statuses.get(6) != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="预算和传播计划必须先确认",
        )


@router.get("")
def list_execution_tasks(
    activity_id: UUID,
    current: CurrentSession,
    db: DbSession,
) -> list[dict[str, object]]:
    activity = _owned_activity(activity_id, current, db)
    tasks = db.scalars(
        select(ExecutionTask)
        .where(ExecutionTask.activity_id == activity.id)
        .order_by(ExecutionTask.due_at, ExecutionTask.id)
    ).all()
    return [_serialize(task) for task in tasks]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_execution_task(
    activity_id: UUID,
    payload: ExecutionTaskRequest,
    current: CurrentSession,
    db: DbSession,
) -> dict[str, object]:
    activity = _owned_activity(activity_id, current, db)
    _require_execution_prerequisites(activity, db)
    task = ExecutionTask(
        activity_id=activity.id,
        step_no=7,
        title=payload.title,
        description=payload.description,
        owner=payload.owner,
        due_at=payload.due_at,
        status="pending_confirmation",
        attachment_file_ids=payload.attachment_file_ids,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize(task)


@router.post("/{task_id}/confirm")
def confirm_execution_task(
    activity_id: UUID,
    task_id: UUID,
    current: CurrentSession,
    db: DbSession,
) -> dict[str, object]:
    activity = _owned_activity(activity_id, current, db)
    task = db.scalar(
        select(ExecutionTask).where(ExecutionTask.id == task_id, ExecutionTask.activity_id == activity.id)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution task not found")
    if task.status != "pending_confirmation":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not awaiting confirmation")
    task.status = "ready"
    db.commit()
    db.refresh(task)
    return _serialize(task)


@router.patch("/{task_id}")
def update_execution_task(
    activity_id: UUID,
    task_id: UUID,
    payload: ExecutionTaskUpdate,
    current: CurrentSession,
    db: DbSession,
) -> dict[str, object]:
    activity = _owned_activity(activity_id, current, db)
    task = db.scalar(
        select(ExecutionTask).where(ExecutionTask.id == task_id, ExecutionTask.activity_id == activity.id)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution task not found")
    if "owner" in payload.model_fields_set:
        task.owner = payload.owner
    if "due_at" in payload.model_fields_set:
        task.due_at = payload.due_at
    if "status" in payload.model_fields_set:
        task.status = payload.status
    db.commit()
    db.refresh(task)
    return _serialize(task)
