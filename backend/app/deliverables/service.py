"""Versioned deliverable service; storage is injected by the application layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, Sequence
from uuid import uuid4

from .generator import (
    DeliverableFile,
    generate_budget_xlsx,
    generate_execution_tasks_xlsx,
    generate_plan_docx,
)


@dataclass(frozen=True)
class DeliverableRecord:
    activity_id: str
    filename: str
    content_type: str
    storage_key: str
    version: int
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DeliverableRepository(Protocol):
    async def save_batch(
        self, activity_id: str, files: Sequence[DeliverableFile]
    ) -> Sequence[DeliverableRecord]:
        ...

    async def list(self, activity_id: str) -> Sequence[DeliverableRecord]:
        ...

    async def read(self, record: DeliverableRecord) -> bytes:
        ...


class DeliverableService:
    """Generate fixed deliverable names without overwriting older versions."""

    def __init__(self, repository: DeliverableRepository) -> None:
        self.repository = repository

    async def list(self, activity_id: str) -> Sequence[DeliverableRecord]:
        return await self.repository.list(activity_id)

    async def read(self, record: DeliverableRecord) -> bytes:
        return await self.repository.read(record)

    async def generate_all(
        self,
        *,
        activity_id: str,
        title: str,
        sections: dict[str, str],
        budget_rows: list[dict[str, object]],
        execution_rows: list[dict[str, object]],
        preserve_document_lines: bool = False,
    ) -> list[DeliverableRecord]:
        files = [
            generate_plan_docx(title, sections, preserve_lines=preserve_document_lines),
            generate_budget_xlsx(budget_rows),
            generate_execution_tasks_xlsx(execution_rows),
        ]
        return list(await self.repository.save_batch(activity_id, files))
