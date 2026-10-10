"""Strict per-unit planning generation, context projection, and durable audit."""

from copy import deepcopy
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.activity_prompt import build_activity_system_prompt
from backend.activity_steps import (
    AnnualEventBrief, AnnualThemeGenerationOutput, GENERATION_OUTPUT_SCHEMAS,
    ReviewAnalysisGenerationOutput, StepDomainError, _OutputModel,
    _calculated_budget_total, _reject_json_constant, _unique_json_object,
    _validate_generated_user_visible_strings, annual_plan_event_ids,
    find_step, list_steps, validate_generated_output, validate_step_output,
)


class PlanningUnitAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    status: Literal["waiting", "running", "completed", "failed", "cancelled"]
    model: str | None = Field(default=None, min_length=1, max_length=200)
    providerRequestId: str | None = Field(default=None, min_length=1, max_length=300)
    durationMs: int | None = Field(default=None, ge=0)
    promptTokens: int | None = Field(default=None, ge=0)
    completionTokens: int | None = Field(default=None, ge=0)
    totalTokens: int | None = Field(default=None, ge=0)
    errorCode: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, value):
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("planning audit optional fields must be omitted instead of null")
        return value

    @model_validator(mode="after")
    def check_status(self):
        metadata = (self.model, self.providerRequestId, self.durationMs, self.promptTokens, self.completionTokens, self.totalTokens)
        for value in (self.key, self.label, self.model, self.providerRequestId, self.errorCode):
            if value is not None and not value.strip():
                raise ValueError("planning audit text must not be blank")
        if any(value is not None for value in (self.promptTokens, self.completionTokens, self.totalTokens)) and any(value is None for value in metadata):
            raise ValueError("provider response metadata must be complete")
        if self.status == "completed" and (any(value is None for value in metadata) or self.errorCode is not None):
            raise ValueError("completed units require complete metadata without error")
        if self.status in {"waiting", "running"} and any(value is not None for value in (*metadata, self.errorCode)):
            raise ValueError("unfinished units cannot have completed provider metadata")
        if self.status in {"failed", "cancelled"} and not self.errorCode:
            raise ValueError("failed or cancelled units require an error code")
        if self.status == "cancelled" and any(value is not None for value in metadata):
            raise ValueError("uncalled cancelled units cannot have provider metadata")
        return self


class PlanningProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    units: list[PlanningUnitAudit] = Field(min_length=1, max_length=13)

    @model_validator(mode="after")
    def check_units(self):
        keys = [unit.key for unit in self.units]
        if len(keys) != len(set(keys)) or keys[0] not in {"single", "annual"} or (keys[0] == "single" and len(keys) != 1):
            raise ValueError("planning unit keys must be unique and have a single or annual first unit")
        if any(key in {"single", "annual"} for key in keys[1:]):
            raise ValueError("reserved planning keys can only be the first unit")
        states = [unit.status for unit in self.units]
        position = 0
        while position < len(states) and states[position] == "completed":
            position += 1
        tail = states[position:]
        if tail:
            expected = {"running": "waiting", "waiting": "waiting", "failed": "cancelled", "cancelled": "cancelled"}[tail[0]]
            if any(state != expected for state in tail[1:]):
                raise ValueError("planning progress requires a completed prefix and a sequential tail")
        return self


class AnnualEventSeed(_OutputModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    time_window: str = Field(alias="timeWindow", min_length=1, max_length=200)
    target_audience: str = Field(alias="targetAudience", min_length=1, max_length=1000)
    positioning: str = Field(min_length=1, max_length=2000)
    theme_direction: str = Field(alias="themeDirection", min_length=1, max_length=2000)
    scale: str = Field(min_length=1, max_length=200)


class AnnualArchitectureDraft(_OutputModel):
    annual_narrative: str = Field(alias="annualNarrative", min_length=1, max_length=5000)
    event_seeds: list[AnnualEventSeed] = Field(alias="eventSeeds", min_length=2, max_length=12)


class AnnualEventDetails(_OutputModel):
    shared_assets: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(alias="sharedAssets", max_length=50)
    highlights: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=20)


def initial_planning_progress(activity, step):
    annual = activity.input.get("planningMode", "single") == "annual"
    if not annual:
        units = [{"key": "single", "label": "活动方案", "status": "waiting"}]
    elif step.step_no == 3:
        units = [{"key": "annual", "label": "年度架构", "status": "waiting"}]
        units += [{"key": f"event-{index}", "label": f"活动简案 {index}", "status": "waiting"} for index in range(1, activity.input["plannedEventCount"] + 1)]
    elif step.step_no >= 4:
        architecture = annual_architecture(activity)
        units = [{"key": "annual", "label": "年度统筹", "status": "waiting"}]
        units += [{"key": item["id"], "label": item["name"], "status": "waiting"} for item in architecture["eventBriefs"]]
    else:
        units = [{"key": "annual", "label": "年度简报" if step.step_no == 1 else "年度研判", "status": "waiting"}]
    return PlanningProgress.model_validate({"units": units}).model_dump(exclude_none=True)


def planning_progress_snapshot(run, *, error_code=None):
    try:
        progress = PlanningProgress.model_validate(run.planning_progress)
    except ValueError as exc:
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Persisted planning progress is invalid") from exc
    states = [item.status for item in progress.units]
    if (run.status == "running" and any(value in {"failed", "cancelled"} for value in states)
        or run.status == "completed" and any(value != "completed" for value in states)
        or run.status == "failed" and any(value in {"waiting", "running"} for value in states)
        or run.status not in {"running", "completed", "failed"}):
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Planning parent status does not match unit states")
    snapshot = {"activityId": str(run.activity_id), "generationId": str(run.generation_id), "stepNo": run.step_no,
                "status": run.status, "totalUnits": len(progress.units), "completedUnits": sum(item.status == "completed" for item in progress.units),
                "units": [{"key": item.key, "label": item.label, "status": item.status} for item in progress.units]}
    if run.status == "failed":
        if not error_code:
            raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Failed planning progress requires a public error code")
        snapshot["errorCode"] = error_code
    return snapshot


def aggregate_planning_audit(progress):
    parsed = PlanningProgress.model_validate(progress)
    return {"duration_ms": sum(item.durationMs or 0 for item in parsed.units),
            "usage": {"prompt_tokens": sum(item.promptTokens or 0 for item in parsed.units),
                      "completion_tokens": sum(item.completionTokens or 0 for item in parsed.units),
                      "total_tokens": sum(item.totalTokens or 0 for item in parsed.units)}}


def result_audit(result):
    return {"model": result.model, "providerRequestId": result.provider_request_id, "durationMs": result.duration_ms,
            "promptTokens": result.prompt_tokens, "completionTokens": result.completion_tokens, "totalTokens": result.total_tokens}


def annual_architecture(activity):
    step = find_step(activity=activity, step_no=3)
    if step.status != "confirmed":
        raise StepDomainError("PREVIOUS_STEP_NOT_CONFIRMED", "Confirm the annual architecture before generating later steps")
    return validate_step_output(3, dict(step.output_json), search_enabled=activity.search_enabled,
                                planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")


def saved_unit_output(activity, step, key):
    if not step.output_json:
        return None
    if activity.input.get("planningMode", "single") != "annual" or step.step_no < 4:
        return deepcopy(step.output_json)
    canonical = validate_step_output(step.step_no, dict(step.output_json), search_enabled=activity.search_enabled,
                                     planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")
    if key == "annual":
        return canonical["annualPlan"]
    return next((item["output"] for item in canonical["eventPlans"] if item["eventId"] == key), None)


def planning_unit_messages(activity, step, key, *, architecture_draft=None, current_annual_plan=None):
    annual = activity.input.get("planningMode", "single") == "annual"
    if not annual or step.step_no < 3:
        from backend.activity_steps import build_generation_messages
        return build_generation_messages(activity, step)
    schema = GENERATION_OUTPUT_SCHEMAS[step.step_no]
    instruction = "请只生成当前规划单元的纯 JSON 草稿，严格遵守 requiredJsonSchema。"
    context = {"activityInput": activity.input, "planningUnit": {"key": key}, "searchEnabled": activity.search_enabled}
    research = find_step(activity=activity, step_no=2)
    if research.status != "confirmed":
        raise StepDomainError("PREVIOUS_STEP_NOT_CONFIRMED", "Confirm research before annual planning")
    context["confirmedResearchEvidence"] = validate_step_output(2, dict(research.output_json), search_enabled=activity.search_enabled, error_code="PERSISTED_STEP_OUTPUT_INVALID")
    preceding = []
    constraints = []
    brief_step = find_step(activity=activity, step_no=1)
    if brief_step.status != "confirmed":
        raise StepDomainError("PREVIOUS_STEP_NOT_CONFIRMED", "Confirm the standardized brief before annual planning")
    preceding.append({"stepNo": 1, "output": validate_step_output(1, dict(brief_step.output_json),
        search_enabled=activity.search_enabled, planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")})
    if step.step_no == 3:
        if key == "annual":
            schema = AnnualArchitectureDraft
            count = activity.input["plannedEventCount"]
            context["requiredEventIds"] = [f"event-{index}" for index in range(1, count + 1)]
            instruction += f"本次只生成年度总叙事与恰好 {count} 个活动种子，id 严格依次采用 requiredEventIds；各活动亮点和共享资产会逐场另行生成，不得一次展开所有简案。"
            instruction += "annualNarrative 将作为完整年度架构的最终展示文字，只描述业务定位、客群、年度活动节奏和统筹约束；禁止描述模型请求、种子设定、生成进度、后续另行生成或其他内部流程。"
        else:
            if architecture_draft is None:
                raise StepDomainError("INVALID_GENERATION_METADATA", "Event brief generation requires its annual architecture draft")
            seed = next((item for item in architecture_draft["eventSeeds"] if item["id"] == key), None)
            if seed is None:
                raise StepDomainError("INVALID_GENERATION_METADATA", "Event seed does not exist")
            schema = AnnualEventDetails
            context.update(annualNarrative=architecture_draft["annualNarrative"], currentEventSeed=seed)
            instruction += "本次只输出这一场活动的 sharedAssets 和 highlights；服务端保留其余种子字段，不得输出或重写它们。不要输出其他活动或完整年度活动列表。"
    else:
        architecture = annual_architecture(activity)
        context["annualNarrative"] = architecture["annualNarrative"]
        if key == "annual":
            context["eventBriefs"] = architecture["eventBriefs"]
            instruction += "本次仅生成年度共享资产、统筹安排和跨活动约束；不得重复计入各场活动专属成本或代替各场方案。"
        else:
            brief = next((item for item in architecture["eventBriefs"] if item["id"] == key), None)
            if brief is None:
                raise StepDomainError("INVALID_GENERATION_METADATA", "Planning unit is outside the confirmed architecture")
            context["currentEventBrief"] = brief
            if current_annual_plan is None:
                raise StepDomainError("INVALID_GENERATION_METADATA", "Current event generation requires its annual coordination draft")
            context["currentAnnualPlan"] = current_annual_plan
            instruction += "本次仅生成当前活动专属方案，遵守年度统筹约束；共享成本已计入年度统筹预算，不得在单场预算重复计费。"
        allowed_preceding = {4, 5, 6} if step.step_no == 7 else set(range(1, step.step_no))
        ids = annual_plan_event_ids(activity)
        for previous in list_steps(activity=activity):
            if previous.step_no not in allowed_preceding or previous.status != "confirmed" or previous.step_no in {2, 3}:
                continue
            if previous.step_no == 1:
                continue
            output = validate_step_output(previous.step_no, dict(previous.output_json), search_enabled=activity.search_enabled,
                                          planning_mode="annual", event_ids=ids, error_code="PERSISTED_STEP_OUTPUT_INVALID")
            constraints.append({"stepNo": previous.step_no, "output": output["annualPlan"]})
            unit_output = output["annualPlan"] if key == "annual" else next(item["output"] for item in output["eventPlans"] if item["eventId"] == key)
            preceding.append({"stepNo": previous.step_no, "output": unit_output})
        if key != "annual":
            context["annualConstraints"] = constraints
        if step.step_no == 9:
            saved = saved_unit_output(activity, step, key)
            if saved and saved["actualMetrics"]:
                schema = ReviewAnalysisGenerationOutput
                context.update({field: saved[field] for field in ("forecastMetrics", "actualMetrics", "missingActualMetrics")})
                instruction += "仅生成 conclusions 与 improvements；服务端原样保留当前单元已录入的全部指标。年度层不加总复游率、占比或满意度等比率型指标。"
        if step.step_no == 5:
            instruction += "预算仅输出基础项，禁止 subtotal、totalAmount 和 annualTotalAmount；所有金额合计由服务端确定性计算。"
    context.update(confirmedPreviousSteps=preceding, requiredJsonSchema=schema.model_json_schema(by_alias=True))
    return [{"role": "system", "content": build_activity_system_prompt(step.step_no, step.step_key)},
            {"role": "user", "content": instruction + "\n" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))}]


def validate_planning_unit_output(activity, step, key, text, *, architecture_draft=None):
    annual = activity.input.get("planningMode", "single") == "annual"
    if not annual or step.step_no < 3:
        return validate_generated_output(step.step_no, text, search_enabled=activity.search_enabled,
                                         planning_mode=activity.input.get("planningMode", "single"), saved_step_output=saved_unit_output(activity, step, key))
    if step.step_no >= 4:
        return validate_generated_output(step.step_no, text, search_enabled=activity.search_enabled,
                                         saved_step_output=saved_unit_output(activity, step, key) if step.step_no == 9 else None)
    try:
        raw = json.loads(text, object_pairs_hook=_unique_json_object, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise StepDomainError("INVALID_MODEL_RESPONSE", "Model response was not valid JSON") from exc
    if not isinstance(raw, dict):
        raise StepDomainError("INVALID_MODEL_RESPONSE", "Model response must be a JSON object")
    try:
        _validate_generated_user_visible_strings(raw)
        if key == "annual":
            result = AnnualArchitectureDraft.model_validate(raw).model_dump(by_alias=True, mode="json")
            expected_ids = [f"event-{index}" for index in range(1, activity.input["plannedEventCount"] + 1)]
            if [item["id"] for item in result["eventSeeds"]] != expected_ids:
                raise ValueError("generated event seed IDs must match the requested count and order")
            return result
        details = AnnualEventDetails.model_validate(raw).model_dump(by_alias=True, mode="json")
        seed = next(item for item in architecture_draft["eventSeeds"] if item["id"] == key)
        return AnnualEventBrief.model_validate({**seed, **details}).model_dump(by_alias=True, mode="json")
    except (ValueError, StopIteration, TypeError) as exc:
        raise StepDomainError("INVALID_MODEL_RESPONSE", "Planning unit output does not match its confirmed contract") from exc


def merge_planning_outputs(activity, step, outputs):
    if activity.input.get("planningMode", "single") != "annual" or step.step_no < 3:
        return outputs[0][1]
    if step.step_no == 3:
        result = {"annualNarrative": outputs[0][1]["annualNarrative"], "eventBriefs": [output for _, output in outputs[1:]]}
        return validate_step_output(3, result, search_enabled=activity.search_enabled, planning_mode="annual", error_code="INVALID_MODEL_RESPONSE")
    result = {"annualPlan": outputs[0][1], "eventPlans": [{"eventId": key, "output": output} for key, output in outputs[1:]]}
    if step.step_no == 5:
        result["annualTotalAmount"] = _calculated_budget_total([output["totalAmount"] for _, output in outputs])
    return validate_step_output(step.step_no, result, search_enabled=activity.search_enabled, planning_mode="annual",
                                event_ids=annual_plan_event_ids(activity), error_code="INVALID_MODEL_RESPONSE")
