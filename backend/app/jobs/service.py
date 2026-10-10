"""Idempotent job lifecycle and recoverable progress events."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from .models import JobEvent, JobEventType, JobRecord, JobStatus
from .repository import JobRepository

ProgressCallback = Callable[[int, str], Awaitable[None]]
JobWorker = Callable[[ProgressCallback], Awaitable[dict[str, Any]]]


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    async def get_or_create(
        self,
        *,
        activity_id: str,
        kind: str,
        idempotency_key: str,
        step_no: int | None = None,
    ) -> JobRecord:
        existing = await self.repository.find_by_idempotency(
            activity_id=activity_id,
            kind=kind,
            step_no=step_no,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing
        return await self.repository.create(
            JobRecord(
                activity_id=activity_id,
                kind=kind,
                idempotency_key=idempotency_key,
                step_no=step_no,
            )
        )

    async def execute(
        self,
        job: JobRecord,
        worker: JobWorker,
    ) -> JobRecord:
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
            return job
        job.error_code = None
        job.error_message = None
        await self._transition(job, JobStatus.RUNNING, 0, "开始处理", JobEventType.JOB_STARTED)

        async def progress(percent: int, message: str) -> None:
            bounded = max(0, min(100, percent))
            await self._transition(job, JobStatus.RUNNING, bounded, message, JobEventType.PROGRESS)

        try:
            result = await worker(progress)
        except Exception:
            job.error_code = "job_failed"
            job.error_message = "任务处理失败"
            await self._transition(job, JobStatus.FAILED, job.percent, "处理失败", JobEventType.JOB_FAILED)
            return job

        job.result = result
        await self._transition(job, JobStatus.COMPLETED, 100, "处理完成", JobEventType.JOB_COMPLETED)
        return job

    async def get(self, job_id: str) -> JobRecord | None:
        return await self.repository.get(job_id)

    async def events_since(self, job_id: str, event_id: str | None = None) -> Sequence[JobEvent]:
        return await self.repository.events_since(job_id, event_id)

    async def _transition(
        self,
        job: JobRecord,
        status: JobStatus,
        percent: int,
        message: str,
        event_type: JobEventType,
    ) -> None:
        job.status = status
        job.percent = percent
        job.message = message
        job.touch()
        await self.repository.save(job)
        await self.repository.append_event(
            JobEvent(
                job_id=job.id,
                activity_id=job.activity_id,
                step_no=job.step_no,
                event_type=event_type,
                payload={"percent": percent, "message": message},
            )
        )
