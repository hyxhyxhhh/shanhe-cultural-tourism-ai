"""Vendor-neutral job records and progress events."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEventType(StrEnum):
    JOB_STARTED = "job_started"
    PROGRESS = "progress"
    STEP_OUTPUT_UPDATED = "step_output_updated"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"


@dataclass
class JobRecord:
    activity_id: str
    kind: str
    idempotency_key: str
    step_no: int | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.QUEUED
    percent: int = 0
    message: str = "等待处理"
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "activityId": self.activity_id,
            "kind": self.kind,
            "idempotencyKey": self.idempotency_key,
            "stepNo": self.step_no,
            "status": self.status.value,
            "percent": self.percent,
            "message": self.message,
            "result": self.result,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    activity_id: str
    event_type: JobEventType
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    step_no: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "activityId": self.activity_id,
            "jobId": self.job_id,
            "stepNo": self.step_no,
            "type": self.event_type.value,
            "createdAt": self.created_at.isoformat(),
            "payload": self.payload,
        }
