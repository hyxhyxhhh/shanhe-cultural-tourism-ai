"""Export confirmed annual coordination and every event brief without loss."""

from __future__ import annotations

from decimal import Decimal
from pydantic import ValidationError

from backend.activities import ActivityBriefInputData
from backend.activity_steps import StepDomainError, validate_step_output


ANNUAL_STEP_HEADINGS = {
    4: "内容与空间",
    5: "预算与资源",
    6: "传播计划",
    7: "执行准备",
    8: "渠道商业化",
    9: "预测与复盘",
}

FIELD_LABELS = {
    "idea": "活动构想", "planningMode": "策划类型", "location": "景区地点",
    "plannedStartAt": "计划开始时间", "plannedEndAt": "计划结束时间", "target": "策划目标",
    "budgetMin": "年度预算下限", "budgetMax": "年度预算上限", "targetAudience": "目标客群",
    "knownConstraints": "已知约束", "annualPeriod": "年度规划周期", "annualGoals": "年度目标",
    "plannedEventCount": "计划活动数量", "annualNarrative": "年度总叙事", "eventBriefs": "活动组合",
    "id": "简案编号", "name": "名称", "timeWindow": "时间窗口", "positioning": "活动定位",
    "themeDirection": "主题方向", "scale": "活动规模", "sharedAssets": "可共享资源", "highlights": "活动亮点",
    "schedule": "活动安排", "time": "时间", "title": "标题", "description": "说明",
    "zones": "空间分区", "purpose": "用途", "activities": "活动内容", "requirements": "资源要求",
    "personnel": "人员配置", "role": "岗位", "count": "人数", "responsibilities": "岗位职责",
    "safetyRequirements": "安全要求", "items": "预算明细", "item": "项目", "category": "分类",
    "quantity": "数量", "unit": "单位", "unitPrice": "单价", "subtotal": "小计", "sourceType": "来源类型",
    "basis": "依据", "totalAmount": "预算合计", "savings": "节省方案", "action": "措施",
    "estimatedSaving": "预计节省", "impact": "影响", "resources": "资源配置", "budgetNote": "预算说明",
    "strategy": "传播策略", "phases": "传播阶段", "phase": "阶段", "objective": "目标", "channels": "渠道",
    "contentDrafts": "传播内容草稿", "materials": "所需素材", "tasks": "执行任务", "owner": "负责人",
    "dueAt": "截止时间", "dependencies": "前置依赖", "approvalDraft": "审批草稿",
    "supplierInquiryDraft": "供应商询价草稿", "approvalSummary": "审批总览",
    "externalActionsDraftOnly": "外部动作仅为草稿", "channelActions": "渠道联动", "channel": "渠道",
    "actions": "行动方案", "revenueModel": "收入模式", "draftTerms": "合作条款草稿",
    "sponsorshipPackages": "赞助方案", "targetPartner": "目标合作方", "benefits": "合作权益",
    "referencePrice": "参考价格", "ticketingPlan": "票务方案", "secondarySalesPlan": "二次消费方案",
    "forecastMetrics": "预测指标", "actualMetrics": "实际指标", "missingActualMetrics": "待补充实际指标",
    "metric": "指标", "value": "数值", "conclusions": "结论", "improvements": "改进措施",
}
ENUM_LABELS = {
    "planningMode": {"annual": "年度活动组合", "single": "单场活动"},
    "sourceType": {"actual": "实际数据", "public": "公开信息", "calculated": "推算数据", "missing": "数据缺失"},
    "phase": {"warmup": "预热期", "peak": "集中传播期", "followup": "延续期"},
}
METRIC_LABELS = {"attendance": "客流", "revenue": "收入", "cost": "成本", "exposure": "曝光", "engagement": "互动", "conversion": "转化"}
TASK_STATUS_LABELS = {"draft": "草稿", "pending_confirmation": "待确认", "ready": "待执行", "in_progress": "执行中", "blocked": "受阻", "completed": "已完成"}


def _text(output: dict) -> str:
    def lines(value, indent=0, field=""):
        prefix = "  " * indent
        if isinstance(value, dict):
            result = []
            for key, item in value.items():
                if key not in FIELD_LABELS:
                    raise StepDomainError("ANNUAL_EXPORT_FIELD_UNSUPPORTED", "年度导出包含未定义的字段")
                if isinstance(item, (dict, list)):
                    result.append(f"{prefix}{FIELD_LABELS[key]}：")
                    result.extend(lines(item, indent + 1, key))
                else:
                    result.append(f"{prefix}{FIELD_LABELS[key]}：{scalar(item, key)}")
            return result
        if isinstance(value, list):
            result = []
            for index, item in enumerate(value, 1):
                if isinstance(item, (dict, list)):
                    result.append(f"{prefix}{index}.")
                    result.extend(lines(item, indent + 1, field))
                else:
                    result.append(f"{prefix}{index}. {scalar(item, field)}")
            return result or [f"{prefix}当前无记录"]
        raise StepDomainError("ANNUAL_EXPORT_FIELD_UNSUPPORTED", "年度导出字段结构不正确")

    def scalar(value, field):
        if field in ENUM_LABELS:
            try:
                return ENUM_LABELS[field][value]
            except KeyError as exc:
                raise StepDomainError("ANNUAL_EXPORT_ENUM_UNSUPPORTED", "年度导出包含未定义的选项") from exc
        if field in {"metric", "missingActualMetrics"} and value in METRIC_LABELS:
            return METRIC_LABELS[value]
        if isinstance(value, bool):
            return "是" if value else "否"
        return str(value)

    return "\n".join(lines(output))


def _money(value) -> str:
    return format(Decimal(str(value)), "f")


def annual_export_content(activity, steps: dict) -> tuple[dict[str, str], list[dict[str, object]]]:
    """Validate persisted annual data before producing cross-event documents."""
    try:
        brief = ActivityBriefInputData.model_validate(activity.input)
    except ValidationError as exc:
        raise StepDomainError("PERSISTED_ANNUAL_BRIEF_INVALID", "年度简报不符合确认的字段约定") from exc
    if brief.planning_mode != "annual":
        raise StepDomainError("ANNUAL_PLAN_REQUIRED", "年度导出要求年度策划简报")
    architecture = validate_step_output(3, steps[3].output_json, search_enabled=activity.search_enabled, planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")
    events = architecture["eventBriefs"]
    expected_ids = {event["id"] for event in events}
    outputs = {}
    for step_no in ANNUAL_STEP_HEADINGS:
        output = validate_step_output(step_no, steps[step_no].output_json, search_enabled=activity.search_enabled, planning_mode="annual", error_code="PERSISTED_STEP_OUTPUT_INVALID")
        if {event["eventId"] for event in output["eventPlans"]} != expected_ids:
            raise StepDomainError("ANNUAL_EVENT_SCOPE_MISMATCH", f"第{step_no}步活动简案范围与年度架构不一致")
        outputs[step_no] = output

    sections = {
        "年度活动简报": _text(brief.model_dump(by_alias=True, exclude_none=True, mode="json")),
        "年度总叙事与活动组合": _text(architecture),
    }
    for step_no, heading in ANNUAL_STEP_HEADINGS.items():
        sections[f"年度统筹｜{heading}"] = _text(outputs[step_no]["annualPlan"])
    sections["年度预算合计"] = f"全年预算合计：{_money(outputs[5]['annualTotalAmount'])}；年度共享成本计入年度统筹一次，各活动专属成本分别列示。"
    for event in events:
        # IDs avoid overwriting sections if two distinct events share a name.
        prefix = f"活动简案｜{event['name']}（{event['id']}）"
        sections[prefix] = _text(event)
        for step_no, heading in ANNUAL_STEP_HEADINGS.items():
            current = next(item["output"] for item in outputs[step_no]["eventPlans"] if item["eventId"] == event["id"])
            sections[f"{prefix}｜{heading}"] = _text(current)

    budget = outputs[5]
    names = {event["id"]: event["name"] for event in events}
    blocks = [("年度统筹／共享成本", budget["annualPlan"])] + [(f"{names[item['eventId']]}（{item['eventId']}）", item["output"]) for item in budget["eventPlans"]]
    rows = []
    for label, block in blocks:
        for item in block["items"]:
            rows.append({
                "项目": f"{label}｜{item['item']}",
                "数量": item["quantity"],
                "单价": _money(item["unitPrice"]),
                "小计": _money(item["subtotal"]),
                "来源": f"{ENUM_LABELS['sourceType'][item['sourceType']]}：{item['basis']}",
            })
        rows.append({"项目": f"{label}｜汇总（非新增成本）", "数量": "", "单价": "", "小计": _money(block["totalAmount"]), "来源": "推算数据：本组预算明细合计，仅供核对"})
    rows.append({"项目": "全年预算合计（非新增成本）", "数量": "", "单价": "", "小计": _money(budget["annualTotalAmount"]), "来源": "推算数据：年度共享成本与各活动专属成本之和，仅供核对"})
    return sections, rows


def annual_execution_rows(steps: dict, tasks: list) -> list[dict[str, object]]:
    """Attach annual/event labels to actual tasks from the confirmed version."""
    names = {item["id"]: item["name"] for item in steps[3].output_json["eventBriefs"]}
    output = steps[7].output_json
    blocks = [("年度统筹", output["annualPlan"])] + [(names[item["eventId"]], item["output"]) for item in output["eventPlans"]]
    labels = [label for label, block in blocks for _task in block["tasks"]]
    generated = [task for task in tasks if task.source_step_version == steps[7].version]
    if len(generated) != len(labels) or {task.source_task_index for task in generated} != set(range(len(labels))):
        raise StepDomainError("EXECUTION_TASK_SYNC_CONFLICT", "年度执行任务与已确认简案数量或索引不一致")
    generated.sort(key=lambda task: task.source_task_index)
    rows = []
    for task in [*generated, *[task for task in tasks if task.source_step_version is None]]:
        label = "手动追加任务" if task.source_step_version is None else labels[task.source_task_index]
        if task.status not in TASK_STATUS_LABELS:
            raise StepDomainError("ANNUAL_EXPORT_TASK_STATUS_UNSUPPORTED", "年度执行任务包含未定义的状态")
        rows.append({
            "任务": f"{label}｜{task.title}",
            "负责人": task.owner or "",
            "截止时间": task.due_at.isoformat() if task.due_at else "",
            "状态": TASK_STATUS_LABELS[task.status],
            "附件": ",".join(task.attachment_file_ids),
        })
    return rows
