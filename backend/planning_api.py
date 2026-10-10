"""Streaming planning orchestration with durable unit progress and atomic output."""

from copy import deepcopy
import json
import logging
import time
from uuid import UUID

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask

from backend.activity_api import (
    ActivityDb, CurrentUser, GenerationProvider, GenerateStepRequest,
    _locked_step, _owned_activity, _research_public_code, _step_dto, _step_error,
)
from backend.activity_steps import (
    StepDomainError, _active_run, complete_generation, fail_generation, find_step,
    generation_failure_diagnostic, start_generation,
)
from backend.ccode_provider import CcodeProviderError, ModelMessage
from backend.model_catalog import AllowedModels
from backend.models import ModelRun
from backend.planning_generation import (
    PlanningProgress, aggregate_planning_audit, initial_planning_progress,
    merge_planning_outputs, planning_progress_snapshot, planning_unit_messages,
    result_audit, validate_planning_unit_output,
)


router = APIRouter()
logger = logging.getLogger(__name__)


def _locked_planning_run(activity_id, step_no, generation_id, current, db):
    activity, step = _locked_step(activity_id, step_no, current, db)
    run = _active_run(db, generation_id)
    if run.activity_id != activity.id or run.step_no != step_no or step.status != "generating":
        raise StepDomainError("GENERATION_STALE", "Planning generation is no longer active")
    try:
        PlanningProgress.model_validate(run.planning_progress)
    except ValueError as exc:
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Planning progress is invalid") from exc
    return activity, step, run


def _record_planning_unit(run, key, new_status, db, *, result=None):
    progress = deepcopy(run.planning_progress)
    entry = next((item for item in progress["units"] if item["key"] == key), None)
    if entry is None or new_status not in {"running", "completed"} or entry["status"] != {"running": "waiting", "completed": "running"}[new_status]:
        raise StepDomainError("INVALID_GENERATION_METADATA", "Planning unit transition is invalid")
    entry["status"] = new_status
    if result is not None:
        entry.update(result_audit(result))
    try:
        run.planning_progress = PlanningProgress.model_validate(progress).model_dump(exclude_none=True)
    except ValueError as exc:
        raise StepDomainError("INVALID_GENERATION_METADATA", "Planning provider metadata is invalid") from exc
    snapshot = planning_progress_snapshot(run)
    db.commit()
    return snapshot


def _fail_planning_group(activity_id, step_no, generation_id, current, db, error_code, model, *, failed_key=None, result=None, duration_ms=None, request_id=None):
    db.rollback()
    activity, step = _locked_step(activity_id, step_no, current, db)
    run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id).with_for_update().execution_options(populate_existing=True))
    if run is None or run.activity_id != activity.id or run.step_no != step_no:
        raise StepDomainError("GENERATION_STALE", "Planning generation is no longer active")
    superseded = run.status == "failed" and run.error_code == "GENERATION_SUPERSEDED"
    if not superseded and (run.status != "running" or step.status != "generating"):
        raise StepDomainError("GENERATION_STALE", "Planning generation is no longer active")
    progress = deepcopy(run.planning_progress)
    for item in progress["units"]:
        if item["key"] == failed_key:
            if item["status"] != ("failed" if superseded else "running"):
                raise StepDomainError("INVALID_GENERATION_METADATA", "Only the current planning unit can fail")
            item.update(status="failed", errorCode="GENERATION_SUPERSEDED" if superseded else error_code)
            if result is not None:
                item.update(result_audit(result))
            else:
                item["model"] = model
                if duration_ms is not None:
                    item["durationMs"] = duration_ms
                if request_id is not None:
                    item["providerRequestId"] = request_id
        elif not superseded and item["status"] in {"waiting", "running"}:
            item.update(status="cancelled", errorCode=error_code)
    try:
        run.planning_progress = PlanningProgress.model_validate(progress).model_dump(exclude_none=True)
    except ValueError as exc:
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Failed planning audit is invalid") from exc
    aggregate = aggregate_planning_audit(run.planning_progress)
    if superseded:
        run.duration_ms = aggregate["duration_ms"]
        run.prompt_tokens = aggregate["usage"]["prompt_tokens"]
        run.completion_tokens = aggregate["usage"]["completion_tokens"]
        run.total_tokens = aggregate["usage"]["total_tokens"]
    else:
        fail_generation(activity=activity, step=step, generation_id=generation_id, actor=str(current.user_id),
                        error_code=error_code, model=model, request_id=None, session=db, **aggregate)
    snapshot = planning_progress_snapshot(run, error_code=_research_public_code(run.error_code))
    db.commit()
    return snapshot


@router.get("/{activity_id}/steps/{step_no}/generate/progress")
def get_planning_generation_progress(activity_id: UUID, step_no: int, current: CurrentUser, db: ActivityDb):
    activity = _owned_activity(activity_id, current, db)
    try:
        find_step(activity=activity, step_no=step_no)
    except StepDomainError as exc:
        raise HTTPException(status_code=404, detail="Activity step not found") from exc
    run = db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id, ModelRun.step_no == step_no)
                    .order_by(ModelRun.started_at.desc(), ModelRun.id.desc()).limit(1).execution_options(populate_existing=True))
    progress = None if run is None or run.planning_progress is None else planning_progress_snapshot(run, error_code=_research_public_code(run.error_code) if run.error_code else None)
    return {"activityId": str(activity_id), "stepNo": step_no, "progress": progress}


@router.post("/{activity_id}/steps/{step_no}/generate/stream")
def stream_planning_generation(activity_id: UUID, step_no: int, payload: GenerateStepRequest, request: Request,
                               current: CurrentUser, db: ActivityDb, provider: GenerationProvider, allowed_models: AllowedModels):
    activity, step = _locked_step(activity_id, step_no, current, db)
    if step_no == 2 and activity.search_enabled:
        db.rollback()
        raise _step_error(StepDomainError("USE_RESEARCH_STREAM_ENDPOINT", "Web research requires per-scope streaming generation"))
    if payload.model not in allowed_models:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": "MODEL_NOT_ALLOWED", "message": "The selected model is not allowed"})
    try:
        generation_id, raw_messages = start_generation(activity=activity, step=step, expected_version=payload.version,
                                                       model=payload.model, actor=str(current.user_id), session=db)
        run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id))
        run.planning_progress = initial_planning_progress(activity, step)
        initial = planning_progress_snapshot(run)
        db.commit()
    except StepDomainError as exc:
        db.rollback()
        raise _step_error(exc) from exc
    except ValueError as exc:
        db.rollback()
        raise _step_error(StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Planning generation units do not match the activity contract")) from exc

    def event(name, value):
        return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"

    async def events():
        terminal = False
        outputs = []
        current_key = None
        result = None
        started = None
        required_schema = None
        try:
            yield event("planning_progress", initial)
            for unit in initial["units"]:
                if await request.is_disconnected():
                    return
                unit_key = unit["key"]
                result = None
                started = None
                required_schema = None
                locked_activity, locked_step, locked_run = _locked_planning_run(activity_id, step_no, generation_id, current, db)
                architecture = outputs[0][1] if outputs and step_no == 3 else None
                annual_plan = outputs[0][1] if outputs and step_no >= 4 else None
                if locked_activity.input.get("planningMode", "single") == "annual" and step_no >= 3:
                    messages = planning_unit_messages(locked_activity, locked_step, unit_key,
                                                      architecture_draft=architecture, current_annual_plan=annual_plan)
                else:
                    messages = raw_messages
                required_schema = json.loads(messages[1]["content"].split("\n", 1)[1])["requiredJsonSchema"]
                snapshot = _record_planning_unit(locked_run, unit_key, "running", db)
                current_key = unit_key
                yield event("planning_progress", snapshot)
                started = time.perf_counter()
                # Protect the in-flight provider audit if the client disconnects.
                with anyio.CancelScope(shield=True):
                    result = await anyio.to_thread.run_sync(lambda: provider.generate(
                        [ModelMessage(**message) for message in messages], model=payload.model,
                        metadata={"activity_id": str(activity_id), "step_no": step_no, "generation_id": str(generation_id), "planning_unit": current_key},
                    ))
                output = validate_planning_unit_output(locked_activity, locked_step, current_key, result.text, architecture_draft=architecture)
                _activity, _step, locked_run = _locked_planning_run(activity_id, step_no, generation_id, current, db)
                outputs.append((current_key, output))
                snapshot = _record_planning_unit(locked_run, current_key, "completed", db, result=result)
                current_key = None
                result = None
                started = None
                yield event("planning_progress", snapshot)
            if await request.is_disconnected():
                return
            locked_activity, locked_step, locked_run = _locked_planning_run(activity_id, step_no, generation_id, current, db)
            merged = merge_planning_outputs(locked_activity, locked_step, outputs)
            complete_generation(activity=locked_activity, step=locked_step, generation_id=generation_id, actor=str(current.user_id),
                                output_json=merged, model=payload.model, request_id=None, session=db, planning_group=True,
                                **aggregate_planning_audit(locked_run.planning_progress))
            step_dto = _step_dto(locked_step, planning_mode=locked_activity.input.get("planningMode", "single")).model_dump(by_alias=True, mode="json")
            snapshot = planning_progress_snapshot(locked_run)
            db.commit()
            terminal = True
            yield event("planning_completed", {**snapshot, "step": step_dto})
        except (CcodeProviderError, StepDomainError) as exc:
            code = exc.error_code if isinstance(exc, CcodeProviderError) else exc.code
            if isinstance(exc, StepDomainError):
                diagnostic = generation_failure_diagnostic(exc, step_no=step_no,
                    response_text=result.text if result else None,
                    planning_mode=activity.input.get("planningMode", "single"),
                    required_json_schema=required_schema)
                diagnostic["unit"] = current_key
                logger.warning("activity_planning_generation_validation_failed %s", json.dumps(diagnostic, sort_keys=True))
            snapshot = _fail_planning_group(activity_id, step_no, generation_id, current, db, code, payload.model,
                                            failed_key=current_key, result=result,
                                            duration_ms=max(0, round((time.perf_counter() - started) * 1000)) if started is not None else None,
                                            request_id=exc.request_id if isinstance(exc, CcodeProviderError) else None)
            terminal = True
            yield event("planning_failed", snapshot)
        finally:
            if not terminal:
                with anyio.CancelScope(shield=True):
                    try:
                        _fail_planning_group(activity_id, step_no, generation_id, current, db, "GENERATION_INTERRUPTED", payload.model,
                                             failed_key=current_key, result=result,
                                             duration_ms=max(0, round((time.perf_counter() - started) * 1000)) if started is not None else None)
                    except StepDomainError as exc:
                        if exc.code != "GENERATION_STALE":
                            raise

    def cleanup_unstarted_response():
        db.rollback()
        run = db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id))
        if run is not None and run.status == "running":
            _fail_planning_group(activity_id, step_no, generation_id, current, db, "GENERATION_INTERRUPTED", payload.model)
        else:
            db.rollback()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(cleanup_unstarted_response))
