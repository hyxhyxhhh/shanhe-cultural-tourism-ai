from __future__ import annotations

import json
import logging
import math
import time
from copy import deepcopy
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.activities import (
    InvalidActivityTransition,
    archive_activity,
    create_activity,
    get_activity,
    list_activities,
    pause_activity,
    update_activity,
)
from backend.activity_steps import (
    StepDomainError,
    complete_generation,
    confirm_step,
    fail_generation,
    find_step,
    generation_failure_diagnostic,
    get_owned_activity,
    list_steps,
    patch_step,
    reopen_step,
    start_generation,
    validate_generated_output,
    validate_step_output,
)
from backend.auth import AuthenticatedUser, require_session
from backend.ccode_provider import (
    CcodeModelProvider,
    CcodeProviderError,
    ModelMessage,
    ModelProvider,
    ModelResult,
)
from backend.db import SessionLocal
from backend.models import Activity, ActivityStep, ModelRun
from backend.app.research.selection import load_public_evidence, select_public_evidence
from backend.research_generation import (
    ScopeProgress, aggregate_scope_audit, complete_research_group_generation,
    initial_scope_progress, merged_scope_output, progress_snapshot, scope_messages, validate_scope_citations,
)
from backend.model_catalog import AllowedModels


logger = logging.getLogger(__name__)


ActivityStatusValue = Literal["draft", "running", "paused", "completed", "failed", "archived"]
ActivityStepStatusValue = Literal[
    "locked", "draft", "generating", "review", "confirmed", "needs_review", "failed"
]
ActivityStepNoValue = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9]
ActivityStepKeyValue = Literal[
    "brief",
    "research",
    "theme",
    "content_space",
    "budget",
    "promotion",
    "execution_plan",
    "channel_business",
    "review",
]


class ActivityBriefInputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    idea: str = Field(min_length=1, max_length=5000)
    planning_mode: Literal["single", "annual"] = Field(default="single", alias="planningMode")
    location: str | None = Field(default=None, max_length=500)
    planned_start_at: datetime | None = Field(default=None, alias="plannedStartAt")
    planned_end_at: datetime | None = Field(default=None, alias="plannedEndAt")
    target: str | None = Field(default=None, max_length=1000)
    budget_min: float | None = Field(default=None, ge=0, alias="budgetMin")
    budget_max: float | None = Field(default=None, ge=0, alias="budgetMax")
    target_audience: str | None = Field(default=None, max_length=2000, alias="targetAudience")
    known_constraints: str | None = Field(default=None, max_length=5000, alias="knownConstraints")
    annual_period: str | None = Field(default=None, min_length=1, max_length=200, alias="annualPeriod")
    annual_goals: str | None = Field(default=None, min_length=1, max_length=5000, alias="annualGoals")
    planned_event_count: int | None = Field(default=None, ge=2, le=12, strict=True, alias="plannedEventCount")

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict) and any(field_value is None for field_value in value.values()):
            raise ValueError("activity brief fields must be omitted instead of null")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> ActivityBriefInputDTO:
        for value in (self.budget_min, self.budget_max):
            if value is not None and not math.isfinite(value):
                raise ValueError("budget values must be finite")
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budgetMin cannot exceed budgetMax")
        if self.planned_start_at is not None and self.planned_start_at.utcoffset() is None:
            raise ValueError("plannedStartAt must include a timezone")
        if self.planned_end_at is not None and self.planned_end_at.utcoffset() is None:
            raise ValueError("plannedEndAt must include a timezone")
        if (
            self.planned_start_at is not None
            and self.planned_end_at is not None
            and self.planned_start_at >= self.planned_end_at
        ):
            raise ValueError("plannedStartAt must be earlier than plannedEndAt")
        annual_fields = (self.annual_period, self.annual_goals, self.planned_event_count)
        if self.planning_mode == "annual" and any(value is None for value in annual_fields):
            raise ValueError("annual planning requires annualPeriod, annualGoals, and plannedEventCount")
        if self.planning_mode == "single" and any(value is not None for value in annual_fields):
            raise ValueError("annual planning fields require planningMode annual")
        return self

    @model_serializer(mode="wrap")
    def serialize_sparse(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}


class CreateActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    input: ActivityBriefInputDTO


class UpdateActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["draft", "running"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> UpdateActivityRequest:
        if not self.model_fields_set:
            raise ValueError("at least one activity field is required")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class ActivityStepDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    activity_id: UUID = Field(alias="activityId")
    step_no: ActivityStepNoValue = Field(alias="stepNo")
    step_key: ActivityStepKeyValue = Field(alias="stepKey")
    status: ActivityStepStatusValue
    input_json: dict = Field(alias="inputJson")
    output_json: dict[str, Any] = Field(alias="outputJson")
    version: int
    confirmed_by: str | None = Field(alias="confirmedBy")
    confirmed_at: datetime | None = Field(alias="confirmedAt")
    updated_at: datetime = Field(alias="updatedAt")


class ActivityDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    title: str
    status: ActivityStatusValue
    current_step: ActivityStepNoValue = Field(alias="currentStep")
    input: ActivityBriefInputDTO
    search_enabled: bool = Field(alias="searchEnabled")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    steps: list[ActivityStepDTO]


class PatchStepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    input_json: dict[str, Any] | None = Field(default=None, alias="inputJson")
    output_json: dict[str, Any] | None = Field(default=None, alias="outputJson")

    @model_validator(mode="after")
    def require_content(self) -> PatchStepRequest:
        supplied = self.model_fields_set - {"version"}
        if not supplied:
            raise ValueError("inputJson or outputJson is required")
        for field_name in supplied:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class StepVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=1)


class GenerateStepRequest(StepVersionRequest):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    model: str = Field(min_length=1, max_length=200, strict=True)

    @model_validator(mode="after")
    def validate_model(self) -> GenerateStepRequest:
        if self.model != self.model.strip():
            raise ValueError("model must not contain leading or trailing whitespace")
        return self


class ReopenStepRequest(StepVersionRequest):
    comment: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def reject_explicit_null_comment(self) -> ReopenStepRequest:
        if "comment" in self.model_fields_set and self.comment is None:
            raise ValueError("comment must be omitted instead of null")
        return self


class ConfirmStepRequest(StepVersionRequest):
    comment: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def reject_explicit_null_comment(self) -> ConfirmStepRequest:
        if "comment" in self.model_fields_set and self.comment is None:
            raise ValueError("comment must be omitted instead of null")
        return self


class _LazyCcodeProvider:
    def generate(self, messages, *, model, metadata=None):
        with CcodeModelProvider.from_env() as provider:
            return provider.generate(messages, model=model, metadata=metadata)


def get_activity_db_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def get_model_provider() -> ModelProvider:
    # Delay environment validation until generate() so the step and model-run
    # failure are persisted even when deployment configuration is incomplete.
    return _LazyCcodeProvider()


ActivityDb = Annotated[Session, Depends(get_activity_db_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_session)]
GenerationProvider = Annotated[ModelProvider, Depends(get_model_provider)]

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _brief_dict(payload: ActivityBriefInputDTO) -> dict:
    return payload.model_dump(by_alias=True, exclude_none=True, mode="json")


def _persisted_output_uses_web_search(
    step: ActivityStep,
    output_json: dict[str, Any],
) -> bool:
    if step.step_no != 2:
        return False
    sources = output_json.get("sources")
    if not isinstance(sources, list):
        return False
    return any(
        isinstance(source, dict) and source.get("sourceType") == "public"
        for source in sources
    )


def _step_dto(step: ActivityStep, *, planning_mode: Literal["single", "annual"] = "single") -> ActivityStepDTO:
    output_json = dict(step.output_json)
    if output_json:
        try:
            output_json = validate_step_output(
                step.step_no,
                output_json,
                # Persisted output may outlive the current search toggle. Select
                # the semantic branch from the saved evidence, then run the full
                # schema and source-evidence validation unchanged.
                search_enabled=_persisted_output_uses_web_search(step, output_json),
                planning_mode=planning_mode,
                error_code="PERSISTED_STEP_OUTPUT_INVALID",
            )
        except StepDomainError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
    return ActivityStepDTO(
        id=step.id,
        activityId=step.activity_id,
        stepNo=step.step_no,
        stepKey=step.step_key,
        status=step.status,
        inputJson=step.input_json,
        outputJson=output_json,
        version=step.version,
        confirmedBy=step.confirmed_by,
        confirmedAt=step.confirmed_at,
        updatedAt=step.updated_at,
    )


def serialize_activity(activity: Activity) -> ActivityDTO:
    return ActivityDTO(
        id=activity.id,
        title=activity.title,
        status=activity.status,
        currentStep=activity.current_step,
        input=ActivityBriefInputDTO.model_validate(activity.input),
        searchEnabled=activity.search_enabled,
        createdBy=activity.created_by,
        createdAt=activity.created_at,
        updatedAt=activity.updated_at,
        steps=[_step_dto(step, planning_mode=activity.input.get("planningMode", "single")) for step in sorted(activity.steps, key=lambda item: item.step_no)],
    )


def _owned_activity(activity_id: UUID, current: AuthenticatedUser, db: Session) -> Activity:
    activity = get_activity(activity_id=activity_id, created_by=str(current.user_id), session=db)
    if activity is None:
        # Deliberately use the same response for an unknown ID and another user's ID.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _conflict(exc: InvalidActivityTransition) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _step_error(exc: StepDomainError, *, status_code: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def _step_write_error(exc: StepDomainError) -> HTTPException:
    validation_codes = {"INVALID_STEP_INPUT", "INVALID_STEP_OUTPUT"}
    return _step_error(
        exc,
        status_code=(
            status.HTTP_422_UNPROCESSABLE_CONTENT
            if exc.code in validation_codes
            else status.HTTP_409_CONFLICT
        ),
    )


def _provider_status(exc: CcodeProviderError) -> int:
    mapping = {
        "CCODE_NOT_CONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CCODE_AUTHENTICATION_FAILED": status.HTTP_502_BAD_GATEWAY,
        "CCODE_BALANCE_INSUFFICIENT": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CCODE_RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
        "CCODE_MODEL_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CCODE_TIMEOUT": status.HTTP_504_GATEWAY_TIMEOUT,
        "CCODE_NETWORK_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CCODE_UPSTREAM_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CCODE_REQUEST_REJECTED": status.HTTP_502_BAD_GATEWAY,
        "CCODE_INVALID_RESPONSE": status.HTTP_502_BAD_GATEWAY,
    }
    try:
        return mapping[exc.error_code]
    except KeyError as unknown_code:
        raise RuntimeError(f"Unsupported provider error code: {exc.error_code}") from unknown_code


def _provider_public_error(exc: CcodeProviderError) -> tuple[str, str]:
    mapping = {
        "CCODE_NOT_CONFIGURED": ("PROVIDER_NOT_CONFIGURED", "The generation service is not configured"),
        "CCODE_AUTHENTICATION_FAILED": ("PROVIDER_AUTH_ERROR", "The generation service rejected its credentials"),
        "CCODE_BALANCE_INSUFFICIENT": ("PROVIDER_BALANCE_ERROR", "The generation service has insufficient balance"),
        "CCODE_RATE_LIMITED": ("PROVIDER_RATE_LIMITED", "The generation service is rate limited"),
        "CCODE_MODEL_UNAVAILABLE": ("MODEL_UNAVAILABLE", "The configured generation model is unavailable"),
        "CCODE_TIMEOUT": ("PROVIDER_TIMEOUT", "The generation service timed out"),
        "CCODE_NETWORK_ERROR": ("PROVIDER_UNAVAILABLE", "The generation service is unavailable"),
        "CCODE_UPSTREAM_ERROR": ("PROVIDER_UNAVAILABLE", "The generation service is unavailable"),
        "CCODE_REQUEST_REJECTED": ("PROVIDER_UNAVAILABLE", "The generation request was rejected"),
        "CCODE_INVALID_RESPONSE": ("INVALID_MODEL_RESPONSE", "The generation service returned an invalid response"),
    }
    try:
        return mapping[exc.error_code]
    except KeyError as unknown_code:
        raise RuntimeError(f"Unsupported provider error code: {exc.error_code}") from unknown_code


def _locked_step(
    activity_id: UUID,
    step_no: int,
    current: AuthenticatedUser,
    db: Session,
) -> tuple[Activity, ActivityStep]:
    activity = get_owned_activity(
        activity_id=activity_id,
        owner_id=str(current.user_id),
        session=db,
        lock=True,
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    try:
        return activity, find_step(activity=activity, step_no=step_no)
    except StepDomainError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity step not found") from exc


@router.get("", response_model=list[ActivityDTO])
def get_activities(
    current: CurrentUser,
    db: ActivityDb,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
) -> list[ActivityDTO]:
    activities = list_activities(
        created_by=str(current.user_id),
        include_archived=include_archived,
        session=db,
    )
    return [serialize_activity(activity) for activity in activities]


@router.post("", response_model=ActivityDTO, status_code=status.HTTP_201_CREATED)
def post_activity(payload: CreateActivityRequest, current: CurrentUser, db: ActivityDb) -> ActivityDTO:
    brief = _brief_dict(payload.input)
    activity = create_activity(
        title=payload.title,
        idea=payload.input.idea,
        created_by=str(current.user_id),
        input_data=brief,
        session=db,
    )
    db.commit()
    return serialize_activity(activity)


@router.get("/{activity_id}", response_model=ActivityDTO)
def get_activity_by_id(activity_id: UUID, current: CurrentUser, db: ActivityDb) -> ActivityDTO:
    return serialize_activity(_owned_activity(activity_id, current, db))


@router.patch("/{activity_id}", response_model=ActivityDTO)
def patch_activity(
    activity_id: UUID,
    payload: UpdateActivityRequest,
    current: CurrentUser,
    db: ActivityDb,
) -> ActivityDTO:
    activity = _owned_activity(activity_id, current, db)
    try:
        update_activity(
            activity=activity,
            title=payload.title if "title" in payload.model_fields_set else None,
            status=payload.status if "status" in payload.model_fields_set else None,
            session=db,
        )
    except InvalidActivityTransition as exc:
        db.rollback()
        raise _conflict(exc) from exc
    db.commit()
    return serialize_activity(activity)


@router.post("/{activity_id}/pause", response_model=ActivityDTO)
def post_pause(activity_id: UUID, current: CurrentUser, db: ActivityDb) -> ActivityDTO:
    activity = _owned_activity(activity_id, current, db)
    try:
        pause_activity(activity=activity, session=db)
    except InvalidActivityTransition as exc:
        db.rollback()
        raise _conflict(exc) from exc
    db.commit()
    return serialize_activity(activity)


@router.post("/{activity_id}/archive", response_model=ActivityDTO)
def post_archive(activity_id: UUID, current: CurrentUser, db: ActivityDb) -> ActivityDTO:
    activity = _owned_activity(activity_id, current, db)
    try:
        archive_activity(activity=activity, session=db)
    except InvalidActivityTransition as exc:
        db.rollback()
        raise _conflict(exc) from exc
    db.commit()
    return serialize_activity(activity)


@router.get("/{activity_id}/steps", response_model=list[ActivityStepDTO])
def get_activity_steps(activity_id: UUID, current: CurrentUser, db: ActivityDb) -> list[ActivityStepDTO]:
    activity = get_owned_activity(
        activity_id=activity_id,
        owner_id=str(current.user_id),
        session=db,
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return [_step_dto(step, planning_mode=activity.input.get("planningMode", "single")) for step in list_steps(activity=activity)]


@router.get("/{activity_id}/steps/{step_no}", response_model=ActivityStepDTO)
def get_activity_step(
    activity_id: UUID,
    step_no: int,
    current: CurrentUser,
    db: ActivityDb,
) -> ActivityStepDTO:
    activity, step = _locked_step(activity_id, step_no, current, db)
    return _step_dto(step, planning_mode=activity.input.get("planningMode", "single"))


@router.patch("/{activity_id}/steps/{step_no}", response_model=ActivityStepDTO)
def patch_activity_step(
    activity_id: UUID,
    step_no: int,
    payload: PatchStepRequest,
    current: CurrentUser,
    db: ActivityDb,
) -> ActivityStepDTO:
    activity, step = _locked_step(activity_id, step_no, current, db)
    try:
        patch_step(
            activity=activity,
            step=step,
            expected_version=payload.version,
            actor=str(current.user_id),
            session=db,
            input_json=payload.input_json,
            output_json=payload.output_json,
            input_supplied="input_json" in payload.model_fields_set,
            output_supplied="output_json" in payload.model_fields_set,
        )
    except StepDomainError as exc:
        db.rollback()
        raise _step_write_error(exc) from exc
    db.commit()
    return _step_dto(step, planning_mode=activity.input.get("planningMode", "single"))


@router.post("/{activity_id}/steps/{step_no}/confirm", response_model=ActivityStepDTO)
def post_confirm_activity_step(
    activity_id: UUID,
    step_no: int,
    payload: ConfirmStepRequest,
    current: CurrentUser,
    db: ActivityDb,
) -> ActivityStepDTO:
    activity, step = _locked_step(activity_id, step_no, current, db)
    try:
        confirm_step(
            activity=activity,
            step=step,
            expected_version=payload.version,
            actor=str(current.user_id),
            comment=payload.comment,
            session=db,
        )
    except StepDomainError as exc:
        db.rollback()
        raise _step_error(
            exc,
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
                if exc.code == "PERSISTED_STEP_OUTPUT_INVALID"
                else status.HTTP_409_CONFLICT
            ),
        ) from exc
    db.commit()
    return _step_dto(step, planning_mode=activity.input.get("planningMode", "single"))


@router.post("/{activity_id}/steps/{step_no}/reopen", response_model=ActivityStepDTO)
def post_reopen_activity_step(
    activity_id: UUID,
    step_no: int,
    payload: ReopenStepRequest,
    current: CurrentUser,
    db: ActivityDb,
) -> ActivityStepDTO:
    activity, step = _locked_step(activity_id, step_no, current, db)
    try:
        reopen_step(
            activity=activity,
            step=step,
            expected_version=payload.version,
            actor=str(current.user_id),
            comment=payload.comment,
            session=db,
        )
    except StepDomainError as exc:
        db.rollback()
        raise _step_error(exc) from exc
    db.commit()
    return _step_dto(step, planning_mode=activity.input.get("planningMode", "single"))


@router.post("/{activity_id}/steps/{step_no}/generate", response_model=ActivityStepDTO)
def post_generate_activity_step(
    activity_id: UUID,
    step_no: int,
    payload: GenerateStepRequest,
    current: CurrentUser,
    db: ActivityDb,
    provider: GenerationProvider,
    allowed_models: AllowedModels,
) -> ActivityStepDTO:
    activity, step = _locked_step(activity_id, step_no, current, db)
    if step_no == 2 and activity.search_enabled:
        db.rollback()
        raise _step_error(StepDomainError("USE_RESEARCH_STREAM_ENDPOINT", "Web research generation requires the per-scope streaming endpoint"))
    if activity.input.get("planningMode", "single") == "annual" and step_no >= 3:
        db.rollback()
        raise _step_error(StepDomainError("USE_PLANNING_STREAM_ENDPOINT", "Annual planning requires per-unit streaming generation"))
    saved_step_output = dict(step.output_json)
    if payload.model not in allowed_models:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "MODEL_NOT_ALLOWED",
                "message": "The selected model is not allowed",
            },
        )
    try:
        generation_id, raw_messages = start_generation(
            activity=activity,
            step=step,
            expected_version=payload.version,
            model=payload.model,
            actor=str(current.user_id),
            session=db,
        )
    except StepDomainError as exc:
        db.rollback()
        raise _step_error(exc) from exc
    db.commit()

    messages = [ModelMessage(role=message["role"], content=message["content"]) for message in raw_messages]
    result = None
    try:
        result = provider.generate(
            messages,
            model=payload.model,
            metadata={
                "activity_id": str(activity_id),
                "step_no": step_no,
                "generation_id": str(generation_id),
            },
        )
        generated_output = validate_generated_output(
            step_no,
            result.text,
            search_enabled=activity.search_enabled,
            planning_mode=activity.input.get("planningMode", "single"),
            saved_step_output=saved_step_output,
        )
    except CcodeProviderError as exc:
        try:
            _persist_generation_failure(
                db=db,
                activity_id=activity_id,
                step_no=step_no,
                current=current,
                generation_id=generation_id,
                error_code=exc.error_code,
                model=payload.model,
                request_id=exc.request_id,
            )
        except StepDomainError as state_exc:
            raise _step_error(state_exc) from exc
        public_code, public_message = _provider_public_error(exc)
        raise HTTPException(
            status_code=_provider_status(exc),
            detail={
                "code": public_code,
                "message": public_message,
                "generationId": str(generation_id),
            },
        ) from exc
    except StepDomainError as exc:
        logger.warning(
            "activity_generation_validation_failed %s",
            json.dumps(generation_failure_diagnostic(
                exc, step_no=step_no, response_text=result.text if result else None,
                planning_mode=activity.input.get("planningMode", "single"),
            ), sort_keys=True),
        )
        try:
            _persist_generation_failure(
                db=db,
                activity_id=activity_id,
                step_no=step_no,
                current=current,
                generation_id=generation_id,
                error_code=exc.code,
                model=payload.model,
                request_id=result.provider_request_id if result else None,
                duration_ms=result.duration_ms if result else None,
                usage=_result_usage(result) if result else None,
            )
        except StepDomainError as state_exc:
            raise _step_error(state_exc) from exc
        raise _step_error(exc, status_code=status.HTTP_502_BAD_GATEWAY) from exc
    activity, step = _locked_step(activity_id, step_no, current, db)
    try:
        complete_generation(
            activity=activity,
            step=step,
            generation_id=generation_id,
            actor=str(current.user_id),
            output_json=generated_output,
            model=payload.model,
            request_id=result.provider_request_id,
            duration_ms=result.duration_ms,
            usage=_result_usage(result),
            session=db,
        )
    except StepDomainError as exc:
        db.rollback()
        if exc.code in {
            "INVALID_STEP_OUTPUT", "PERSISTED_STEP_OUTPUT_INVALID",
            "PUBLIC_CITATION_METADATA_MISMATCH", "PUBLIC_CITATION_EXCERPT_MISMATCH",
        }:
            try:
                _persist_generation_failure(
                    db=db, activity_id=activity_id, step_no=step_no, current=current,
                    generation_id=generation_id, error_code=exc.code,
                    model=payload.model, request_id=result.provider_request_id,
                    duration_ms=result.duration_ms, usage=_result_usage(result),
                )
            except StepDomainError as state_exc:
                raise _step_error(state_exc) from exc
            raise _step_error(exc, status_code=status.HTTP_502_BAD_GATEWAY) from exc
        raise _step_error(exc) from exc
    db.commit()
    return _step_dto(step, planning_mode=activity.input.get("planningMode", "single"))


def _result_usage(result: ModelResult) -> dict[str, int]:
    return {
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
    }


def _research_public_code(code: str) -> str:
    if code.startswith("CCODE_"):
        mapping = {
            "CCODE_NOT_CONFIGURED": "PROVIDER_NOT_CONFIGURED", "CCODE_AUTHENTICATION_FAILED": "PROVIDER_AUTH_ERROR",
            "CCODE_BALANCE_INSUFFICIENT": "PROVIDER_BALANCE_ERROR", "CCODE_RATE_LIMITED": "PROVIDER_RATE_LIMITED",
            "CCODE_MODEL_UNAVAILABLE": "MODEL_UNAVAILABLE", "CCODE_TIMEOUT": "PROVIDER_TIMEOUT",
            "CCODE_NETWORK_ERROR": "PROVIDER_UNAVAILABLE", "CCODE_UPSTREAM_ERROR": "PROVIDER_UNAVAILABLE",
            "CCODE_REQUEST_REJECTED": "PROVIDER_UNAVAILABLE", "CCODE_INVALID_RESPONSE": "INVALID_MODEL_RESPONSE",
        }
        if code not in mapping:
            raise RuntimeError("Unsupported research provider error code")
        return mapping[code]
    return code


def _locked_research_run(activity_id, generation_id, current, db):
    from backend.activity_steps import _active_run
    activity, step = _locked_step(activity_id, 2, current, db)
    run = _active_run(db, generation_id)
    if run.activity_id != activity.id or run.step_no != 2 or step.status != "generating":
        raise StepDomainError("GENERATION_STALE", "Research generation is no longer active")
    ScopeProgress.model_validate(run.scope_progress)
    return activity, step, run


def _record_research_scope(activity_id, generation_id, current, db, scope, scope_status, *, result=None):
    _activity, _step, run = _locked_research_run(activity_id, generation_id, current, db)
    progress = deepcopy(run.scope_progress)
    entry = next(item for item in progress["scopes"] if item["scope"] == scope)
    if scope_status not in {"running", "completed"} or (scope_status == "running" and entry["status"] != "waiting") or (scope_status == "completed" and entry["status"] != "running"):
        raise StepDomainError("INVALID_GENERATION_METADATA", "Research scope progress transition is invalid")
    entry["status"] = scope_status
    if result is not None:
        entry.update(model=result.model, providerRequestId=result.provider_request_id, durationMs=result.duration_ms,
                     promptTokens=result.prompt_tokens, completionTokens=result.completion_tokens, totalTokens=result.total_tokens)
    run.scope_progress = ScopeProgress.model_validate(progress).model_dump(exclude_none=True)
    snapshot = progress_snapshot(run)
    db.commit()
    return snapshot


def _fail_research_group(activity_id, generation_id, current, db, error_code, model, *, failed_scope=None, result=None, duration_ms=None, request_id=None):
    db.rollback()
    _activity, _step, run = _locked_research_run(activity_id, generation_id, current, db)
    progress = deepcopy(run.scope_progress)
    for item in progress["scopes"]:
        if item["scope"] == failed_scope:
            if item["status"] != "running":
                raise StepDomainError("INVALID_GENERATION_METADATA", "Only the current running scope can fail")
            item.update(status="failed", errorCode=error_code)
            if result is not None:
                item.update(model=result.model, providerRequestId=result.provider_request_id, durationMs=result.duration_ms,
                            promptTokens=result.prompt_tokens, completionTokens=result.completion_tokens, totalTokens=result.total_tokens)
            else:
                item["model"] = model
                if duration_ms is not None:
                    item["durationMs"] = duration_ms
                if request_id is not None:
                    item["providerRequestId"] = request_id
            continue
        if item["status"] in {"waiting", "running"}:
            item["status"] = "cancelled"
            item["errorCode"] = "GENERATION_INTERRUPTED" if error_code == "GENERATION_INTERRUPTED" else "RESEARCH_SCOPE_CANCELLED"
    run.scope_progress = ScopeProgress.model_validate(progress).model_dump(exclude_none=True)
    aggregate = aggregate_scope_audit(run.scope_progress)
    fail_generation(activity=_activity, step=_step, generation_id=generation_id, actor=str(current.user_id),
                    error_code=error_code, model=model, request_id=None, session=db, **aggregate)
    snapshot = progress_snapshot(run, error_code=_research_public_code(error_code))
    db.commit()
    return snapshot


@router.get("/{activity_id}/research/generate/progress")
def get_research_generation_progress(activity_id: UUID, current: CurrentUser, db: ActivityDb):
    _owned_activity(activity_id, current, db)
    run = db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id, ModelRun.step_no == 2)
                    .order_by(ModelRun.started_at.desc(), ModelRun.id.desc()).limit(1))
    if run is None or run.scope_progress is None:
        return {"activityId": str(activity_id), "progress": None}
    return {"activityId": str(activity_id), "progress": progress_snapshot(run, error_code=_research_public_code(run.error_code) if run.error_code else None)}


@router.post("/{activity_id}/research/generate/stream")
def stream_research_generation(
    activity_id: UUID, payload: GenerateStepRequest, request: Request,
    current: CurrentUser, db: ActivityDb, provider: GenerationProvider, allowed_models: AllowedModels,
):
    activity, step = _locked_step(activity_id, 2, current, db)
    if not activity.search_enabled or step.input_json.get("useWebSearch") is not True:
        db.rollback()
        raise _step_error(StepDomainError("WEB_SEARCH_NOT_ENABLED", "Research scope generation requires saved web search selection"))
    if payload.model not in allowed_models:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": "MODEL_NOT_ALLOWED", "message": "The selected model is not allowed"})
    try:
        evidence, _selection = select_public_evidence(load_public_evidence(db, activity_id))
        if not evidence:
            raise StepDomainError("RESEARCH_EVIDENCE_REQUIRED", "Research scope generation requires persisted search evidence")
        generation_id, raw_messages = start_generation(activity=activity, step=step, expected_version=payload.version,
                                                       model=payload.model, actor=str(current.user_id), session=db)
        run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id))
        run.scope_progress = initial_scope_progress(evidence)
        initial = progress_snapshot(run)
        db.commit()
    except StepDomainError as exc:
        db.rollback()
        raise _step_error(exc) from exc
    except ValueError as exc:
        db.rollback()
        raise _step_error(StepDomainError("PERSISTED_STEP_OUTPUT_INVALID", "Research evidence does not match its contract")) from exc

    def event(name, value):
        return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"

    async def events():
        terminal = False
        outputs = []
        current_scope = None
        result = None
        started = None
        try:
            yield event("research_progress", initial)
            for item in initial["scopes"]:
                if await request.is_disconnected():
                    return
                current_scope = item["scope"]
                result = None
                started = time.perf_counter()
                snapshot = _record_research_scope(activity_id, generation_id, current, db, current_scope, "running")
                yield event("research_progress", snapshot)
                scoped_messages, scoped_evidence = scope_messages(raw_messages, current_scope, initial["totalScopes"])
                # Shield an in-flight synchronous provider call so its actual audit is retained on disconnect.
                with anyio.CancelScope(shield=True):
                    result = await anyio.to_thread.run_sync(lambda: provider.generate(
                        [ModelMessage(**message) for message in scoped_messages], model=payload.model,
                        metadata={"activity_id": str(activity_id), "step_no": 2, "generation_id": str(generation_id), "research_scope": current_scope},
                    ))
                output = validate_generated_output(2, result.text, search_enabled=True)
                validate_scope_citations(output, scoped_evidence, required_scope=current_scope)
                activity_locked, _step_locked, _run_locked = _locked_research_run(activity_id, generation_id, current, db)
                current_evidence, _ = select_public_evidence(load_public_evidence(db, activity_locked.id))
                validate_scope_citations(output, [entry for entry in current_evidence if entry["scope"] == current_scope], required_scope=current_scope)
                outputs.append((current_scope, output))
                snapshot = _record_research_scope(activity_id, generation_id, current, db, current_scope, "completed", result=result)
                current_scope = None
                yield event("research_progress", snapshot)
            if await request.is_disconnected():
                return
            merged = merged_scope_output(outputs)
            activity_locked, step_locked, run_locked = _locked_research_run(activity_id, generation_id, current, db)
            complete_research_group_generation(activity=activity_locked, step=step_locked, generation_id=generation_id,
                                              actor=str(current.user_id), output_json=merged, model=payload.model,
                                              session=db, **aggregate_scope_audit(run_locked.scope_progress))
            step_dto = _step_dto(step_locked).model_dump(by_alias=True, mode="json")
            snapshot = progress_snapshot(run_locked)
            db.commit()
            terminal = True
            yield event("research_completed", {**snapshot, "step": step_dto})
        except (CcodeProviderError, StepDomainError) as exc:
            db.rollback()
            code = exc.error_code if isinstance(exc, CcodeProviderError) else exc.code
            if isinstance(exc, StepDomainError):
                logger.warning("activity_generation_validation_failed %s", json.dumps(generation_failure_diagnostic(
                    exc, step_no=2, response_text=result.text if result else None,
                ), sort_keys=True))
            run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id).with_for_update())
            if run is not None and run.status == "failed" and run.error_code == "GENERATION_SUPERSEDED":
                if current_scope is not None:
                    progress = deepcopy(run.scope_progress)
                    entry = next(item for item in progress["scopes"] if item["scope"] == current_scope)
                    if entry["status"] != "failed":
                        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Superseded in-flight scope must be failed")
                    if result is not None:
                        entry.update(model=result.model, providerRequestId=result.provider_request_id, durationMs=result.duration_ms,
                                     promptTokens=result.prompt_tokens, completionTokens=result.completion_tokens, totalTokens=result.total_tokens)
                    else:
                        entry["model"] = payload.model
                        if started is not None:
                            entry["durationMs"] = max(0, round((time.perf_counter() - started) * 1000))
                        if isinstance(exc, CcodeProviderError) and exc.request_id is not None:
                            entry["providerRequestId"] = exc.request_id
                    run.scope_progress = ScopeProgress.model_validate(progress).model_dump(exclude_none=True)
                    aggregate = aggregate_scope_audit(run.scope_progress)
                    run.duration_ms = aggregate["duration_ms"]
                    run.prompt_tokens = aggregate["usage"]["prompt_tokens"]
                    run.completion_tokens = aggregate["usage"]["completion_tokens"]
                    run.total_tokens = aggregate["usage"]["total_tokens"]
                snapshot = progress_snapshot(run, error_code=_research_public_code(run.error_code))
                db.commit()
                terminal = True
                yield event("research_failed", snapshot)
                return
            if code == "GENERATION_STALE":
                raise
            db.rollback()
            snapshot = _fail_research_group(activity_id, generation_id, current, db, code, payload.model,
                                            failed_scope=current_scope, result=result,
                                            duration_ms=max(0, round((time.perf_counter() - started) * 1000)) if started else None,
                                            request_id=exc.request_id if isinstance(exc, CcodeProviderError) else None)
            terminal = True
            yield event("research_failed", snapshot)
        finally:
            if not terminal:
                with anyio.CancelScope(shield=True):
                    try:
                        _fail_research_group(activity_id, generation_id, current, db, "GENERATION_INTERRUPTED", payload.model,
                                             failed_scope=current_scope, result=result,
                                             duration_ms=max(0, round((time.perf_counter() - started) * 1000)) if started else None)
                    except StepDomainError as exc:
                        if exc.code != "GENERATION_STALE":
                            raise
                        logger.warning("research_generation_cleanup_stale")

    def cleanup_unstarted_response():
        # Also cover a disconnect before the async generator is first entered.
        db.rollback()
        run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id))
        if run is not None and run.status == "running":
            _fail_research_group(activity_id, generation_id, current, db, "GENERATION_INTERRUPTED", payload.model)
        else:
            db.rollback()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(cleanup_unstarted_response))


def _persist_generation_failure(
    *,
    db: Session,
    activity_id: UUID,
    step_no: int,
    current: AuthenticatedUser,
    generation_id: UUID,
    error_code: str,
    model: str | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    usage: dict[str, int] | None = None,
) -> None:
    db.rollback()
    activity, step = _locked_step(activity_id, step_no, current, db)
    try:
        fail_generation(
            activity=activity,
            step=step,
            generation_id=generation_id,
            actor=str(current.user_id),
            error_code=error_code,
            model=model,
            request_id=request_id,
            duration_ms=duration_ms,
            usage=usage,
            session=db,
        )
    except StepDomainError:
        db.rollback()
        raise
    db.commit()


# Import after the shared activity dependencies are declared; tests and runtime
# assembly receive the same streaming routes through the canonical router.
from backend.planning_api import router as planning_router

router.include_router(planning_router)
