"""Versioned deliverable endpoints with injected storage."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from backend.app.deliverables.service import DeliverableRecord, DeliverableService
from backend.app.deliverables.annual import annual_execution_rows, annual_export_content
from backend.activity_steps import StepDomainError
from backend.auth import CurrentSession, DbSession
from backend.models import Activity, ExecutionTask


router = APIRouter(prefix="/api/activities/{activity_id}/deliverables", tags=["deliverables"])


def _owned_activity(activity_id: UUID, current, db) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.created_by == str(current.user_id))
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _service(request: Request) -> DeliverableService:
    service = getattr(request.app.state, "deliverable_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deliverable storage is not configured",
        )
    return service


def _serialize(record: DeliverableRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "activityId": record.activity_id,
        "filename": record.filename,
        "contentType": record.content_type,
        "storageKey": record.storage_key,
        "version": record.version,
        "createdAt": record.created_at.isoformat(),
    }


@router.get("")
async def list_deliverables(
    activity_id: UUID,
    current: CurrentSession,
    db: DbSession,
    request: Request,
) -> list[dict[str, object]]:
    activity = _owned_activity(activity_id, current, db)
    records = await _service(request).list(str(activity.id))
    return [_serialize(record) for record in records]


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_deliverables(
    activity_id: UUID,
    current: CurrentSession,
    db: DbSession,
    request: Request,
) -> list[dict[str, object]]:
    activity = _owned_activity(activity_id, current, db)
    steps = {step.step_no: step for step in activity.steps}
    is_annual = activity.input.get("planningMode", "single") == "annual"
    required = [3, 4, 5, 6, 7, 8, 9] if is_annual else [4, 5, 6, 7, 8, 9]
    missing = [step_no for step_no in required if steps.get(step_no) is None or steps[step_no].status != "confirmed"]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"以下步骤尚未确认：{','.join(str(step_no) for step_no in missing)}",
        )
    tasks = db.scalars(select(ExecutionTask).where(ExecutionTask.activity_id == activity.id)).all()
    if is_annual:
        try:
            sections, budget_rows = annual_export_content(activity, steps)
        except StepDomainError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message}) from exc
    else:
        budget_rows = _rows_from_step(steps[5].output_json)
        sections = {
            "活动简报": activity.input.get("idea", ""),
            "预算控制": _section_text(steps[5].output_json),
            "传播计划": _section_text(steps[6].output_json),
            "执行准备": _section_text(steps[7].output_json),
            "渠道商业化": _section_text(steps[8].output_json),
            "预测与复盘": _section_text(steps[9].output_json),
        }
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="没有可导出的执行任务",
        )
    if is_annual:
        try:
            execution_rows = annual_execution_rows(steps, tasks)
        except StepDomainError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message}) from exc
    else:
        execution_rows = []
        for task in tasks:
            execution_rows.append(
                {
                    "任务": task.title,
                    "负责人": task.owner or "",
                    "截止时间": task.due_at.isoformat() if task.due_at else "",
                    "状态": task.status,
                    "附件": ",".join(task.attachment_file_ids),
                }
            )
    idea = activity.input.get("idea")
    if not isinstance(idea, str) or not idea.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="活动简报缺少活动构想",
        )
    records = await _service(request).generate_all(
        activity_id=str(activity.id),
        title=activity.title,
        sections=sections,
        budget_rows=budget_rows,
        execution_rows=execution_rows,
        preserve_document_lines=is_annual,
    )
    return [_serialize(record) for record in records]


@router.get("/{deliverable_id}/download")
async def download_deliverable(
    activity_id: UUID,
    deliverable_id: str,
    current: CurrentSession,
    db: DbSession,
    request: Request,
) -> Response:
    activity = _owned_activity(activity_id, current, db)
    records = await _service(request).list(str(activity.id))
    record = next((item for item in records if item.id == deliverable_id), None)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found")
    content = await _service(request).read(record)
    return Response(
        content=content,
        media_type=record.content_type,
        headers={"Content-Disposition": f'attachment; filename="{record.filename}"'},
    )


def _rows_from_step(output: dict[str, object]) -> list[dict[str, object]]:
    rows = output.get("items")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="预算步骤缺少可导出的明细行",
        )
    if not all(isinstance(row, dict) for row in rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="预算步骤明细行格式无效",
        )
    required = {
        "item",
        "quantity",
        "unitPrice",
        "subtotal",
        "sourceType",
        "basis",
    }
    if any(not required.issubset(row) for row in rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="预算步骤明细行缺少导出字段",
        )
    return [
        {
            "项目": row["item"],
            "数量": row["quantity"],
            "单价": row["unitPrice"],
            "小计": row["subtotal"],
            "来源": f'{row["sourceType"]}: {row["basis"]}',
        }
        for row in rows
    ]


def _section_text(output: dict[str, object]) -> str:
    if not output:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已确认步骤缺少可导出的内容",
        )
    return json.dumps(output, ensure_ascii=False, indent=2)
