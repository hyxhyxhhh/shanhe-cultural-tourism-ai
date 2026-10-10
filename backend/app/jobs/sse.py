"""Finite SSE serialization and replay helpers for persisted job events."""

import json
from collections.abc import AsyncIterator, Sequence

from fastapi.responses import StreamingResponse

from .models import JobEvent
from .repository import JobRepository


def format_event(event: JobEvent) -> str:
    return (
        f"id: {event.event_id}\n"
        f"event: {event.event_type.value}\n"
        f"data: {json.dumps(event.as_dict(), ensure_ascii=False)}\n\n"
    )


async def replay_events(repository: JobRepository, job_id: str, last_event_id: str | None = None) -> AsyncIterator[str]:
    events: Sequence[JobEvent] = await repository.events_since(job_id, last_event_id)
    for event in events:
        yield format_event(event)


def event_replay_response(
    repository: JobRepository,
    job_id: str,
    last_event_id: str | None = None,
) -> StreamingResponse:
    """Return currently persisted events and close once the replay is exhausted."""

    return StreamingResponse(
        replay_events(repository, job_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Event-Stream-Mode": "replay",
        },
    )
