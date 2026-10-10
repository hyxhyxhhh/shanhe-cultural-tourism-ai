"""Authenticated public-data research route backed by Volcengine Global Search."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete

from backend.activity_steps import StepDomainError, find_step, get_owned_activity, patch_step
from backend.app.research.service import ResearchResult, ResearchService
from backend.app.research.selection import load_public_evidence, select_public_evidence
from backend.app.research.volcengine import SearchProviderError, VolcengineGlobalSearchProvider
from backend.auth import CurrentSession, DbSession
from backend.models import Activity, SourceReference


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=False)

    version: int = Field(ge=1)
    use_web_search: bool = Field(alias="useWebSearch")
    query_scope: list[
        Literal["weather", "holiday", "similar_events", "public_trend"]
    ] = Field(alias="queryScope", max_length=4)
    query: str | None = Field(default=None, max_length=70)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict) and any(field_value is None for field_value in value.values()):
            raise ValueError("research request fields must be omitted instead of null")
        return value

    @model_validator(mode="after")
    def validate_search_choice(self) -> "ResearchRequest":
        if len(set(self.query_scope)) != len(self.query_scope):
            raise ValueError("queryScope must not contain duplicates")
        if self.use_web_search:
            if not self.query_scope:
                raise ValueError("queryScope must contain at least one scope when web search is enabled")
            if self.query is None or not self.query or self.query != self.query.strip():
                raise ValueError("query must be non-empty without surrounding whitespace")
        elif self.query_scope or self.query is not None:
            raise ValueError("query and queryScope must be omitted when web search is disabled")
        return self


router = APIRouter(prefix="/api/activities/{activity_id}/research", tags=["research"])


def _owned_activity(activity_id: UUID, current, db, *, lock: bool = False) -> Activity:
    activity = get_owned_activity(
        activity_id=activity_id,
        owner_id=str(current.user_id),
        session=db,
        lock=lock,
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _provider(request: Request):
    injected = getattr(request.app.state, "research_provider", None)
    return injected if injected is not None else VolcengineGlobalSearchProvider.from_env()


def _search_http_error(exc: SearchProviderError) -> HTTPException:
    detail: dict[str, str] = {"code": exc.code, "message": exc.message}
    if exc.provider_request_id is not None:
        detail["requestId"] = exc.provider_request_id
    return HTTPException(status_code=exc.status_code, detail=detail)


def _step_http_error(exc: StepDomainError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": exc.code, "message": exc.message},
    )


def _assert_research_can_run(activity: Activity, version: int) -> None:
    step = find_step(activity=activity, step_no=2)
    if step.version != version:
        raise StepDomainError("VERSION_CONFLICT", f"Step version is {step.version}; refresh before searching")
    if activity.status not in {"draft", "running", "failed", "completed"}:
        raise StepDomainError(
            "ACTIVITY_NOT_WRITABLE",
            f"Research cannot be changed while activity status is {activity.status}",
        )
    if step.status == "locked":
        raise StepDomainError("STEP_LOCKED", "The brief must be confirmed before research")
    if step.status == "generating":
        raise StepDomainError("STEP_GENERATING", "Research is already being generated")
    if step.status == "confirmed":
        raise StepDomainError("STEP_REOPEN_REQUIRED", "Reopen the confirmed research step first")
    first_step = find_step(activity=activity, step_no=1)
    if first_step.status != "confirmed":
        raise StepDomainError("PREVIOUS_STEP_NOT_CONFIRMED", "Confirm step 1 before running research")
    if not activity.search_enabled or step.input_json.get("useWebSearch") is not True:
        raise StepDomainError("WEB_SEARCH_NOT_ENABLED", "Enable web search on step 2 before running research")


def _replace_persisted_sources(db, activity_id: UUID, result: ResearchResult) -> None:
    db.execute(
        delete(SourceReference).where(
            SourceReference.activity_id == activity_id,
            SourceReference.step_no == 2,
        )
    )
    db.add_all(
        SourceReference(
            activity_id=activity_id,
            step_no=2,
            source_type="public",
            label=item.label,
            url=item.url,
            captured_at=item.captured_at,
            excerpt=item.summary,
            published_at=item.published_at,
            site_name=item.site_name,
            authority_level=item.authority_level,
            rank=item.rank,
            provider_request_id=item.provider_request_id,
            scope=item.scope,
        )
        for item in result.items
    )


@router.get("/selection")
def get_research_selection(
    activity_id: UUID, current: CurrentSession, db: DbSession,
) -> dict[str, object]:
    activity = _owned_activity(activity_id, current, db)
    try:
        _, selection = select_public_evidence(load_public_evidence(db, activity.id))
    except ValueError as exc:
        raise _step_http_error(
            StepDomainError("PERSISTED_STEP_OUTPUT_INVALID", "Persisted public search evidence does not match its contract")
        ) from exc
    return {"activityId": str(activity.id), **selection}


@router.post("")
async def run_research(
    activity_id: UUID,
    payload: ResearchRequest,
    request: Request,
    current: CurrentSession,
    db: DbSession,
) -> dict[str, object]:
    activity = _owned_activity(activity_id, current, db, lock=payload.use_web_search)
    if not payload.use_web_search:
        return {
            "activityId": str(activity.id),
            "useWebSearch": False,
            "query": "",
            "queryScope": [],
            "sourceType": "missing",
            "items": [],
            "sourceReferences": [
                {
                    "sourceType": "missing",
                    "label": "用户未启用联网搜索",
                    "reasoning": "用户未启用联网搜索",
                }
            ],
            "warning": "用户未启用联网搜索",
        }

    try:
        _assert_research_can_run(activity, payload.version)
        result = await ResearchService(_provider(request)).run(
            query=payload.query or "",
            use_web_search=True,
            scopes=payload.query_scope,
        )
        step = find_step(activity=activity, step_no=2)
        patch_step(
            activity=activity,
            step=step,
            expected_version=payload.version,
            actor=str(current.user_id),
            session=db,
            output_json={},
            output_supplied=True,
        )
        db.flush()
        _replace_persisted_sources(db, activity.id, result)
        db.commit()
    except SearchProviderError as exc:
        db.rollback()
        raise _search_http_error(exc) from exc
    except StepDomainError as exc:
        db.rollback()
        raise _step_http_error(exc) from exc

    references = result.source_references()
    return {
        "activityId": str(activity.id),
        "useWebSearch": True,
        "query": result.query,
        "queryScope": list(result.scopes),
        "sourceType": "public",
        "items": [
            {
                "label": item.label,
                "summary": item.summary,
                "url": item.url,
                "capturedAt": item.captured_at.isoformat(),
                **({"publishedAt": item.published_at} if item.published_at is not None else {}),
                **({"siteName": item.site_name} if item.site_name is not None else {}),
                **(
                    {"authorityLevel": item.authority_level}
                    if item.authority_level is not None
                    else {}
                ),
                "rank": item.rank,
                "providerRequestId": item.provider_request_id,
                "scope": item.scope,
            }
            for item in result.items
        ],
        "sourceReferences": references,
    }
