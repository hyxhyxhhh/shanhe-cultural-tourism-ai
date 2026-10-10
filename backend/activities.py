from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import SessionLocal
from backend.models import Activity, ActivityStep, ActivityStepVersion, STEP_KEYS


ACTIVITY_STATUSES = frozenset({"draft", "running", "paused", "completed", "failed", "archived"})
USER_EDITABLE_STATUSES = frozenset({"draft", "running"})
_STATUS_TRANSITIONS = {
    "draft": frozenset({"running", "paused", "archived"}),
    "running": frozenset({"paused", "failed", "completed", "archived"}),
    "paused": frozenset({"running", "archived"}),
    "failed": frozenset({"running", "paused", "archived"}),
    "completed": frozenset({"archived"}),
    "archived": frozenset(),
}


class ActivityBriefInputData(BaseModel):
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
    def validate_ranges(self) -> ActivityBriefInputData:
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


class InvalidActivityTransition(ValueError):
    pass


def _normalized_title(title: str) -> str:
    normalized = title.strip()
    if not normalized or len(normalized) > 200:
        raise ValueError("title must contain 1 to 200 characters")
    return normalized


def _validated_input(input_data: Mapping[str, Any]) -> dict[str, Any]:
    try:
        parsed = ActivityBriefInputData.model_validate(dict(input_data))
    except ValueError as exc:
        raise ValueError("activity input is invalid") from exc
    return parsed.model_dump(by_alias=True, exclude_none=True, mode="json")


def validate_activity_brief_input(input_data: Mapping[str, Any]) -> dict[str, Any]:
    return _validated_input(input_data)


def _transition(activity: Activity, target_status: str) -> None:
    if target_status not in ACTIVITY_STATUSES:
        raise InvalidActivityTransition(f"unknown activity status: {target_status}")
    if target_status == activity.status:
        return
    allowed_targets = _STATUS_TRANSITIONS.get(activity.status)
    if allowed_targets is None:
        raise InvalidActivityTransition(f"activity has unknown current status: {activity.status}")
    if target_status not in allowed_targets:
        raise InvalidActivityTransition(f"cannot transition activity from {activity.status} to {target_status}")
    activity.status = target_status


def create_activity(
    *,
    title: str,
    idea: str,
    created_by: str,
    input_data: dict[str, Any] | None = None,
    session: Session | None = None,
) -> Activity:
    title = _normalized_title(title)
    idea = idea.strip()
    created_by = created_by.strip()
    if not idea:
        raise ValueError("idea is required")
    if not created_by:
        raise ValueError("created_by is required")

    brief = _validated_input({**(input_data or {}), "idea": idea})
    activity = Activity(
        title=title,
        status="draft",
        current_step=1,
        input=brief,
        search_enabled=False,
        created_by=created_by,
    )
    activity.steps = [
        ActivityStep(
            step_no=index,
            step_key=key,
            status="draft" if index == 1 else "locked",
            input_json=(
                dict(brief)
                if index == 1
                else {"useWebSearch": False}
                if index == 2
                else {}
            ),
            output_json={},
            version=1,
        )
        for index, key in enumerate(STEP_KEYS, start=1)
    ]

    if session is not None:
        session.add(activity)
        session.flush()
        session.add_all(
            ActivityStepVersion(
                activity_id=activity.id,
                step_no=step.step_no,
                version=step.version,
                input_json=dict(step.input_json),
                output_json=dict(step.output_json),
                status=step.status,
                changed_by=created_by,
                change_type="initial",
            )
            for step in activity.steps
        )
        session.flush()
        return activity

    with SessionLocal.begin() as owned_session:
        owned_session.add(activity)
        owned_session.flush()
        owned_session.add_all(
            ActivityStepVersion(
                activity_id=activity.id,
                step_no=step.step_no,
                version=step.version,
                input_json=dict(step.input_json),
                output_json=dict(step.output_json),
                status=step.status,
                changed_by=created_by,
                change_type="initial",
            )
            for step in activity.steps
        )
    return activity


def list_activities(
    *, created_by: str, include_archived: bool = False, session: Session | None = None
) -> list[Activity]:
    if not created_by.strip():
        raise ValueError("created_by is required")
    statement = select(Activity).where(Activity.created_by == created_by)
    if not include_archived:
        statement = statement.where(Activity.status != "archived")
    statement = statement.order_by(Activity.updated_at.desc(), Activity.id).options(selectinload(Activity.steps))
    if session is not None:
        return list(session.scalars(statement))
    with SessionLocal() as owned_session:
        return list(owned_session.scalars(statement))


def get_activity(*, activity_id: UUID, created_by: str, session: Session | None = None) -> Activity | None:
    if not created_by.strip():
        raise ValueError("created_by is required")
    statement = (
        select(Activity)
        .where(Activity.id == activity_id, Activity.created_by == created_by)
        .options(selectinload(Activity.steps))
    )
    if session is not None:
        return session.scalar(statement)
    with SessionLocal() as owned_session:
        return owned_session.scalar(statement)


def update_activity(
    *,
    activity: Activity,
    title: str | None = None,
    status: str | None = None,
    session: Session,
) -> Activity:
    if activity.status == "archived":
        raise InvalidActivityTransition("archived activities cannot be edited")
    if title is not None:
        activity.title = _normalized_title(title)
    if status is not None:
        if status not in USER_EDITABLE_STATUSES:
            raise InvalidActivityTransition(f"status cannot be set through activity update: {status}")
        _transition(activity, status)
    session.flush()
    return activity


def pause_activity(*, activity: Activity, session: Session) -> Activity:
    _transition(activity, "paused")
    session.flush()
    return activity


def archive_activity(*, activity: Activity, session: Session) -> Activity:
    _transition(activity, "archived")
    session.flush()
    return activity
