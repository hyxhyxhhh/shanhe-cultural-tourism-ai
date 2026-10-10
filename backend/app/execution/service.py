"""Execution task lifecycle without external side effects."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol, Sequence
from uuid import uuid4


class ExecutionTaskStatus(StrEnum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass
class ExecutionTaskDraft:
    activity_id: str
    step_no: int
    title: str
    description: str | None = None
    owner: str | None = None
    due_at: datetime | None = None
    status: ExecutionTaskStatus = ExecutionTaskStatus.PENDING_CONFIRMATION
    attachment_file_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))


class ExecutionTaskRepository(Protocol):
    async def save(self, task: ExecutionTaskDraft) -> ExecutionTaskDraft:
        ...

    async def get(self, task_id: str) -> ExecutionTaskDraft | None:
        ...

    async def list_for_activity(self, activity_id: str) -> Sequence[ExecutionTaskDraft]:
        ...


class ExecutionTaskService:
    def __init__(self, repository: ExecutionTaskRepository) -> None:
        self.repository = repository

    async def create_draft(self, task: ExecutionTaskDraft) -> ExecutionTaskDraft:
        task.status = ExecutionTaskStatus.PENDING_CONFIRMATION
        return await self.repository.save(task)

    async def confirm(self, task_id: str) -> ExecutionTaskDraft:
        task = await self.repository.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != ExecutionTaskStatus.PENDING_CONFIRMATION:
            raise ValueError("only pending confirmation tasks can become ready")
        task.status = ExecutionTaskStatus.READY
        return await self.repository.save(task)

    async def update(
        self,
        task_id: str,
        *,
        owner: str | None = None,
        due_at: datetime | None = None,
        status: ExecutionTaskStatus | None = None,
    ) -> ExecutionTaskDraft:
        task = await self.repository.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if owner is not None:
            task.owner = owner
        if due_at is not None:
            task.due_at = due_at
        if status is not None:
            task.status = status
        return await self.repository.save(task)
