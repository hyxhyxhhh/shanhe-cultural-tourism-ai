"""Generation endpoints for the activity agent's steps five through nine."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from backend.app.jobs import JobService, event_replay_response
from backend.app.jobs.repository import JobRepository
from backend.auth import CurrentSession, DbSession
from backend.models import Activity


router = APIRouter(prefix="/api/activities/{activity_id}/steps", tags=["generation"])


def _owned_activity(activity_id: UUID, current, db) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.created_by == str(current.user_id))
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _job_repository(request: Request) -> JobRepository:
    repository = getattr(request.app.state, "job_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation job storage is not configured",
        )
    return repository


@router.get("/{step_no}/jobs/{job_id}")
async def get_generation_job(
    activity_id: UUID,
    step_no: int,
    job_id: str,
    current: CurrentSession,
    db: DbSession,
    request: Request,
) -> dict[str, object]:
    _owned_activity(activity_id, current, db)
    repository = _job_repository(request)
    job = await JobService(repository).get(job_id)
    if job is None or job.activity_id != str(activity_id) or job.step_no != step_no:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job.as_dict()


@router.get("/{step_no}/jobs/{job_id}/stream")
async def replay_generation_job_events(
    activity_id: UUID,
    step_no: int,
    job_id: str,
    current: CurrentSession,
    db: DbSession,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    _owned_activity(activity_id, current, db)
    repository = _job_repository(request)
    job = await JobService(repository).get(job_id)
    if job is None or job.activity_id != str(activity_id) or job.step_no != step_no:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return event_replay_response(repository, job_id, last_event_id)
