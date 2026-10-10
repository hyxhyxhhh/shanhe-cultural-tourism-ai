import type { CockpitId } from "@/lib/types/access";

export interface DashboardMetric {
  label: string;
  value: string;
  unit: string;
  change: string;
  comparison: string;
  direction: "up" | "down" | "flat";
}

export interface DashboardTrend {
  title: string;
  primaryLabel: string;
  secondaryLabel: string;
  unit: string;
  points: { label: string; primary: number; secondary: number }[];
}

export interface DashboardSegment {
  label: string;
  value: number;
  color: string;
}

export interface DashboardProgress {
  name: string;
  stage: string;
  imageSrc: string;
  percent: number;
  targetDate: string;
  status: "进行中" | "待审核" | "有风险" | "已完成";
}

export interface DashboardRisk {
  title: string;
  severity: "高" | "中" | "低";
  impact: string;
  dueDate: string;
}

export interface CockpitDashboardData {
  period: string;
  metrics: DashboardMetric[];
  trend: DashboardTrend;
  distributionTitle: string;
  segments: DashboardSegment[];
  progress: DashboardProgress[];
  risks: DashboardRisk[];
}

// 以现有项目、决策议题和工作流名称组织的演示快照；尚未连接真实业务接口。
export const COCKPIT_DASHBOARDS: Record<CockpitId, CockpitDashboardData> = {
  management: {
    period: "2026 年 9 月 · 集团经营演示快照",
    metrics: [
      { label: "重点项目", value: "3", unit: "个", change: "+1", comparison: "较上月", direction: "up" },
      { label: "待决策事项", value: "1", unit: "项", change: "持平", comparison: "较上月", direction: "flat" },
      { label: "推进中工作流", value: "4", unit: "条", change: "+1", comparison: "较上月", direction: "up" },
      { label: "风险提示", value: "2", unit: "项", change: "-1", comparison: "较上月", direction: "down" }
    ],
    trend: { title: "项目与决策推进趋势", primaryLabel: "新增事项", secondaryLabel: "已处理事项", unit: "项", points: [
      { label: "第1周", primary: 5, secondary: 3 }, { label: "第2周", primary: 7, secondary: 5 },
      { label: "第3周", primary: 6, secondary: 6 }, { label: "第4周", primary: 8, secondary: 7 }
    ] },
    distributionTitle: "管理事项结构",
    segments: [
      { label: "经营增长", value: 4, color: "#5bb99d" },
      { label: "项目决策", value: 3, color: "#d9b76d" },
      { label: "金融风控", value: 2, color: "#83a8a1" }
    ],
    progress: [
      { name: "渝西文旅资产整合项目", stage: "资产归集与项目决策", imageSrc: "/images/cockpit-progress/management-1.webp", percent: 72, targetDate: "2026-10-15", status: "进行中" },
      { name: "云山核心景区增长项目", stage: "经营增长方案复核", imageSrc: "/images/cockpit-progress/management-2.webp", percent: 58, targetDate: "2026-10-28", status: "待审核" },
      { name: "古城商业街区更新项目", stage: "合作模型比较", imageSrc: "/images/cockpit-progress/management-3.webp", percent: 43, targetDate: "2026-11-12", status: "有风险" }
    ],
    risks: [
      { title: "古城街区合作模式尚待确认", severity: "高", impact: "可能影响招商与现金流测算", dueDate: "2026-09-28" },
      { title: "云山景区增长方案等待专业复核", severity: "中", impact: "可能推迟下一阶段执行", dueDate: "2026-10-05" }
    ]
  },
  "ai-advisor": {
    period: "2026 年 9 月 · 顾问工作流演示快照",
    metrics: [
      { label: "项目诊断", value: "3", unit: "项", change: "+1", comparison: "较上月", direction: "up" },
      { label: "待审核建议", value: "2", unit: "条", change: "+1", comparison: "较上月", direction: "up" },
      { label: "报告草稿", value: "5", unit: "份", change: "+2", comparison: "较上月", direction: "up" },
      { label: "已归档结论", value: "4", unit: "条", change: "+1", comparison: "较上月", direction: "up" }
    ],
    trend: { title: "诊断与建议形成趋势", primaryLabel: "发起诊断", secondaryLabel: "形成建议", unit: "项", points: [
      { label: "第1周", primary: 3, secondary: 2 }, { label: "第2周", primary: 4, secondary: 3 },
      { label: "第3周", primary: 5, secondary: 4 }, { label: "第4周", primary: 4, secondary: 3 }
    ] },
    distributionTitle: "顾问任务状态",
    segments: [
      { label: "诊断中", value: 3, color: "#5bb99d" },
      { label: "待专家审核", value: 2, color: "#d9b76d" },
      { label: "结论已归档", value: 4, color: "#83a8a1" }
    ],
    progress: [
      { name: "渝西文旅资产整合项目", stage: "资产盘活诊断", imageSrc: "/images/cockpit-progress/ai-advisor-1.webp", percent: 76, targetDate: "2026-10-08", status: "进行中" },
      { name: "云山核心景区增长项目", stage: "客流与二消分析", imageSrc: "/images/cockpit-progress/ai-advisor-2.webp", percent: 61, targetDate: "2026-10-18", status: "待审核" },
      { name: "古城商业街区更新项目", stage: "合作模式建议", imageSrc: "/images/cockpit-progress/ai-advisor-3.webp", percent: 48, targetDate: "2026-10-30", status: "有风险" }
    ],
    risks: [
      { title: "古城街区现金流依据待补充", severity: "高", impact: "影响合作模式建议的可靠性", dueDate: "2026-09-29" },
      { title: "云山景区同类项目基准待核验", severity: "中", impact: "可能延后专家审核", dueDate: "2026-10-03" }
    ]
  },
  "decision-center": {
    period: "2026 年 9 月 · 决策工作流演示快照",
    metrics: [
      { label: "在办议题", value: "3", unit: "项", change: "+1", comparison: "较上月", direction: "up" },
      { label: "待正式决策", value: "1", unit: "项", change: "持平", comparison: "较上月", direction: "flat" },
      { label: "待专家审核", value: "1", unit: "项", change: "持平", comparison: "较上月", direction: "flat" },
      { label: "阻断整改", value: "1", unit: "项", change: "-1", comparison: "较上月", direction: "down" }
    ],
    trend: { title: "议题新增与办结趋势", primaryLabel: "新增议题", secondaryLabel: "办结议题", unit: "项", points: [
      { label: "第1周", primary: 2, secondary: 1 }, { label: "第2周", primary: 3, secondary: 2 },
      { label: "第3周", primary: 2, secondary: 2 }, { label: "第4周", primary: 3, secondary: 2 }
    ] },
    distributionTitle: "议题状态分布",
    segments: [
      { label: "待正式决策", value: 1, color: "#5bb99d" },
      { label: "专家审核", value: 1, color: "#d9b76d" },
      { label: "阻断整改", value: 1, color: "#c98777" }
    ],
    progress: [
      { name: "酒店板块二期改造决策", stage: "经营预测、设计与成本比选", imageSrc: "/images/cockpit-progress/decision-center-1.webp", percent: 78, targetDate: "2026-10-06", status: "待审核" },
      { name: "古城商业街区合作模型", stage: "租赁与联营方案专家审核", imageSrc: "/images/cockpit-progress/decision-center-2.webp", percent: 62, targetDate: "2026-10-14", status: "进行中" },
      { name: "核心景区 REITs 储备评估", stage: "权属、手续与收益整改", imageSrc: "/images/cockpit-progress/decision-center-3.webp", percent: 39, targetDate: "2026-11-02", status: "有风险" }
    ],
    risks: [
      { title: "核心景区 REITs 储备评估受阻", severity: "高", impact: "权属与手续证据不完整，影响资本路径判断", dueDate: "2026-09-30" },
      { title: "古城街区方案仍待专家结论", severity: "中", impact: "可能影响合作模型审批", dueDate: "2026-10-08" }
    ]
  },
  "task-center": {
    period: "2026 年 9 月 · 专业任务演示快照",
    metrics: [
      { label: "专业模块", value: "11", unit: "个", change: "持平", comparison: "较上月", direction: "flat" },
      { label: "进行中任务", value: "9", unit: "项", change: "+2", comparison: "较上月", direction: "up" },
      { label: "待审核成果", value: "3", unit: "份", change: "+1", comparison: "较上月", direction: "up" },
      { label: "交付完成", value: "6", unit: "项", change: "+2", comparison: "较上月", direction: "up" }
    ],
    trend: { title: "专业任务推进趋势", primaryLabel: "新增任务", secondaryLabel: "完成任务", unit: "项", points: [
      { label: "第1周", primary: 5, secondary: 3 }, { label: "第2周", primary: 6, secondary: 5 },
      { label: "第3周", primary: 7, secondary: 6 }, { label: "第4周", primary: 5, secondary: 6 }
    ] },
    distributionTitle: "专业任务结构",
    segments: [
      { label: "投资建设", value: 6, color: "#5bb99d" },
      { label: "经营增长", value: 7, color: "#d9b76d" },
      { label: "项目全生命周期", value: 5, color: "#83a8a1" }
    ],
    progress: [
      { name: "云山景区活动与营销协同", stage: "活动策划 Agent · 执行排期", imageSrc: "/images/cockpit-progress/task-center-1.webp", percent: 82, targetDate: "2026-10-12", status: "进行中" },
      { name: "古城街区招商组合优化", stage: "运营招商 Agent · 专家审核", imageSrc: "/images/cockpit-progress/task-center-2.webp", percent: 65, targetDate: "2026-10-24", status: "待审核" },
      { name: "渝西资产实施 PMO", stage: "项目管控 · 里程碑核对", imageSrc: "/images/cockpit-progress/task-center-3.webp", percent: 51, targetDate: "2026-11-06", status: "有风险" }
    ],
    risks: [
      { title: "渝西资产实施里程碑存在偏差", severity: "高", impact: "可能影响后续成果验收", dueDate: "2026-10-01" },
      { title: "古城街区招商方案待确认", severity: "中", impact: "商户沟通尚不能进入下一阶段", dueDate: "2026-10-09" }
    ]
  },
  "collaboration-room": {
    period: "2026 年 9 月 · 机构协作演示快照",
    metrics: [
      { label: "成果文件", value: "6", unit: "份", change: "+2", comparison: "较上月", direction: "up" },
      { label: "待专业审核", value: "2", unit: "份", change: "+1", comparison: "较上月", direction: "up" },
      { label: "协同机构", value: "3", unit: "家", change: "持平", comparison: "较上月", direction: "flat" },
      { label: "版本更新", value: "4", unit: "次", change: "+1", comparison: "较上月", direction: "up" }
    ],
    trend: { title: "资料提交与审核趋势", primaryLabel: "提交资料", secondaryLabel: "审核完成", unit: "份", points: [
      { label: "第1周", primary: 3, secondary: 2 }, { label: "第2周", primary: 5, secondary: 3 },
      { label: "第3周", primary: 4, secondary: 4 }, { label: "第4周", primary: 6, secondary: 4 }
    ] },
    distributionTitle: "成果审核状态",
    segments: [
      { label: "证据链完整", value: 4, color: "#5bb99d" },
      { label: "待专业审核", value: 2, color: "#d9b76d" }
    ],
    progress: [
      { name: "一期资产归集及权属清单", stage: "项目资料库 · 版本核对", imageSrc: "/images/cockpit-progress/collaboration-room-1.webp", percent: 88, targetDate: "2026-10-04", status: "进行中" },
      { name: "资本化前置诊断报告", stage: "专家交付 · 专业审核", imageSrc: "/images/cockpit-progress/collaboration-room-2.webp", percent: 72, targetDate: "2026-10-16", status: "待审核" },
      { name: "持牌机构进场准备资料包", stage: "机构协作 · 证据补充", imageSrc: "/images/cockpit-progress/collaboration-room-3.webp", percent: 46, targetDate: "2026-10-29", status: "有风险" }
    ],
    risks: [
      { title: "机构进场资料包尚缺权属附件", severity: "高", impact: "影响机构尽调范围确认", dueDate: "2026-10-02" },
      { title: "资本化诊断报告等待专业审核", severity: "中", impact: "正式交付时间可能顺延", dueDate: "2026-10-10" }
    ]
  }
};
