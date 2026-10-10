"""Persistence boundary for long-running jobs.

The in-memory implementation is intentionally limited to local development and
tests. Production must provide a PostgreSQL implementation behind this Protocol.
"""

from collections.abc import Sequence
from copy import deepcopy
from typing import Protocol

from .models import JobEvent, JobRecord


class JobRepository(Protocol):
    async def find_by_idempotency(
        self,
        *,
        activity_id: str,
        kind: str,
        step_no: int | None,
        idempotency_key: str,
    ) -> JobRecord | None:
        ...

    async def get(self, job_id: str) -> JobRecord | None:
        ...

    async def create(self, job: JobRecord) -> JobRecord:
        ...

    async def save(self, job: JobRecord) -> JobRecord:
        ...

    async def append_event(self, event: JobEvent) -> JobEvent:
        ...

    async def events_since(self, job_id: str, event_id: str | None = None) -> Sequence[JobEvent]:
        ...


class InMemoryJobRepository:
    """A deterministic repository for tests; never use as production storage."""

    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}
        self.events: list[JobEvent] = []

    async def find_by_idempotency(
        self,
        *,
        activity_id: str,
        kind: str,
        step_no: int | None,
        idempotency_key: str,
    ) -> JobRecord | None:
        for job in self.jobs.values():
            if (
                job.activity_id == activity_id
                and job.kind == kind
                and job.step_no == step_no
                and job.idempotency_key == idempotency_key
            ):
                return deepcopy(job)
        return None

    async def get(self, job_id: str) -> JobRecord | None:
        job = self.jobs.get(job_id)
        return deepcopy(job) if job else None

    async def create(self, job: JobRecord) -> JobRecord:
        if any(
            item.activity_id == job.activity_id
            and item.kind == job.kind
            and item.step_no == job.step_no
            and item.idempotency_key == job.idempotency_key
            for item in self.jobs.values()
        ):
            raise ValueError("duplicate job idempotency key")
        self.jobs[job.id] = deepcopy(job)
        return deepcopy(job)

    async def save(self, job: JobRecord) -> JobRecord:
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = deepcopy(job)
        return deepcopy(job)

    async def append_event(self, event: JobEvent) -> JobEvent:
        self.events.append(event)
        return event

    async def events_since(self, job_id: str, event_id: str | None = None) -> Sequence[JobEvent]:
        events = [event for event in self.events if event.job_id == job_id]
        if event_id is None:
            return tuple(events)
        for index, event in enumerate(events):
            if event.event_id == event_id:
                return tuple(events[index + 1 :])
        return tuple(events)
