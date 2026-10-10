export interface ProjectAIContent {
  description: string;
  heroTitle: string;
  heroDescription: string;
  emptyState: string;
  placeholder: string;
  quickActions: string[];
}

export interface Project {
  id: string;
  name: string;
  owner: string;
  status: string;
  updatedAt: string;
  ai: ProjectAIContent;
}

export const projects: Project[] = [
  {
    id: "sh-xi-001",
    name: "渝西文旅资产整合项目",
    owner: "政府平台公司",
    status: "示范空间",
    updatedAt: "2026-08-21",
    ai: {
      description: "连接统一指标、项目事实、行业模型、专业规则与专家审核",
      heroTitle: "从问题开始，而不是从报告开始",
      heroDescription: "把战略、资产、运营、数字治理或产融问题交给统一顾问入口。",
      emptyState: "请输入一个资产整合问题，开始与 AI 首席顾问对话",
      placeholder: "输入一个战略、资产、运营、数字治理或产融问题…",
      quickActions: ["区域文旅战略诊断", "资产归集与盘活", "运营PMC诊断", "现金流改善测算", "数据治理评估", "资本化前置诊断", "管理层决策简报"]
    }
  },
  {
    id: "yunshan-002",
    name: "云山核心景区增长项目",
    owner: "云山景区运营公司",
    status: "增长专项",
    updatedAt: "2026-09-02",
    ai: {
      description: "连接客流、票务、业态、营销与游客体验数据",
      heroTitle: "从客流增长开始，找到经营提升路径",
      heroDescription: "围绕游客结构、停留时长、二次消费和淡旺季波动形成增长建议。",
      emptyState: "请输入一个景区增长问题，开始与 AI 首席顾问对话",
      placeholder: "输入一个客流、产品、业态或营销增长问题…",
      quickActions: ["客流结构与峰谷诊断", "二次消费提升分析", "景区产品组合优化", "渠道投放效果评估", "游客动线与停留分析", "淡季增长方案", "经营增长决策简报"]
    }
  },
  {
    id: "gucheng-003",
    name: "古城商业街区更新项目",
    owner: "古城文旅运营公司",
    status: "更新专项",
    updatedAt: "2026-09-08",
    ai: {
      description: "连接街区资产、商户、客群、租约和更新实施数据",
      heroTitle: "从街区经营问题出发，重构业态与现金流",
      heroDescription: "围绕空间更新、招商组合、租赁策略与夜间消费形成实施建议。",
      emptyState: "请输入一个街区更新问题，开始与 AI 首席顾问对话",
      placeholder: "输入一个空间更新、招商、客群或现金流问题…",
      quickActions: ["街区客群与消费诊断", "租赁与联营模式比较", "业态组合优化", "低效空间盘活", "夜间消费场景策划", "更新投资测算", "街区更新决策简报"]
    }
  }
];

export function getProject(projectId: string): Project {
  return projects.find((project) => project.id === projectId) ?? projects[0]!;
}

export const projectApi = {
  async list(): Promise<Project[]> { return projects; },
  async get(id: string): Promise<Project | undefined> { return (await this.list()).find((project) => project.id === id); },
  async create(input: Pick<Project,"name"|"owner">): Promise<Project> {
    return { id:`project-${Date.now()}`, ...input, status:"待配置", updatedAt:new Date().toISOString(), ai:projects[0]!.ai };
  }
};
