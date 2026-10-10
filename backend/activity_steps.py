from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from backend.activities import validate_activity_brief_input
from backend.activity_prompt import build_activity_system_prompt
from backend.app.research.selection import RESEARCH_SCOPES, RawPublicEvidence, load_public_evidence, select_public_evidence
from backend.models import (
    Activity,
    ActivityStep,
    ActivityStepConfirmation,
    ActivityStepVersion,
    ExecutionTask,
    ModelRun,
    SourceReference,
)


STEP_STATUSES = frozenset(
    {"locked", "draft", "generating", "review", "confirmed", "needs_review", "failed"}
)
WRITABLE_ACTIVITY_STATUSES = frozenset({"draft", "running", "failed", "completed"})
GENERATABLE_STEP_STATUSES = frozenset({"draft", "review", "needs_review", "failed"})
CONFIRMABLE_STEP_STATUSES = frozenset({"review", "needs_review"})


class StepDomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict):
            null_fields = [key for key, field_value in value.items() if field_value is None]
            if null_fields:
                raise ValueError(f"explicit null is not allowed for: {', '.join(sorted(null_fields))}")
        return value


class StandardizedBrief(_OutputModel):
    objective: str = Field(min_length=1, max_length=3000)
    planning_mode: Literal["single", "annual"] | None = Field(default=None, alias="planningMode")
    location: str | None = Field(default=None, max_length=500)
    planned_start_at: str | None = Field(default=None, alias="plannedStartAt", max_length=80)
    planned_end_at: str | None = Field(default=None, alias="plannedEndAt", max_length=80)
    target: str | None = Field(default=None, max_length=1000)
    budget_min: float | None = Field(default=None, ge=0, alias="budgetMin")
    budget_max: float | None = Field(default=None, ge=0, alias="budgetMax")
    target_audience: str | None = Field(default=None, alias="targetAudience", max_length=2000)
    known_constraints: str | None = Field(default=None, alias="knownConstraints", max_length=5000)
    annual_period: str | None = Field(default=None, min_length=1, max_length=200, alias="annualPeriod")
    annual_goals: str | None = Field(default=None, min_length=1, max_length=5000, alias="annualGoals")
    planned_event_count: int | None = Field(default=None, ge=2, le=12, strict=True, alias="plannedEventCount")

    @model_validator(mode="after")
    def validate_budget_range(self) -> StandardizedBrief:
        for value in (self.budget_min, self.budget_max):
            if value is not None and not math.isfinite(value):
                raise ValueError("budget values must be finite")
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budgetMin cannot exceed budgetMax")
        annual_fields = (self.annual_period, self.annual_goals, self.planned_event_count)
        if self.planning_mode == "annual" and any(value is None for value in annual_fields):
            raise ValueError("annual planning requires annualPeriod, annualGoals, and plannedEventCount")
        if self.planning_mode in {None, "single"} and any(value is not None for value in annual_fields):
            raise ValueError("annual planning fields require planningMode annual")
        return self


class BriefGenerationOutput(_OutputModel):
    standardized_brief: StandardizedBrief = Field(alias="standardizedBrief")
    missing_fields: list[str] = Field(alias="missingFields", max_length=50)


class ResearchSource(_OutputModel):
    source_type: Literal["actual", "public", "calculated", "missing"] = Field(alias="sourceType")
    label: str = Field(min_length=1, max_length=300)
    url: HttpUrl | None = None
    captured_at: datetime | None = Field(default=None, alias="capturedAt")
    published_at: str | None = Field(default=None, alias="publishedAt", min_length=1, max_length=100)
    site_name: str | None = Field(default=None, alias="siteName", min_length=1, max_length=300)
    authority_level: Literal["very_high", "high", "normal"] | None = Field(
        default=None, alias="authorityLevel"
    )
    rank: int | None = Field(default=None, ge=0, strict=True)
    provider_request_id: str | None = Field(
        default=None, alias="providerRequestId", min_length=1, max_length=300
    )
    scope: Literal["weather", "holiday", "similar_events", "public_trend"] | None = None
    excerpt: str | None = Field(default=None, max_length=3000)
    reasoning: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_source_evidence(self) -> ResearchSource:
        if self.captured_at is not None and self.captured_at.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone")
        if self.source_type == "public":
            if self.url is None or self.captured_at is None or not self.excerpt:
                raise ValueError("public sources require url, capturedAt, and excerpt")
        if self.source_type == "calculated" and not self.reasoning:
            raise ValueError("calculated sources require reasoning")
        return self


class ResearchGenerationOutput(_OutputModel):
    summary: str = Field(min_length=1, max_length=5000)
    findings: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=100)
    sources: list[ResearchSource] = Field(min_length=1, max_length=100)
    risks: list[str] = Field(max_length=100)


class ThemeCandidate(_OutputModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    storyline: str = Field(min_length=1, max_length=3000)
    visual_direction: str = Field(alias="visualDirection", min_length=1, max_length=2000)
    highlights: list[str] = Field(min_length=1, max_length=20)


class ThemeGenerationOutput(_OutputModel):
    candidates: list[ThemeCandidate] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique_theme_ids(self) -> ThemeGenerationOutput:
        ids = [theme.id for theme in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("theme ids must be unique")
        return self


class AnnualEventBrief(_OutputModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    time_window: str = Field(alias="timeWindow", min_length=1, max_length=200)
    target_audience: str = Field(alias="targetAudience", min_length=1, max_length=1000)
    positioning: str = Field(min_length=1, max_length=2000)
    theme_direction: str = Field(alias="themeDirection", min_length=1, max_length=2000)
    scale: str = Field(min_length=1, max_length=200)
    shared_assets: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(alias="sharedAssets", max_length=50)
    highlights: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=20)


class AnnualThemeGenerationOutput(_OutputModel):
    annual_narrative: str = Field(alias="annualNarrative", min_length=1, max_length=5000)
    event_briefs: list[AnnualEventBrief] = Field(alias="eventBriefs", min_length=2, max_length=12)

    @model_validator(mode="after")
    def unique_event_ids(self) -> AnnualThemeGenerationOutput:
        ids = [event.id for event in self.event_briefs]
        if len(ids) != len(set(ids)):
            raise ValueError("event brief ids must be unique")
        if any(event_id in {"annual", "single"} for event_id in ids):
            raise ValueError("event brief IDs cannot use reserved planning unit keys")
        return self


class ScheduleItem(_OutputModel):
    time: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=3000)


class SpaceZone(_OutputModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=1000)
    activities: list[str] = Field(default_factory=list, max_length=50)
    requirements: list[str] = Field(default_factory=list, max_length=50)


class PersonnelRequirement(_OutputModel):
    role: str = Field(min_length=1, max_length=200)
    count: int = Field(ge=1, le=100000)
    responsibilities: list[str] = Field(min_length=1, max_length=30)


class ContentSpaceGenerationOutput(_OutputModel):
    schedule: list[ScheduleItem] = Field(min_length=1, max_length=200)
    zones: list[SpaceZone] = Field(min_length=1, max_length=100)
    personnel: list[PersonnelRequirement] = Field(min_length=1, max_length=100)
    safety_requirements: list[str] = Field(alias="safetyRequirements", min_length=1, max_length=100)


SourceType = Literal["actual", "public", "calculated", "missing"]


def _decimal_as_finite_float(value: Decimal) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("budget arithmetic result must be finite")
    return number


def _calculated_budget_subtotal(quantity: float, unit_price: float) -> float:
    return _decimal_as_finite_float(Decimal(str(quantity)) * Decimal(str(unit_price)))


def _calculated_budget_total(subtotals: list[float]) -> float:
    return _decimal_as_finite_float(
        sum((Decimal(str(subtotal)) for subtotal in subtotals), Decimal("0"))
    )


class BudgetDraftItem(_OutputModel):
    item: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1, max_length=80)
    unit_price: float = Field(alias="unitPrice", ge=0, allow_inf_nan=False, strict=True)
    source_type: SourceType = Field(alias="sourceType")
    basis: str = Field(min_length=1, max_length=2000)


class BudgetItem(_OutputModel):
    item: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1, max_length=80)
    unit_price: float = Field(alias="unitPrice", ge=0, allow_inf_nan=False, strict=True)
    subtotal: float = Field(ge=0, allow_inf_nan=False, strict=True)
    source_type: SourceType = Field(alias="sourceType")
    basis: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_subtotal(self) -> BudgetItem:
        if self.subtotal != _calculated_budget_subtotal(self.quantity, self.unit_price):
            raise ValueError("subtotal must equal quantity multiplied by unitPrice")
        return self


class BudgetSaving(_OutputModel):
    action: str = Field(min_length=1, max_length=1000)
    estimated_saving: float = Field(
        alias="estimatedSaving", ge=0, allow_inf_nan=False, strict=True
    )
    impact: str = Field(min_length=1, max_length=1000)


class BudgetResource(_OutputModel):
    name: str = Field(min_length=1, max_length=300)
    quantity: float = Field(gt=0, allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=1000)


class BudgetGenerationOutput(_OutputModel):
    items: list[BudgetItem] = Field(min_length=1, max_length=300)
    total_amount: float = Field(alias="totalAmount", ge=0, allow_inf_nan=False, strict=True)
    savings: list[BudgetSaving] = Field(default_factory=list, max_length=100)
    resources: list[BudgetResource] = Field(min_length=1, max_length=200)
    budget_note: str = Field(alias="budgetNote", min_length=1, max_length=3000)

    @model_validator(mode="after")
    def validate_total(self) -> BudgetGenerationOutput:
        if self.total_amount != _calculated_budget_total(
            [item.subtotal for item in self.items]
        ):
            raise ValueError("totalAmount must equal the sum of item subtotals")
        return self


class BudgetGenerationDraft(_OutputModel):
    items: list[BudgetDraftItem] = Field(min_length=1, max_length=300)
    savings: list[BudgetSaving] = Field(default_factory=list, max_length=100)
    resources: list[BudgetResource] = Field(min_length=1, max_length=200)
    budget_note: str = Field(alias="budgetNote", min_length=1, max_length=3000)


class PromotionPhase(_OutputModel):
    phase: Literal["warmup", "peak", "followup"]
    objective: str = Field(min_length=1, max_length=1000)
    channels: list[str] = Field(min_length=1, max_length=50)
    content_drafts: list[str] = Field(alias="contentDrafts", min_length=1, max_length=100)
    materials: list[str] = Field(min_length=1, max_length=100)


class PromotionGenerationOutput(_OutputModel):
    strategy: str = Field(min_length=1, max_length=3000)
    phases: list[PromotionPhase] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_phases(self) -> PromotionGenerationOutput:
        phases = [phase.phase for phase in self.phases]
        if set(phases) != {"warmup", "peak", "followup"} or len(phases) != len(set(phases)):
            raise ValueError("phases must contain warmup, peak, and followup exactly once")
        return self


class WbsTask(_OutputModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=5000)
    owner: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = Field(default=None, alias="dueAt")
    dependencies: list[str] = Field(default_factory=list, max_length=100)
    approval_draft: str = Field(alias="approvalDraft", min_length=1, max_length=5000)
    supplier_inquiry_draft: str = Field(
        alias="supplierInquiryDraft", min_length=1, max_length=5000
    )

    @model_validator(mode="after")
    def validate_due_at(self) -> WbsTask:
        if self.due_at is not None and self.due_at.utcoffset() is None:
            raise ValueError("dueAt must include a timezone")
        return self


class ExecutionPlanGenerationOutput(_OutputModel):
    tasks: list[WbsTask] = Field(min_length=1, max_length=300)
    approval_summary: str = Field(alias="approvalSummary", min_length=1, max_length=5000)
    external_actions_draft_only: Literal[True] = Field(alias="externalActionsDraftOnly")


class ChannelAction(_OutputModel):
    channel: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=1000)
    actions: list[str] = Field(min_length=1, max_length=100)
    revenue_model: str = Field(alias="revenueModel", min_length=1, max_length=2000)
    draft_terms: str = Field(alias="draftTerms", min_length=1, max_length=5000)


class SponsorshipPackage(_OutputModel):
    name: str = Field(min_length=1, max_length=300)
    target_partner: str = Field(alias="targetPartner", min_length=1, max_length=500)
    benefits: list[str] = Field(min_length=1, max_length=100)
    reference_price: float = Field(
        alias="referencePrice", ge=0, allow_inf_nan=False, strict=True
    )
    source_type: Literal["calculated", "missing"] = Field(alias="sourceType")
    basis: str = Field(min_length=1, max_length=2000)


class ChannelBusinessGenerationOutput(_OutputModel):
    channel_actions: list[ChannelAction] = Field(alias="channelActions", min_length=1, max_length=100)
    sponsorship_packages: list[SponsorshipPackage] = Field(
        alias="sponsorshipPackages", min_length=1, max_length=100
    )
    ticketing_plan: str = Field(alias="ticketingPlan", min_length=1, max_length=5000)
    secondary_sales_plan: str = Field(alias="secondarySalesPlan", min_length=1, max_length=5000)
    external_actions_draft_only: Literal[True] = Field(alias="externalActionsDraftOnly")


class ReviewMetric(_OutputModel):
    metric: str = Field(min_length=1, max_length=300)
    value: float = Field(allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1, max_length=80)
    source_type: Literal["actual", "calculated"] = Field(alias="sourceType")
    basis: str = Field(min_length=1, max_length=2000)


class ReviewGenerationOutput(_OutputModel):
    forecast_metrics: list[ReviewMetric] = Field(alias="forecastMetrics", min_length=1, max_length=100)
    actual_metrics: list[ReviewMetric] = Field(alias="actualMetrics", default_factory=list, max_length=100)
    missing_actual_metrics: list[str] = Field(
        alias="missingActualMetrics", default_factory=list, max_length=100
    )
    conclusions: list[str] = Field(min_length=1, max_length=100)
    improvements: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_actual_evidence(self) -> ReviewGenerationOutput:
        if any(metric.source_type != "actual" for metric in self.actual_metrics):
            raise ValueError("actualMetrics entries must use sourceType actual")
        if any(metric.source_type != "calculated" for metric in self.forecast_metrics):
            raise ValueError("forecastMetrics entries must use sourceType calculated")
        if not self.actual_metrics and not self.missing_actual_metrics:
            raise ValueError("missingActualMetrics is required when actualMetrics is empty")
        return self


class ReviewAnalysisGenerationOutput(_OutputModel):
    conclusions: list[str] = Field(min_length=1, max_length=100)
    improvements: list[str] = Field(min_length=1, max_length=100)


OUTPUT_SCHEMAS: dict[int, type[_OutputModel]] = {
    1: BriefGenerationOutput,
    2: ResearchGenerationOutput,
    3: ThemeGenerationOutput,
    4: ContentSpaceGenerationOutput,
    5: BudgetGenerationOutput,
    6: PromotionGenerationOutput,
    7: ExecutionPlanGenerationOutput,
    8: ChannelBusinessGenerationOutput,
    9: ReviewGenerationOutput,
}

_PlanOutput = TypeVar("_PlanOutput", bound=_OutputModel)


class AnnualEventPlan(_OutputModel, Generic[_PlanOutput]):
    event_id: str = Field(alias="eventId", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    output: _PlanOutput


class AnnualPlanningOutput(_OutputModel, Generic[_PlanOutput]):
    annual_plan: _PlanOutput = Field(alias="annualPlan")
    event_plans: list[AnnualEventPlan[_PlanOutput]] = Field(alias="eventPlans", min_length=2, max_length=12)

    @model_validator(mode="after")
    def unique_event_ids(self):
        ids = [item.event_id for item in self.event_plans]
        if len(ids) != len(set(ids)):
            raise ValueError("event plan ids must be unique")
        return self


class AnnualBudgetOutput(AnnualPlanningOutput[BudgetGenerationOutput]):
    annual_total_amount: float = Field(alias="annualTotalAmount", ge=0, allow_inf_nan=False, strict=True)

    @model_validator(mode="after")
    def check_annual_total(self):
        expected = _calculated_budget_total([self.annual_plan.total_amount, *[item.output.total_amount for item in self.event_plans]])
        if self.annual_total_amount != expected:
            raise ValueError("annualTotalAmount must equal shared budget plus all event budgets")
        return self


ANNUAL_OUTPUT_SCHEMAS = {step_no: AnnualPlanningOutput[schema] for step_no, schema in OUTPUT_SCHEMAS.items() if step_no >= 4}
ANNUAL_OUTPUT_SCHEMAS[5] = AnnualBudgetOutput


def annual_plan_event_ids(activity: Activity) -> list[str]:
    if activity.input.get("planningMode", "single") != "annual":
        return []
    theme_step = find_step(activity=activity, step_no=3)
    if not theme_step.output_json:
        return []
    parsed = validate_step_output(3, dict(theme_step.output_json), search_enabled=activity.search_enabled,
                                 planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")
    return [item["id"] for item in parsed["eventBriefs"]]


def _output_schema(step_no: int, planning_mode: str = "single") -> type[_OutputModel] | None:
    if planning_mode not in {"single", "annual"}:
        raise _domain_error("INVALID_PLANNING_MODE", "Planning mode must be single or annual")
    if step_no == 3 and planning_mode == "annual":
        return AnnualThemeGenerationOutput
    if step_no >= 4 and planning_mode == "annual":
        return ANNUAL_OUTPUT_SCHEMAS.get(step_no)
    return OUTPUT_SCHEMAS.get(step_no)

GENERATION_OUTPUT_SCHEMAS: dict[int, type[_OutputModel]] = {
    **OUTPUT_SCHEMAS,
    5: BudgetGenerationDraft,
}

_INTERNAL_MODEL_IDENTIFIERS = frozenset(
    {
        "activityInput",
        "searchEnabled",
        "confirmedPreviousSteps",
        "stepInput",
        "requiredJsonSchema",
        "planningMode",
        "annualPeriod",
        "annualGoals",
        "plannedEventCount",
        "annualNarrative",
        "eventBriefs",
        "timeWindow",
        "themeDirection",
        "sharedAssets",
        "currentEventBrief",
        "selectedPlanItemId",
        "planningUnit",
        "requiredEventIds",
        "eventSeeds",
        "currentEventSeed",
        "currentAnnualPlan",
        "annualConstraints",
        "annualPlan",
        "eventPlans",
        "eventId",
        "annualTotalAmount",
        "confirmedResearchEvidence",
        "publicSearchEvidence",
        "publicSearchSelection",
        "standardizedBrief",
        "plannedStartAt",
        "plannedEndAt",
        "budgetMin",
        "budgetMax",
        "targetAudience",
        "knownConstraints",
        "missingFields",
        "sourceType",
        "capturedAt",
        "publishedAt",
        "siteName",
        "authorityLevel",
        "providerRequestId",
        "visualDirection",
        "safetyRequirements",
        "unitPrice",
        "totalAmount",
        "estimatedSaving",
        "budgetNote",
        "contentDrafts",
        "dueAt",
        "approvalDraft",
        "supplierInquiryDraft",
        "approvalSummary",
        "externalActionsDraftOnly",
        "channelActions",
        "revenueModel",
        "draftTerms",
        "sponsorshipPackages",
        "targetPartner",
        "referencePrice",
        "ticketingPlan",
        "secondarySalesPlan",
        "forecastMetrics",
        "actualMetrics",
        "missingActualMetrics",
        "actual",
        "public",
        "calculated",
        "missing",
        "weather",
        "holiday",
        "similar_events",
        "public_trend",
        "very_high",
        "high",
        "normal",
        "warmup",
        "peak",
        "followup",
    }
)
_INTERNAL_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    + "|".join(
        re.escape(identifier)
        for identifier in sorted(_INTERNAL_MODEL_IDENTIFIERS, key=len, reverse=True)
    )
    + r")(?![A-Za-z0-9_])"
)
_TECHNICAL_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[a-z]+(?:[A-Z][A-Za-z0-9]*)+)(?![A-Za-z0-9_])"
)
_STRUCTURAL_STRING_VALUE_KEYS = frozenset(
    {
        "id",
        "url",
        "capturedAt",
        "publishedAt",
        "providerRequestId",
        "sourceType",
        "authorityLevel",
        "scope",
        "phase",
        "planningMode",
        "dueAt",
    }
)


def _validate_generated_user_visible_strings(
    value: Any, *, parent_key: str | None = None,
    allow_public_source_excerpts: bool = False, path: tuple[str | int, ...] = (),
) -> None:
    if isinstance(value, str):
        if parent_key in _STRUCTURAL_STRING_VALUE_KEYS:
            return
        if _INTERNAL_IDENTIFIER_PATTERN.search(value) or _TECHNICAL_IDENTIFIER_PATTERN.search(value):
            error = _domain_error(
                "INVALID_MODEL_RESPONSE",
                "Model response contained an internal technical identifier in user-visible text",
            )
            error.diagnostic_path = path
            raise error
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_generated_user_visible_strings(
                child, parent_key=parent_key,
                allow_public_source_excerpts=allow_public_source_excerpts, path=(*path, index),
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                allow_public_source_excerpts and len(path) == 2 and path[0] == "sources"
                and isinstance(path[1], int) and value.get("sourceType") == "public" and key == "excerpt"
            ):
                # External verbatim text is checked against the stored source under the generation lock.
                continue
            _validate_generated_user_visible_strings(
                child, parent_key=key,
                allow_public_source_excerpts=allow_public_source_excerpts, path=(*path, key),
            )


def _domain_error(code: str, message: str) -> StepDomainError:
    return StepDomainError(code, message)


def generation_failure_diagnostic(
    error: StepDomainError, *, step_no: int, response_text: str | None,
    planning_mode: str = "single",
    required_json_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return failure shape only; never include model text, field values, or exception reprs."""
    known_fields: set[str] = set()

    def collect_schema_fields(value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                known_fields.update(properties)
            for child in value.values():
                collect_schema_fields(child)
        elif isinstance(value, list):
            for child in value:
                collect_schema_fields(child)

    schema = (
        _output_schema(step_no, planning_mode)
        if step_no == 3
        else GENERATION_OUTPUT_SCHEMAS.get(step_no)
    )
    if required_json_schema is not None:
        collect_schema_fields(required_json_schema)
    elif schema is not None:
        collect_schema_fields(schema.model_json_schema(by_alias=True))

    def safe_path(path) -> list[str | int]:
        return [part if isinstance(part, int) or part in known_fields else "unknown" for part in path]

    detail: dict[str, Any] = {"stepNo": step_no, "code": error.code, "stage": "domain_validation"}
    cause = error.__cause__
    if error.message == "Model response contained an internal technical identifier in user-visible text":
        detail.update(stage="user_visible_identifier", path=safe_path(getattr(error, "diagnostic_path", ())))
    elif isinstance(cause, ValidationError):
        detail.update(stage="schema_validation", errors=[
            {"path": safe_path(item["loc"]), "type": item["type"]}
            for item in cause.errors(include_input=False, include_context=False, include_url=False)
        ])
    elif error.message == "Model response was not valid JSON":
        detail.update(stage="json_parse", kind="markdown_fence" if response_text and response_text.lstrip().startswith("```") else "invalid_json")
        if isinstance(cause, json.JSONDecodeError):
            detail.update(line=cause.lineno, column=cause.colno, position=cause.pos)
    elif error.message == "Model response must be a JSON object":
        detail["stage"] = "json_object"
    return detail


def _owned_activity_statement(activity_id: UUID, owner_id: str, *, lock: bool = False):
    statement = (
        select(Activity)
        .where(Activity.id == activity_id, Activity.created_by == owner_id)
        .options(selectinload(Activity.steps))
    )
    return statement.with_for_update().execution_options(populate_existing=True) if lock else statement


def get_owned_activity(
    *, activity_id: UUID, owner_id: str, session: Session, lock: bool = False
) -> Activity | None:
    return session.scalar(_owned_activity_statement(activity_id, owner_id, lock=lock))


def list_steps(*, activity: Activity) -> list[ActivityStep]:
    return sorted(activity.steps, key=lambda step: step.step_no)


def find_step(*, activity: Activity, step_no: int) -> ActivityStep:
    if step_no < 1 or step_no > 9:
        raise _domain_error("STEP_NOT_FOUND", "Activity step not found")
    for step in activity.steps:
        if step.step_no == step_no:
            return step
    raise _domain_error("STEP_NOT_FOUND", "Activity step not found")


def _check_version(step: ActivityStep, expected_version: int) -> None:
    if step.version != expected_version:
        raise _domain_error(
            "VERSION_CONFLICT",
            f"Step version is {step.version}; refresh before saving changes",
        )


def _assert_activity_writable(activity: Activity) -> None:
    if activity.status not in WRITABLE_ACTIVITY_STATUSES:
        raise _domain_error(
            "ACTIVITY_NOT_WRITABLE",
            f"Steps cannot be changed while activity status is {activity.status}",
        )


def _assert_research_generation_completed(
    activity: Activity, step: ActivityStep, session: Session
) -> None:
    versions = session.scalars(
        select(ActivityStepVersion)
        .where(
            ActivityStepVersion.activity_id == activity.id,
            ActivityStepVersion.step_no == 2,
            ActivityStepVersion.version <= step.version,
        )
        .order_by(ActivityStepVersion.version.desc())
    ).all()
    for version in versions:
        # Clearing the research output starts a new evidence/summary cycle.
        # Saved edits and failed attempts cannot substitute for model completion.
        if not version.output_json:
            break
        if version.change_type == "generated":
            if set(version.input_json) != {"useWebSearch"} or not isinstance(
                version.input_json["useWebSearch"], bool
            ):
                raise _domain_error("PERSISTED_STEP_OUTPUT_INVALID", "Research generation input is invalid")
            validate_step_output(
                2,
                dict(version.output_json),
                search_enabled=version.input_json["useWebSearch"],
                error_code="PERSISTED_STEP_OUTPUT_INVALID",
            )
            return
    raise _domain_error(
        "RESEARCH_GENERATION_REQUIRED",
        "第 2 步模型归纳尚未完成，请返回第 2 步完成归纳后再确认或继续。",
    )


def _assert_prerequisites(activity: Activity, step: ActivityStep, session: Session) -> None:
    unconfirmed = [
        previous.step_no
        for previous in activity.steps
        if previous.step_no < step.step_no and previous.status != "confirmed"
    ]
    if unconfirmed:
        raise _domain_error(
            "PREVIOUS_STEP_NOT_CONFIRMED",
            f"Confirm step {min(unconfirmed)} before changing step {step.step_no}",
        )
    if step.step_no >= 3:
        _assert_research_generation_completed(activity, find_step(activity=activity, step_no=2), session)


def _assert_step_writable(activity: Activity, step: ActivityStep, session: Session) -> None:
    _assert_activity_writable(activity)
    if step.status == "locked":
        raise _domain_error("STEP_LOCKED", "The previous step must be confirmed first")
    if step.status == "generating":
        raise _domain_error("STEP_GENERATING", "The step is already being generated")
    if step.status == "confirmed":
        raise _domain_error("STEP_REOPEN_REQUIRED", "Reopen the confirmed step before changing it")
    _assert_prerequisites(activity, step, session)


def _assert_step_implemented(step: ActivityStep) -> None:
    if step.step_no not in OUTPUT_SCHEMAS:
        raise _domain_error("STEP_NOT_IMPLEMENTED", "This workflow step is not implemented on this branch")


def _normalize_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    normalized = comment.strip()
    if not normalized:
        raise _domain_error("INVALID_COMMENT", "Comment must be omitted or contain non-whitespace text")
    return normalized


def _append_version(
    step: ActivityStep,
    actor: str,
    session: Session,
    *,
    change_type: str,
    change_reason: str | None = None,
) -> None:
    session.add(
        ActivityStepVersion(
            activity_id=step.activity_id,
            step_no=step.step_no,
            version=step.version,
            input_json=dict(step.input_json),
            output_json=dict(step.output_json),
            status=step.status,
            changed_by=actor,
            change_type=change_type,
            change_reason=change_reason,
        )
    )


def _new_version(
    step: ActivityStep,
    actor: str,
    session: Session,
    *,
    change_type: str,
    change_reason: str | None = None,
) -> None:
    step.version += 1
    _append_version(
        step,
        actor,
        session,
        change_type=change_type,
        change_reason=change_reason,
    )


def _mark_downstream_needs_review(
    activity: Activity, changed_step_no: int, actor: str, session: Session
) -> None:
    for downstream in list_steps(activity=activity):
        if downstream.step_no <= changed_step_no or downstream.status in {"locked", "needs_review"}:
            continue
        active_runs = session.scalars(
            select(ModelRun)
            .where(
                ModelRun.activity_id == activity.id,
                ModelRun.step_no == downstream.step_no,
                ModelRun.status == "running",
            )
            .with_for_update()
        ).all()
        for run in active_runs:
            if run.planning_progress is not None:
                from backend.planning_generation import PlanningProgress, aggregate_planning_audit
                progress = PlanningProgress.model_validate(run.planning_progress).model_dump(exclude_none=True)
                for item in progress["units"]:
                    if item["status"] == "running":
                        item.update(status="failed", errorCode="GENERATION_SUPERSEDED")
                    elif item["status"] == "waiting":
                        item.update(status="cancelled", errorCode="GENERATION_SUPERSEDED")
                run.planning_progress = PlanningProgress.model_validate(progress).model_dump(exclude_none=True)
                audit = aggregate_planning_audit(run.planning_progress)
                run.duration_ms = audit["duration_ms"]
                run.prompt_tokens = audit["usage"]["prompt_tokens"]
                run.completion_tokens = audit["usage"]["completion_tokens"]
                run.total_tokens = audit["usage"]["total_tokens"]
            if run.scope_progress is not None:
                from backend.research_generation import ScopeProgress
                progress = ScopeProgress.model_validate(run.scope_progress).model_dump(exclude_none=True)
                for item in progress["scopes"]:
                    if item["status"] == "running":
                        item.update(status="failed", errorCode="GENERATION_SUPERSEDED")
                    elif item["status"] == "waiting":
                        item.update(status="cancelled", errorCode="GENERATION_SUPERSEDED")
                run.scope_progress = ScopeProgress.model_validate(progress).model_dump(exclude_none=True)
                from backend.research_generation import aggregate_scope_audit
                audit = aggregate_scope_audit(run.scope_progress)
                run.duration_ms = audit["duration_ms"]
                run.prompt_tokens = audit["usage"]["prompt_tokens"]
                run.completion_tokens = audit["usage"]["completion_tokens"]
                run.total_tokens = audit["usage"]["total_tokens"]
            run.status = "failed"
            run.error_code = "GENERATION_SUPERSEDED"
            run.finished_at = datetime.now(timezone.utc)
        downstream.status = "needs_review"
        downstream.confirmed_by = None
        downstream.confirmed_at = None
        _new_version(downstream, actor, session, change_type="upstream_invalidated")
    _touch_activity(activity)


def _sync_execution_tasks(
    *, activity: Activity, step: ActivityStep, output_json: dict[str, Any], session: Session
) -> None:
    if activity.input.get("planningMode", "single") == "annual":
        canonical = validate_step_output(7, output_json, search_enabled=activity.search_enabled, planning_mode="annual",
                                         event_ids=annual_plan_event_ids(activity), error_code="PERSISTED_STEP_OUTPUT_INVALID")
        plans = [canonical["annualPlan"], *[item["output"] for item in canonical["eventPlans"]]]
        tasks = [task for plan in plans for task in ExecutionPlanGenerationOutput.model_validate(plan).tasks]
    else:
        tasks = ExecutionPlanGenerationOutput.model_validate(output_json).tasks
    existing = session.scalars(
        select(ExecutionTask).where(
            ExecutionTask.activity_id == activity.id,
            ExecutionTask.source_step_version == step.version,
        )
    ).all()
    if existing:
        expected_indexes = set(range(len(tasks)))
        existing_indexes = {task.source_task_index for task in existing}
        if existing_indexes != expected_indexes:
            raise _domain_error(
                "EXECUTION_TASK_SYNC_CONFLICT",
                "Generated execution tasks do not match the confirmed step version",
            )
        return

    session.add_all(
        ExecutionTask(
            activity_id=activity.id,
            step_no=7,
            title=task.title,
            description=task.description,
            owner=task.owner,
            due_at=task.due_at,
            status="pending_confirmation",
            attachment_file_ids=[],
            source_step_version=step.version,
            source_task_index=index,
        )
        for index, task in enumerate(tasks)
    )


def _touch_activity(activity: Activity) -> None:
    activity.updated_at = datetime.now(timezone.utc)


def _recompute_activity(activity: Activity) -> None:
    steps = list_steps(activity=activity)
    first_unconfirmed = next((step for step in steps if step.status != "confirmed"), None)
    if first_unconfirmed is None:
        activity.current_step = 9
        activity.status = "completed"
        return
    activity.current_step = first_unconfirmed.step_no
    if activity.status in {"completed", "failed"}:
        activity.status = "running"


def patch_step(
    *,
    activity: Activity,
    step: ActivityStep,
    expected_version: int,
    actor: str,
    session: Session,
    input_json: dict[str, Any] | None = None,
    output_json: dict[str, Any] | None = None,
    input_supplied: bool = False,
    output_supplied: bool = False,
) -> ActivityStep:
    _assert_step_implemented(step)
    _check_version(step, expected_version)
    _assert_step_writable(activity, step, session)
    if input_supplied:
        if input_json is None:
            raise _domain_error("INVALID_STEP_INPUT", "inputJson cannot be null")
        supplied_input = dict(input_json)
        if step.step_no == 1:
            try:
                supplied_input = validate_activity_brief_input(supplied_input)
            except ValueError as exc:
                raise _domain_error(
                    "INVALID_STEP_INPUT",
                    "Step 1 input must be a complete valid activity brief",
                ) from exc
            if supplied_input.get("planningMode", "single") != activity.input.get("planningMode", "single") and any(item.output_json for item in activity.steps):
                raise _domain_error("PLANNING_MODE_LOCKED", "已有策划结果后不能切换规划模式，请新建对应模式的策划。")
            activity.input = dict(supplied_input)
        elif step.step_no == 2:
            if set(supplied_input) != {"useWebSearch"} or not isinstance(
                supplied_input["useWebSearch"], bool
            ):
                raise _domain_error("INVALID_STEP_INPUT", "useWebSearch must be a boolean")
            activity.search_enabled = supplied_input["useWebSearch"]
        elif step.step_no == 3:
            planning_mode = activity.input.get("planningMode", "single")
            allowed_input = {"selectedThemeId"} if planning_mode == "single" else {"selectedPlanItemId"}
            if set(supplied_input) - allowed_input:
                field_name = "selectedThemeId" if planning_mode == "single" else "selectedPlanItemId"
                raise _domain_error("INVALID_STEP_INPUT", f"Step 3 input only accepts {field_name}")
            for field_name in allowed_input:
                if field_name in supplied_input and (
                    not isinstance(supplied_input[field_name], str)
                    or not supplied_input[field_name].strip()
                ):
                    raise _domain_error("INVALID_STEP_INPUT", f"{field_name} must be a non-empty string")
        else:
            raise _domain_error("INVALID_STEP_INPUT", f"Step {step.step_no} does not accept inputJson")
        step.input_json = supplied_input
    if output_supplied:
        if output_json is None:
            raise _domain_error("INVALID_STEP_OUTPUT", "outputJson cannot be null")
        supplied_output = dict(output_json)
        if supplied_output:
            supplied_output = validate_step_output(
                step.step_no,
                supplied_output,
                search_enabled=activity.search_enabled,
                planning_mode=activity.input.get("planningMode", "single"),
                event_ids=annual_plan_event_ids(activity) if step.step_no >= 4 else None,
                error_code="INVALID_STEP_OUTPUT",
            )
            if step.step_no == 2:
                _assert_research_generation_completed(activity, step, session)
        step.output_json = supplied_output
        if step.step_no == 2:
            _replace_research_sources(
                activity=activity,
                output_json=supplied_output,
                session=session,
                preserve_public_evidence=True,
            )

    if output_supplied:
        step.status = "review" if step.output_json else "draft"
    elif step.output_json:
        step.status = "needs_review"
    else:
        step.status = "draft"
    step.confirmed_by = None
    step.confirmed_at = None
    _new_version(step, actor, session, change_type="saved")
    activity.status = "running"
    _recompute_activity(activity)
    _touch_activity(activity)
    session.flush()
    return step


def confirm_step(
    *,
    activity: Activity,
    step: ActivityStep,
    expected_version: int,
    actor: str,
    comment: str | None,
    session: Session,
) -> ActivityStep:
    _assert_step_implemented(step)
    _check_version(step, expected_version)
    _assert_step_writable(activity, step, session)
    normalized_comment = _normalize_comment(comment)
    if step.status not in CONFIRMABLE_STEP_STATUSES:
        raise _domain_error("STEP_NOT_CONFIRMABLE", "Generate or save a result before confirming this step")
    if not step.output_json:
        raise _domain_error("STEP_OUTPUT_REQUIRED", "Step output is required before confirmation")
    # Confirmation must never make malformed persisted output authoritative. The
    # write paths validate output already, but this also protects against legacy
    # rows or direct database edits before the confirmation record is inserted.
    planning_mode = activity.input.get("planningMode", "single")
    validated_output = validate_step_output(
        step.step_no,
        dict(step.output_json),
        search_enabled=activity.search_enabled,
        planning_mode=planning_mode,
        event_ids=annual_plan_event_ids(activity) if step.step_no >= 4 else None,
        error_code="PERSISTED_STEP_OUTPUT_INVALID",
    )
    if step.step_no == 2:
        _assert_research_generation_completed(activity, step, session)
    if step.step_no == 3:
        if planning_mode == "annual":
            if set(step.input_json) - {"selectedPlanItemId"}:
                raise _domain_error("PERSISTED_STEP_OUTPUT_INVALID", "Annual step 3 input contains unsupported fields")
            selected_plan_item_id = step.input_json.get("selectedPlanItemId")
            if "selectedPlanItemId" in step.input_json:
                if not isinstance(selected_plan_item_id, str) or not selected_plan_item_id.strip():
                    raise _domain_error("PERSISTED_STEP_OUTPUT_INVALID", "Selected annual event brief must be a non-empty string")
                event_ids = {event["id"] for event in validated_output["eventBriefs"]}
                if selected_plan_item_id not in event_ids:
                    raise _domain_error(
                        "INVALID_PLAN_ITEM_SELECTION",
                        "The selected plan item does not match a current annual event brief",
                    )
        else:
            selected_theme_id = step.input_json.get("selectedThemeId")
            if not isinstance(selected_theme_id, str) or not selected_theme_id.strip():
                raise _domain_error(
                    "THEME_SELECTION_REQUIRED",
                    "Select one generated theme before confirming step 3",
                )
            candidates = validated_output["candidates"]
            candidate_ids = {candidate["id"] for candidate in candidates}
            if selected_theme_id not in candidate_ids:
                raise _domain_error(
                    "INVALID_THEME_SELECTION",
                    "The selected theme does not match a current candidate",
                )
    if step.step_no == 7:
        _sync_execution_tasks(
            activity=activity,
            step=step,
            output_json=validated_output,
            session=session,
        )

    confirmed_at = datetime.now(timezone.utc)
    session.add(
        ActivityStepConfirmation(
            activity_id=activity.id,
            step_no=step.step_no,
            version=step.version,
            confirmed_by=actor,
            comment=normalized_comment,
            confirmed_at=confirmed_at,
        )
    )
    step.status = "confirmed"
    step.confirmed_by = actor
    step.confirmed_at = confirmed_at

    next_step = next(
        (candidate for candidate in activity.steps if candidate.step_no == step.step_no + 1),
        None,
    )
    if next_step is not None and next_step.status == "locked":
        next_step.status = "draft"
        _new_version(next_step, actor, session, change_type="unlocked")
    activity.status = "running"
    _recompute_activity(activity)
    _touch_activity(activity)
    session.flush()
    return step


def reopen_step(
    *,
    activity: Activity,
    step: ActivityStep,
    expected_version: int,
    actor: str,
    comment: str | None,
    session: Session,
) -> ActivityStep:
    _assert_step_implemented(step)
    _check_version(step, expected_version)
    _assert_activity_writable(activity)
    if step.status != "confirmed":
        raise _domain_error("STEP_NOT_CONFIRMED", "Only a confirmed step can be reopened")
    _assert_prerequisites(activity, step, session)
    reason = _normalize_comment(comment)
    step.status = "draft"
    step.confirmed_by = None
    step.confirmed_at = None
    _new_version(step, actor, session, change_type="reopened", change_reason=reason)
    _mark_downstream_needs_review(activity, step.step_no, actor, session)
    activity.status = "running"
    _recompute_activity(activity)
    _touch_activity(activity)
    session.flush()
    return step


def build_generation_messages(
    activity: Activity,
    step: ActivityStep,
    session: Session | None = None,
) -> list[dict[str, str]]:
    if activity.input.get("planningMode", "single") == "annual" and step.step_no >= 3:
        from backend.planning_generation import planning_unit_messages
        return planning_unit_messages(activity, step, "annual")
    if step.step_no not in OUTPUT_SCHEMAS:
        raise _domain_error("STEP_NOT_IMPLEMENTED", "Generation for this step is owned by the later workflow phase")
    preceding_step_numbers = (
        frozenset({4, 5, 6})
        if step.step_no == 7
        else frozenset(range(1, step.step_no))
    )
    preceding = [
        {
            "stepNo": previous.step_no,
            "stepKey": previous.step_key,
            "input": previous.input_json,
            "output": previous.output_json,
        }
        for previous in list_steps(activity=activity)
        if previous.step_no in preceding_step_numbers
        and previous.status == "confirmed"
        and not (step.step_no >= 3 and previous.step_no == 2)
    ]
    planning_mode = activity.input.get("planningMode", "single")
    generation_schema: type[_OutputModel] = GENERATION_OUTPUT_SCHEMAS[step.step_no]
    saved_review_output: dict[str, Any] | None = None
    if step.step_no == 9 and step.output_json:
        canonical_review = validate_step_output(
            9,
            dict(step.output_json),
            search_enabled=activity.search_enabled,
            error_code="PERSISTED_STEP_OUTPUT_INVALID",
        )
        if canonical_review["actualMetrics"]:
            generation_schema = ReviewAnalysisGenerationOutput
            saved_review_output = canonical_review

    context = {
        "activityInput": activity.input,
        "searchEnabled": activity.search_enabled,
        "confirmedPreviousSteps": preceding,
        "stepInput": step.input_json,
        "requiredJsonSchema": generation_schema.model_json_schema(by_alias=True),
    }
    generation_instruction = "请根据以下上下文生成结果。"
    if planning_mode == "annual":
        generation_instruction += "当前为年度活动组合规划，必须保留年度总叙事与各活动单元之间的边界，不得把多场活动压缩成单场活动。"
    if step.step_no == 5:
        generation_instruction += (
            "预算项只输出 requiredJsonSchema 声明的基础字段；禁止输出 subtotal、totalAmount"
            "或其他派生算术字段，服务端会根据 quantity 和 unitPrice 确定性计算。"
        )
    if saved_review_output is not None:
        context.update(
            forecastMetrics=saved_review_output["forecastMetrics"],
            actualMetrics=saved_review_output["actualMetrics"],
            missingActualMetrics=saved_review_output["missingActualMetrics"],
        )
        generation_instruction += (
            "当前已保存实际指标。只能基于上下文中的 forecastMetrics、actualMetrics 和"
            "missingActualMetrics 生成复盘 conclusions 与 improvements；"
            "不得改写、删除、补充或重新判断任何指标、数值、单位、来源类型和依据。"
        )
    if step.step_no >= 3:
        research_step = next(
            (
                previous
                for previous in list_steps(activity=activity)
                if previous.step_no == 2 and previous.status == "confirmed"
            ),
            None,
        )
        if research_step is None:
            raise _domain_error(
                "PREVIOUS_STEP_NOT_CONFIRMED",
                f"Confirm step 2 before generating step {step.step_no}",
            )
        research_evidence = validate_step_output(
            2,
            dict(research_step.output_json),
            search_enabled=activity.search_enabled,
            error_code="PERSISTED_STEP_OUTPUT_INVALID",
        )
        context["confirmedResearchEvidence"] = {
            "summary": research_evidence["summary"],
            "findings": research_evidence["findings"],
            "risks": research_evidence["risks"],
            "sources": research_evidence["sources"],
        }
        generation_instruction += (
            "必须实质参考 confirmedResearchEvidence 中的检索摘要、发现、风险和来源生成结果；"
            "sources 中的 URL、摘要、发布时间、站点、权威等级、排序、供应商请求标识和检索范围"
            "都是已确认的检索证据元数据，不得忽略、改写或伪造。"
        )
    if step.step_no == 2:
        generation_instruction += (
            "第 2 步只在 sources 中列出直接支撑 summary、findings 或 risks 的最少公开来源；"
            "不要逐条回显 publicSearchEvidence，也不要把无关来源复制到输出。"
            "每条公开引用的 excerpt 只摘取对应证据中直接支持结论的必要原文连续片段，"
            "不超过 3000 个字符；不得改写、拼接或捏造摘录。"
            "URL、采集时间及存在的搜索元数据必须从对应证据原样复制；"
            "所有原始来源和完整检索摘要仍保留在系统的检索证据中。"
            "全部有效搜索证据及完整检索摘要均纳入本次模型归纳，不限每个范围的条数。"
            "按照搜索范围、排名和持久化顺序组织证据，不能截断正文或预先筛除来源。"
            "只能依据 publicSearchEvidence 中的证据进行事实研判；"
            "publicSearchSelection 披露全部纳入规则、数量及排名。"
            "在摘要或风险中用自然中文说明资料数量及实际存在的覆盖限制，不能虚构未纳入来源。"
        )
        raw_sources = []
        if activity.search_enabled and session is not None:
            raw_sources = load_public_evidence(session, activity.id)
        try:
            public_sources, selection = select_public_evidence(raw_sources)
        except ValueError as exc:
            raise StepDomainError(
                "PERSISTED_STEP_OUTPUT_INVALID",
                "Persisted public search evidence does not match its contract",
            ) from exc
        context["publicSearchEvidence"] = public_sources
        context["publicSearchSelection"] = {
            "totalCount": selection["totalCount"],
            "selectedCount": selection["selectedCount"],
            "omittedCount": selection["omittedCount"],
            "rule": "全部有效搜索证据纳入，正文不截断；按搜索范围及排名升序排列，排名相同按采集时间及存储顺序排列。",
            "selectedRanksByScope": {
                scope: [source["rank"] for source in public_sources if source["scope"] == scope]
                for scope in RESEARCH_SCOPES
            },
        }
    return [
        {
            "role": "system",
            "content": build_activity_system_prompt(step.step_no, step.step_key),
        },
        {
            "role": "user",
            "content": generation_instruction
            + (
                "响应必须是纯 JSON 对象：首字符必须是 {，末字符必须是 }。"
                "只能输出一个符合 requiredJsonSchema 的 JSON 对象；"
                "禁止 Markdown 代码围栏、解释文字、前后缀、多个 JSON 对象或其他字符。\n"
            )
            + json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def validate_step_output(
    step_no: int,
    raw: dict[str, Any],
    *,
    search_enabled: bool,
    planning_mode: Literal["single", "annual"] = "single",
    event_ids: list[str] | None = None,
    error_code: str,
) -> dict[str, Any]:
    schema = _output_schema(step_no, planning_mode)
    if schema is None:
        raise _domain_error("STEP_NOT_IMPLEMENTED", "Generation for this step is not implemented")
    try:
        parsed = schema.model_validate(raw)
    except ValueError as exc:
        raise _domain_error(error_code, "Step output did not match the required schema") from exc
    if planning_mode == "annual" and step_no >= 4 and event_ids is not None:
        if set(item.event_id for item in parsed.event_plans) != set(event_ids):
            raise _domain_error(error_code, "Annual event plans must match all current architecture events exactly")
        by_id = {item.event_id: item for item in parsed.event_plans}
        parsed.event_plans = [by_id[event_id] for event_id in event_ids]
    if step_no == 1:
        standardized_mode = parsed.standardized_brief.planning_mode
        if planning_mode == "annual" and standardized_mode != "annual":
            raise _domain_error(error_code, "Annual standardized brief must explicitly preserve annual planning fields")
        if planning_mode == "single" and standardized_mode == "annual":
            raise _domain_error(error_code, "Single standardized brief cannot declare annual planning")
    if step_no == 2:
        research = parsed
        has_public = any(source.source_type == "public" for source in research.sources)
        has_missing = any(source.source_type == "missing" for source in research.sources)
        if has_public and not search_enabled:
            raise _domain_error(
                error_code,
                "Public sources are not allowed when web search is disabled",
            )
        if search_enabled and not has_public and not has_missing:
            raise _domain_error(
                error_code,
                "Research without public evidence must state that web-search evidence is missing",
            )
    return parsed.model_dump(by_alias=True, exclude_none=True, mode="json")


def _replace_research_sources(
    *,
    activity: Activity,
    output_json: dict[str, Any],
    session: Session,
    preserve_public_evidence: bool = False,
) -> None:
    research = ResearchGenerationOutput.model_validate(output_json) if output_json else None
    existing_public = []
    if preserve_public_evidence:
        existing_public = session.scalars(
            select(SourceReference).where(
                SourceReference.activity_id == activity.id,
                SourceReference.step_no == 2,
                SourceReference.source_type == "public",
            )
        ).all()
    if existing_public:
        session.execute(
            delete(SourceReference).where(
                SourceReference.activity_id == activity.id,
                SourceReference.step_no == 2,
                SourceReference.source_type != "public",
            )
        )
        if research is not None:
            session.add_all(
                SourceReference(
                    activity_id=activity.id,
                    step_no=2,
                    source_type=source.source_type,
                    label=source.label,
                    url=str(source.url) if source.url is not None else None,
                    captured_at=source.captured_at,
                    excerpt=source.excerpt,
                    reasoning=source.reasoning,
                    published_at=source.published_at,
                    site_name=source.site_name,
                    authority_level=source.authority_level,
                    rank=source.rank,
                    provider_request_id=source.provider_request_id,
                    scope=source.scope,
                )
                for source in research.sources
                if source.source_type != "public"
            )
        return

    session.execute(
        delete(SourceReference).where(
            SourceReference.activity_id == activity.id,
            SourceReference.step_no == 2,
        )
    )
    if research is None:
        return
    session.add_all(
        SourceReference(
            activity_id=activity.id,
            step_no=2,
            source_type=source.source_type,
            label=source.label,
            url=str(source.url) if source.url is not None else None,
            captured_at=source.captured_at,
            excerpt=source.excerpt,
            reasoning=source.reasoning,
            published_at=source.published_at,
            site_name=source.site_name,
            authority_level=source.authority_level,
            rank=source.rank,
            provider_request_id=source.provider_request_id,
            scope=source.scope,
        )
        for source in research.sources
    )


def validate_generated_output(
    step_no: int,
    text: str,
    *,
    search_enabled: bool,
    planning_mode: Literal["single", "annual"] = "single",
    saved_step_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        raw = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise _domain_error("INVALID_MODEL_RESPONSE", "Model response was not valid JSON") from exc
    if not isinstance(raw, dict):
        raise _domain_error("INVALID_MODEL_RESPONSE", "Model response must be a JSON object")
    _validate_generated_user_visible_strings(raw, allow_public_source_excerpts=step_no == 2)
    if step_no == 5:
        try:
            draft = BudgetGenerationDraft.model_validate(raw)
            canonical = draft.model_dump(by_alias=True, exclude_none=True, mode="json")
            subtotals = []
            for item in canonical["items"]:
                subtotal = _calculated_budget_subtotal(item["quantity"], item["unitPrice"])
                item["subtotal"] = subtotal
                subtotals.append(subtotal)
            canonical["totalAmount"] = _calculated_budget_total(subtotals)
        except ValueError as exc:
            raise _domain_error(
                "INVALID_MODEL_RESPONSE",
                "Step output did not match the required schema",
            ) from exc
        return validate_step_output(
            5,
            canonical,
            search_enabled=search_enabled,
            planning_mode=planning_mode,
            error_code="INVALID_MODEL_RESPONSE",
        )
    if step_no == 9 and saved_step_output:
        saved_review = validate_step_output(
            9,
            saved_step_output,
            search_enabled=search_enabled,
            planning_mode=planning_mode,
            error_code="PERSISTED_STEP_OUTPUT_INVALID",
        )
        if saved_review["actualMetrics"]:
            try:
                analysis = ReviewAnalysisGenerationOutput.model_validate(raw)
            except ValueError as exc:
                raise _domain_error(
                    "INVALID_MODEL_RESPONSE",
                    "Step output did not match the required schema",
                ) from exc
            canonical = {
                "forecastMetrics": saved_review["forecastMetrics"],
                "actualMetrics": saved_review["actualMetrics"],
                "missingActualMetrics": saved_review["missingActualMetrics"],
                **analysis.model_dump(by_alias=True, exclude_none=True, mode="json"),
            }
            return validate_step_output(
                9,
                canonical,
                search_enabled=search_enabled,
                planning_mode=planning_mode,
                error_code="INVALID_MODEL_RESPONSE",
            )
    return validate_step_output(
        step_no,
        raw,
        search_enabled=search_enabled,
        planning_mode=planning_mode,
        error_code="INVALID_MODEL_RESPONSE",
    )


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for name, child in pairs:
        if name in value:
            raise ValueError("duplicate JSON object key")
        value[name] = child
    return value


def _reject_json_constant(_: str) -> Any:
    raise ValueError("non-standard JSON numeric constant")


def start_generation(
    *,
    activity: Activity,
    step: ActivityStep,
    expected_version: int,
    model: str,
    actor: str,
    session: Session,
) -> tuple[UUID, list[dict[str, str]]]:
    _assert_step_implemented(step)
    _check_version(step, expected_version)
    _assert_activity_writable(activity)
    _assert_step_writable(activity, step, session)
    if step.status not in GENERATABLE_STEP_STATUSES:
        raise _domain_error("STEP_NOT_GENERATABLE", f"Step cannot be generated from status {step.status}")
    if (
        not isinstance(model, str)
        or not model
        or model != model.strip()
        or len(model) > 200
    ):
        raise _domain_error(
            "INVALID_GENERATION_MODEL",
            "Generation model must be a non-empty string without surrounding whitespace",
        )

    messages = build_generation_messages(activity, step, session)
    step.status = "generating"
    generation_id = uuid4()
    session.add(
        ModelRun(
            activity_id=activity.id,
            step_no=step.step_no,
            generation_id=generation_id,
            provider="ccode",
            model=model,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
    )
    activity.status = "running"
    _recompute_activity(activity)
    _touch_activity(activity)
    session.flush()
    return generation_id, messages


def _active_run(session: Session, generation_id: UUID) -> ModelRun:
    run = session.scalar(
        select(ModelRun).where(ModelRun.generation_id == generation_id).with_for_update().execution_options(populate_existing=True)
    )
    if run is None or run.status != "running":
        raise _domain_error("GENERATION_STALE", "Generation is no longer active")
    return run


def _validate_usage(usage: dict[str, int]) -> None:
    required_usage_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
    if set(usage) != required_usage_keys or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in usage.values()
    ):
        raise _domain_error("INVALID_GENERATION_METADATA", "Generation usage is incomplete or invalid")


def complete_generation(
    *,
    activity: Activity,
    step: ActivityStep,
    generation_id: UUID,
    actor: str,
    output_json: dict[str, Any],
    model: str,
    request_id: str | None,
    duration_ms: int,
    usage: dict[str, int],
    session: Session,
    research_group: bool = False,
    planning_group: bool = False,
) -> ActivityStep:
    run = _active_run(session, generation_id)
    if run.activity_id != activity.id or run.step_no != step.step_no or step.status != "generating":
        raise _domain_error("GENERATION_STALE", "Generation cannot replace the current step state")
    if research_group:
        from backend.research_generation import ScopeProgress
        progress = ScopeProgress.model_validate(run.scope_progress)
        if step.step_no != 2 or request_id is not None or any(item.status != "completed" for item in progress.scopes):
            raise _domain_error("INVALID_GENERATION_METADATA", "Research batch audit must contain all completed scopes and no parent request ID")
    if planning_group:
        from backend.planning_generation import PlanningProgress
        progress = PlanningProgress.model_validate(run.planning_progress)
        if research_group or run.scope_progress is not None or request_id is not None or any(item.status != "completed" for item in progress.units):
            raise _domain_error("INVALID_GENERATION_METADATA", "Planning batch requires all completed unit audits and no parent request ID")
    if not model.strip() or (not research_group and not planning_group and (not isinstance(request_id, str) or not request_id.strip())):
        raise _domain_error("INVALID_GENERATION_METADATA", "Generation model and request ID are required")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms < 0:
        raise _domain_error("INVALID_GENERATION_METADATA", "Generation duration must be a non-negative integer")
    _validate_usage(usage)
    if planning_group:
        output_json = validate_step_output(step.step_no, output_json, search_enabled=activity.search_enabled,
                                           planning_mode=activity.input.get("planningMode", "single"),
                                           event_ids=annual_plan_event_ids(activity) if step.step_no >= 4 else None,
                                           error_code="INVALID_STEP_OUTPUT")
    if step.step_no == 2:
        parsed = ResearchGenerationOutput.model_validate(output_json)
        public_citations = [source for source in parsed.sources if source.source_type == "public"]
        if public_citations:
            try:
                selected, _selection = select_public_evidence(load_public_evidence(session, activity.id))
            except ValueError as exc:
                raise _domain_error(
                    "PERSISTED_STEP_OUTPUT_INVALID", "Persisted public search evidence does not match its contract"
                ) from exc
            selected_evidence = [RawPublicEvidence.model_validate(source) for source in selected]
            for citation in public_citations:
                matching_sources = [source for source in selected_evidence if (
                    citation.label == source.label
                    and citation.url == source.url
                    and citation.captured_at == source.captured_at
                    and citation.rank == source.rank
                    and citation.scope == source.scope
                    and citation.provider_request_id == source.provider_request_id
                    and citation.published_at == source.published_at
                    and citation.site_name == source.site_name
                    and citation.authority_level == source.authority_level
                )]
                if not matching_sources:
                    raise _domain_error(
                        "PUBLIC_CITATION_METADATA_MISMATCH",
                        "公开引用的来源名称、网址、采集时间及全部搜索元数据必须与同一条已纳入来源完全一致。",
                    )
                if not any(citation.excerpt in source.excerpt for source in matching_sources):
                    raise _domain_error(
                        "PUBLIC_CITATION_EXCERPT_MISMATCH",
                        "公开引用摘录必须是所选来源中的一段连续原文，不能拼接、加入省略号或改写标点和空白。",
                    )
    step.output_json = dict(output_json)
    if step.step_no == 2:
        _replace_research_sources(
            activity=activity,
            output_json=step.output_json,
            session=session,
            preserve_public_evidence=True,
        )
    step.status = "review"
    _new_version(step, actor, session, change_type="generated")
    run.status = "completed"
    run.model = model
    run.provider_request_id = request_id
    run.duration_ms = duration_ms
    run.prompt_tokens = usage["prompt_tokens"]
    run.completion_tokens = usage["completion_tokens"]
    run.total_tokens = usage["total_tokens"]
    run.finished_at = datetime.now(timezone.utc)
    activity.status = "running"
    _recompute_activity(activity)
    _touch_activity(activity)
    session.flush()
    return step


def fail_generation(
    *,
    activity: Activity,
    step: ActivityStep,
    generation_id: UUID,
    actor: str,
    error_code: str,
    model: str | None,
    request_id: str | None,
    duration_ms: int | None,
    usage: dict[str, int] | None,
    session: Session,
) -> ActivityStep:
    run = _active_run(session, generation_id)
    if run.activity_id != activity.id or run.step_no != step.step_no or step.status != "generating":
        raise _domain_error("GENERATION_STALE", "Generation cannot replace the current step state")
    if usage is not None:
        _validate_usage(usage)
    step.status = "failed"
    _new_version(step, actor, session, change_type="generation_failed")
    run.status = "failed"
    run.error_code = error_code
    run.model = model
    run.provider_request_id = request_id
    run.duration_ms = duration_ms
    if usage is not None:
        run.prompt_tokens = usage["prompt_tokens"]
        run.completion_tokens = usage["completion_tokens"]
        run.total_tokens = usage["total_tokens"]
    run.finished_at = datetime.now(timezone.utc)
    _recompute_activity(activity)
    activity.status = "failed"
    _touch_activity(activity)
    session.flush()
    return step
