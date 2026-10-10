import type {
  CapabilityId,
  CockpitId,
  CockpitPreviewItem,
  CockpitSummary,
  RoleAccess,
  RoleOption,
  UserRoleId,
  WorkflowId
} from "@/lib/types/access";

export const ROLE_OPTIONS: RoleOption[] = [
  { id: "government", label: "政府决策者", spaceLabel: "政府决策空间" },
  { id: "group-executive", label: "城投/文旅集团高管", spaceLabel: "城投/文旅集团空间" },
  { id: "scenic-operator", label: "景区运营公司", spaceLabel: "景区运营空间" },
  { id: "creative-design", label: "文创/设计企业", spaceLabel: "文创/设计空间" },
  { id: "project-team", label: "项目专项团队", spaceLabel: "项目专项空间" },
  { id: "licensed-institution", label: "持牌机构", spaceLabel: "持牌机构空间" },
  { id: "expert-advisor", label: "专家/顾问", spaceLabel: "专家空间" },
  { id: "management", label: "管理层", spaceLabel: "管理层空间" },
  { id: "platform-admin", label: "平台管理员", spaceLabel: "后台管理空间" }
];

const ALL_COCKPITS: CockpitId[] = ["management", "ai-advisor", "decision-center", "task-center", "collaboration-room"];
const ALL_CAPABILITIES: CapabilityId[] = ["strategy", "assets", "operations", "event-agent", "marketing", "design", "project-control", "creative", "digital", "implementation", "capital"];
export const WORKFLOW_IDS: WorkflowId[] = ["project-lifecycle", "project-decision", "investment-construction", "financial-risk", "operating-growth"];

export const ROLE_ACCESS: Record<UserRoleId, RoleAccess> = {
  government: {
    cockpitIds: ["management", "decision-center"],
    capabilityIds: ["strategy", "assets", "project-control"],
    workflowIds: ["project-decision", "operating-growth"]
  },
  "group-executive": {
    cockpitIds: ["management", "ai-advisor", "decision-center"],
    capabilityIds: ["strategy", "assets", "capital", "operations"],
    workflowIds: ["project-decision", "financial-risk", "operating-growth"]
  },
  "scenic-operator": {
    cockpitIds: ["task-center", "ai-advisor"],
    capabilityIds: ["operations", "event-agent", "marketing"],
    workflowIds: ["operating-growth", "investment-construction"]
  },
  "creative-design": {
    cockpitIds: ["task-center", "ai-advisor"],
    capabilityIds: ["creative", "design"],
    workflowIds: ["operating-growth", "investment-construction"]
  },
  "project-team": {
    cockpitIds: ["task-center", "collaboration-room"],
    capabilityIds: ["design", "project-control", "implementation", "digital"],
    workflowIds: ["investment-construction"]
  },
  "licensed-institution": {
    cockpitIds: ["collaboration-room", "decision-center"],
    capabilityIds: ["capital", "assets", "project-control"],
    workflowIds: ["financial-risk"]
  },
  "expert-advisor": {
    cockpitIds: ["decision-center", "ai-advisor"],
    capabilityIds: ["strategy", "assets", "capital"],
    workflowIds: ["project-decision", "financial-risk"]
  },
  management: {
    cockpitIds: ["management", "ai-advisor", "decision-center"],
    capabilityIds: ALL_CAPABILITIES,
    workflowIds: WORKFLOW_IDS
  },
  "platform-admin": {
    cockpitIds: ALL_COCKPITS,
    capabilityIds: ALL_CAPABILITIES,
    workflowIds: WORKFLOW_IDS
  }
};

const feature = (id: string, title: string, note: string, href?: string, permissionId?: CapabilityId): CockpitPreviewItem => ({
  id, kind: "feature", title, note, href, permissionId
});

const workflow = (id: WorkflowId, title: string, note: string): CockpitPreviewItem => ({
  id, kind: "workflow", title, note, permissionId: id
});

export const COCKPITS: CockpitSummary[] = [
  {
    id: "management", title: "管理层驾驶舱", eyebrow: "MANAGEMENT COCKPIT",
    description: "掌握经营、项目、风险与待决策事项", imageSrc: "/images/cockpits/management.png", href: "/cockpits/management",
    items: [
      feature("business-metrics", "核心经营指标", "客流、收入、现金流与资产表现", "/dashboard"),
      feature("project-progress", "重点项目进度", "里程碑、阻断点与交付状态", "/project-control"),
      feature("risk-alert", "风险预警", "经营、投资与实施风险集中查看", "/dashboard"),
      feature("decision-list", "待决策事项", "需要管理层确认的关键议题", "/decision-center"),
      feature("weekly-judgment", "本周经营判断", "经营变化、关键动作与管理建议", "/dashboard"),
      workflow("project-lifecycle", "项目全生命周期", "从战略到经营复盘的完整链路"),
      workflow("project-decision", "项目决策", "问题、证据、方案与正式决策"),
      workflow("financial-risk", "金融风控", "融资结构、风险识别与专业复核"),
      workflow("operating-growth", "经营增长", "活动、招商与营销协同增长")
    ]
  },
  {
    id: "ai-advisor", title: "AI 首席顾问", eyebrow: "AI CHIEF ADVISOR",
    description: "从项目资料中形成诊断、判断与建议", imageSrc: "/images/cockpits/ai-advisor.png", href: "/cockpits/ai-advisor",
    items: [
      feature("ai-chat", "AI 对话咨询", "围绕当前项目连续提问", "/ai"),
      feature("project-diagnosis", "项目问题诊断", "识别核心问题与原因", "/ai"),
      feature("industry-analysis", "行业数据研判", "结合数据与行业基准判断", "/ai"),
      feature("expert-opinion", "专家意见", "汇总专业审核与顾问建议", "/ai"),
      feature("report-generation", "报告生成", "形成判断、建议与汇报材料", "/ai"),
      workflow("project-decision", "项目决策", "问题、证据、方案与结论"),
      workflow("investment-construction", "投资建设", "方案、建设与交付协同"),
      workflow("financial-risk", "金融风控", "风险识别与专业机构复核"),
      workflow("operating-growth", "经营增长", "围绕经营问题形成行动建议")
    ]
  },
  {
    id: "decision-center", title: "决策议题中心", eyebrow: "DECISION AGENDA",
    description: "集中处理方案、证据、审批与决策记录", imageSrc: "/images/cockpits/decision-center.png", href: "/cockpits/decision-center",
    items: [
      feature("decision-agenda", "待决策议题", "汇总需要确认的关键问题", "/decision-center"),
      feature("scheme-comparison", "方案对比", "并列比较成本、收益与风险", "/decision-center"),
      feature("data-evidence", "数据证据", "查看结论引用的来源和版本", "/deliverables"),
      feature("expert-review", "专家审核", "查看专家意见与审核结论", "/decision-center"),
      feature("approval-opinion", "审批意见", "记录专家与管理层意见", "/decision-center"),
      feature("decision-record", "决策记录", "保留正式决策和后续结果", "/decision-center"),
      workflow("project-decision", "项目决策", "形成可追踪的正式决策"),
      workflow("financial-risk", "金融风控", "形成风控意见与整改要求")
    ]
  },
  {
    id: "task-center", title: "专业任务中心", eyebrow: "PROFESSIONAL TASKS",
    description: "进入专业 Agent，按工作步骤完成任务", imageSrc: "/images/cockpits/task-center.png", href: "/cockpits/task-center",
    items: [
      feature("event-agent", "活动策划 Agent", "首期开放 · 完整九步", "/event-agent", "event-agent"),
      feature("operations", "运营招商 Agent", "首期开放 · 完整九步", "/operations", "operations"),
      feature("marketing", "营销策划 Agent", "首期开放 · 完整九步", "/marketing", "marketing"),
      feature("strategy", "战略策划", "战略任务、定位与项目体系", "/strategy", "strategy"),
      feature("design", "专项设计", "建筑、景观与效果表达", "/design", "design"),
      feature("project-control", "项目管控", "进度、成本、质量与风险", "/project-control", "project-control"),
      feature("creative", "文创产品设计", "产品企划、矩阵与供应链", "/creative", "creative"),
      feature("digital", "数字系统", "数据档案、监测与报告", "/digital", "digital"),
      feature("implementation", "实施 PMO", "任务拆解、执行跟踪与验收", "/implementation", "implementation"),
      feature("assets", "资产盘活", "权属核验、经营评分与盘活方案", "/assets", "assets"),
      feature("capital", "资本化前置", "路径匹配、整改与机构复核", "/capital", "capital"),
      workflow("project-lifecycle", "项目全生命周期", "串联十一项专业模块"),
      workflow("investment-construction", "投资建设", "设计、管控、实施与数字留痕"),
      workflow("operating-growth", "经营增长", "活动、招商、营销与文创协同")
    ]
  },
  {
    id: "collaboration-room", title: "机构协作数据室", eyebrow: "COLLABORATION ROOM",
    description: "管理资料、成果、版本与多方协作", imageSrc: "/images/cockpits/collaboration-room.png", href: "/cockpits/collaboration-room",
    items: [
      feature("project-files", "项目资料库", "集中存放项目基础资料", "/institutions"),
      feature("contracts-reports", "合同与报告", "统一管理正式业务文件", "/institutions"),
      feature("drawings-results", "图纸与成果", "查看交付物及当前版本", "/deliverables"),
      feature("institution-collaboration", "机构协作", "按机构和事项开展协同", "/institutions"),
      feature("expert-delivery", "专家交付", "查看专业成果与审核意见", "/institutions"),
      feature("version-record", "版本记录", "追踪资料、成果和修改过程", "/deliverables"),
      feature("evidence-chain", "证据链", "保留引用、审核与修改记录", "/deliverables"),
      workflow("financial-risk", "金融风控", "机构尽调、复核与风险整改"),
    ]
  }
];

export function getRole(roleId: UserRoleId) {
  return ROLE_OPTIONS.find((role) => role.id === roleId);
}

export function getCockpit(cockpitId: string) {
  return COCKPITS.find((cockpit) => cockpit.id === cockpitId);
}

export function canUseCockpit(roleId: UserRoleId, cockpitId: CockpitId) {
  return ROLE_ACCESS[roleId].cockpitIds.includes(cockpitId);
}

export function canUseItem(roleId: UserRoleId, item: CockpitPreviewItem) {
  return canUseItemWithAccess(ROLE_ACCESS[roleId], item);
}

export function canUseCockpitWithAccess(access: RoleAccess, cockpitId: CockpitId) {
  return access.cockpitIds.includes(cockpitId);
}

export function canUseItemWithAccess(access: RoleAccess, item: CockpitPreviewItem) {
  if (!item.permissionId) return true;
  if (item.kind === "feature") return access.capabilityIds.includes(item.permissionId as CapabilityId);
  return access.workflowIds.includes(item.permissionId as WorkflowId);
}

export function getCockpitsForRole(roleId: UserRoleId): CockpitSummary[] {
  return COCKPITS.map((cockpit) => ({
    ...cockpit,
    available: canUseCockpit(roleId, cockpit.id),
    items: cockpit.items.map((item) => ({ ...item, available: canUseItem(roleId, item) }))
  }));
}
