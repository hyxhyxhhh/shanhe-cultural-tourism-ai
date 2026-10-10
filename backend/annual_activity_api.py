"""Create an independent single activity from one confirmed annual event brief."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from backend.activities import ActivityBriefInputData, create_activity, get_activity
from backend.activity_api import ActivityDb, ActivityDTO, CurrentUser, serialize_activity
from backend.activity_steps import StepDomainError, find_step, get_owned_activity, validate_step_output
from backend.annual_activity_models import AnnualPlanItemActivity


router = APIRouter(prefix="/api/activities", tags=["annual activities"])


class CreatePlanItemActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1, strict=True)


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message})


def _annual_activity(activity_id: UUID, current: CurrentUser, db: ActivityDb, *, lock: bool):
    activity = get_owned_activity(activity_id=activity_id, owner_id=str(current.user_id), session=db, lock=lock)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    try:
        brief = ActivityBriefInputData.model_validate(activity.input)
    except ValidationError as exc:
        raise _conflict("INVALID_ANNUAL_BRIEF", "年度策划简报格式无效") from exc
    if brief.planning_mode != "annual":
        raise _conflict("ANNUAL_PLAN_REQUIRED", "仅年度策划支持单场深入")
    return activity


def _single_brief(activity, architecture: dict, event: dict) -> dict:
    idea = "\n".join([
        f"年度总叙事：{architecture['annualNarrative']}",
        f"本场活动：{event['name']}",
        f"建议时间窗口：{event['timeWindow']}（具体起止日期待确认）",
        f"活动定位：{event['positioning']}",
        f"主题方向：{event['themeDirection']}",
        f"规模：{event['scale']}",
        f"活动亮点：{'；'.join(event['highlights'])}",
        f"可共享资源：{'；'.join(event['sharedAssets'])}",
    ])
    constraints = [
        f"源年度规划周期：{activity.input['annualPeriod']}",
        f"源年度总体目标：{activity.input['annualGoals']}",
        "本场预算需单独核定，年度整体预算不得作为本场预算。",
    ]
    for name, label in (("budgetMin", "年度预算下限"), ("budgetMax", "年度预算上限")):
        if name in activity.input:
            constraints.append(f"{label}：{activity.input[name]}（覆盖全年活动及共享成本）")
    if "knownConstraints" in activity.input:
        constraints.append(f"年度约束：{activity.input['knownConstraints']}")
    raw = {"planningMode": "single", "idea": idea, "targetAudience": event["targetAudience"], "knownConstraints": "\n".join(constraints)}
    if "location" in activity.input:
        raw["location"] = activity.input["location"]
    try:
        return ActivityBriefInputData.model_validate(raw).model_dump(by_alias=True, exclude_none=True, mode="json")
    except ValidationError as exc:
        raise _conflict("PLAN_ITEM_BRIEF_INVALID", "本场活动简报超过字段长度限制，请先精简年度叙事或活动简案") from exc


@router.post("/{activity_id}/plan-items/{event_id}/activity", response_model=ActivityDTO, status_code=status.HTTP_201_CREATED)
def create_plan_item_activity(activity_id: UUID, event_id: str, payload: CreatePlanItemActivityRequest, current: CurrentUser, db: ActivityDb) -> ActivityDTO:
    # Serialize creation and annual edits with the same parent row lock used by
    # step writes. The link and all nine child steps commit atomically.
    activity = _annual_activity(activity_id, current, db, lock=True)
    if activity.status in {"archived", "paused"}:
        raise _conflict("ACTIVITY_NOT_WRITABLE", "已归档或暂停的年度策划不能创建单场活动")
    step = find_step(activity=activity, step_no=3)
    if step.version != payload.version:
        raise _conflict("VERSION_CONFLICT", "年度活动架构版本已变更，请刷新后重试")
    if step.status != "confirmed":
        raise _conflict("ANNUAL_PLAN_NOT_CONFIRMED", "请先确认第三步年度活动架构")
    try:
        architecture = validate_step_output(3, step.output_json, search_enabled=activity.search_enabled, planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")
    except StepDomainError as exc:
        raise _conflict(exc.code, exc.message) from exc
    event = next((item for item in architecture["eventBriefs"] if item["id"] == event_id), None)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "PLAN_ITEM_NOT_FOUND", "message": "年度活动简案不存在"})
    link = db.scalar(select(AnnualPlanItemActivity).where(AnnualPlanItemActivity.annual_activity_id == activity_id, AnnualPlanItemActivity.event_id == event_id))
    if link is not None:
        if link.source_step_version != step.version:
            raise _conflict("PLAN_ITEM_SOURCE_CHANGED", "年度活动架构已更新，已有独立策划保留原内容，请先核对源版本")
        child = get_activity(activity_id=link.child_activity_id, created_by=str(current.user_id), session=db)
        if child is None:
            raise _conflict("PLAN_ITEM_LINK_INVALID", "年度单场策划关联无效")
        result = serialize_activity(child)
        db.commit()
        return result
    brief = _single_brief(activity, architecture, event)
    child = create_activity(title=event["name"], idea=brief["idea"], created_by=str(current.user_id), input_data=brief, session=db)
    db.add(AnnualPlanItemActivity(annual_activity_id=activity.id, event_id=event_id, child_activity_id=child.id, source_step_version=step.version))
    db.flush()
    result = serialize_activity(child)
    db.commit()
    return result
