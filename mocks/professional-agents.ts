import type { ProfessionalAgentData } from "@/lib/types/platform";

const phases: Record<string, string[]> = {
  operations: ["任务输入", "经营诊断", "业态组合", "品牌匹配", "条件测算", "招商触达", "谈判审批", "落位开业", "经营复盘"],
  strategy: ["战略任务", "数据取证", "问题诊断", "定位生成", "项目体系", "商业模式", "投资时序", "决策审批", "年度校准"],
  assets: ["资产导入", "文件识别", "统一ID", "权属核验", "经营评分", "盘活匹配", "方案测算", "审批实施", "价值复盘"],
  marketing: ["增长目标", "客群分层", "机会识别", "战役设计", "内容生产", "预算分配", "审批投放", "转化监测", "模型复盘"],
  implementation: ["读取方案", "任务拆解", "责任确认", "计划排程", "执行跟踪", "风险升级", "证据验收", "结果验证", "经验沉淀"],
  capital: ["路径任务", "资料归集", "条件匹配", "差距诊断", "现金流测算", "整改编排", "专业审核", "机构进场", "持续监测"]
};

const commonAutomations = (items: string[]) => items.map((label, index) => ({
  icon: index < 2 ? "AUTO" : "HITL", label, status: index < 2 ? "运行中" : "需审批"
}));

export const professionalAgents: Record<string, ProfessionalAgentData> = {
  operations: {
    id: "operations", title: "运营招商Agent", description: "从客群与经营缺口出发，自动完成业态规划、品牌匹配、条件测算、招商触达与开业复盘", target: "运营目标、空间条件、财务约束与核心客群共同驱动招商决策。", version: "V12", phases: phases.operations,
    fields: [{label:"招商目标",value:"12个月新增22个品牌，出租率提升至92%"},{label:"项目范围",value:"古城街区一期 · 18,600㎡"},{label:"经营约束",value:"年保底租金≥1,850万，主力店面积≤25%"},{label:"核心客群",value:"亲子家庭、年轻情侣、周边度假客群"}],
    stats:[{label:"招商机会",value:"22"},{label:"品牌线索",value:"286"},{label:"意向转化",value:"18.6%"},{label:"预计租金",value:"¥2,160万"}],
    evidence:[{label:"客流热区",value:"东入口晚间客流+32%"},{label:"业态缺口",value:"亲子体验/地方餐饮"},{label:"空铺风险",value:"9间连续空置>120天"},{label:"品牌线索",value:"286个候选品牌"}],
    outputs:[{label:"业态组合与铺位规划",status:"已生成"},{label:"品牌目标池与匹配评分",status:"已生成"},{label:"租赁/联营条件测算",status:"生成中"},{label:"招商手册与邀约内容",status:"生成中"}],
    automations: commonAutomations(["新增品牌自动评分","审批后批量发送邀约","洽谈纪要自动生成","开业后坪效持续复盘"])
  },
  strategy: {
    id:"strategy",title:"战略策划Agent",description:"从区域机会与经营事实出发，形成战略判断、业务组合、项目体系与实施路线图",target:"区域市场、资源结构、政策机会和经营数据共同校验战略方向。",version:"V18",phases:phases.strategy,
    fields:[{label:"战略目标",value:"由建设平台转型为区域文旅资产运营商"},{label:"空间与周期",value:"渝西四区县 · 2026—2030"},{label:"投资约束",value:"政府投资控制在18亿元以内"},{label:"经营目标",value:"2030年经营收入达到12亿元"}],
    stats:[{label:"战略议题",value:"12"},{label:"储备项目",value:"68"},{label:"优先项目",value:"16"},{label:"数据证据",value:"1,286"}],
    evidence:[{label:"区域市场",value:"周末短途增长21%"},{label:"资源结构",value:"核心资源分散在4个主体"},{label:"竞品差距",value:"夜间产品和度假住宿不足"},{label:"政策机会",value:"3类专项资金适配"}],
    outputs:[{label:"战略问题树与核心判断",status:"已生成"},{label:"总体定位与业务组合",status:"已生成"},{label:"项目库及投资优先级",status:"生成中"},{label:"五年实施与经营路线图",status:"生成中"}],
    automations:commonAutomations(["政策与竞品每日扫描","项目库自动评分更新","方案自动拆解专项任务","年度指标触发战略校准"])
  },
  assets: {
    id:"assets",title:"资产盘活Agent",description:"统一识别资产、权属、经营效率和现金流，形成归集、托管、招商与盘活方案",target:"资产事实、权属边界和经营数据共同决定盘活路径。",version:"V26",phases:phases.assets,
    fields:[{label:"资产范围",value:"集团126项文旅及配套资产"},{label:"盘活目标",value:"三年新增经营现金流1.2亿元"},{label:"核心约束",value:"核心景区经营权不得转让"},{label:"数据周期",value:"最近36个月经营和财务数据"}],
    stats:[{label:"资产数量",value:"126"},{label:"权属清晰率",value:"86%"},{label:"盘活机会",value:"23"},{label:"现金流潜力",value:"¥1.2亿"}],
    evidence:[{label:"资产规模",value:"账面价值42.8亿元"},{label:"低效资产",value:"23项/6.4亿元"},{label:"权属缺口",value:"18项待完善"},{label:"现金流资产",value:"64项持续经营"}],
    outputs:[{label:"集团资产一张图",status:"已生成"},{label:"低效及闲置资产清单",status:"已生成"},{label:"归集/托管/招商盘活方案",status:"生成中"},{label:"现金流改善与资产池",status:"生成中"}],
    automations:commonAutomations(["权证合同OCR分类","权属缺口自动提醒","资产效率月度重算","盘活结果回写估值模型"])
  },
  marketing: {
    id:"marketing",title:"营销增长Agent",description:"从客群、内容和渠道数据出发，生成增长战役、内容资产、预算分配与转化复盘",target:"会员、交易、热点和渠道效率共同驱动持续增长。",version:"V16",phases:phases.marketing,
    fields:[{label:"增长目标",value:"全年客流+15%，二消收入+20%"},{label:"预算规则",value:"年度1,200万元，单次调整≤8万元"},{label:"产品范围",value:"核心景区+酒店+古城夜游"},{label:"目标客群",value:"成渝亲子、年轻情侣、银发研学"}],
    stats:[{label:"增长战役",value:"12"},{label:"目标触达",value:"3,600万"},{label:"会员召回",value:"18万"},{label:"预测ROI",value:"4.8"}],
    evidence:[{label:"会员复购",value:"当前仅12.8%"},{label:"渠道效率",value:"私域ROI最高"},{label:"内容趋势",value:"非遗夜游热度+42%"},{label:"流失客群",value:"18万会员待召回"}],
    outputs:[{label:"年度营销日历",status:"已生成"},{label:"月度增长战役",status:"已生成"},{label:"跨渠道内容资产",status:"生成中"},{label:"预算分配与转化预测",status:"生成中"}],
    automations:commonAutomations(["热点和舆情持续扫描","图文视频批量生成","审批后创建投放任务","每日归因并调整建议"])
  },
  implementation: {
    id:"implementation",title:"实施PMO Agent",description:"把专业方案拆为责任、预算、计划、风险与证据，持续验证经营结果",target:"所有方案必须形成可执行任务、责任矩阵、里程碑和验收证据。",version:"V12",phases:phases.implementation,
    fields:[{label:"实施范围",value:"战略、资产、运营、数字和产融共86项举措"},{label:"实施周期",value:"2026.08—2027.07"},{label:"升级规则",value:"逾期3天提醒，7天升级分管领导"},{label:"验收规则",value:"任务完成必须同时提交成果和指标证据"}],
    stats:[{label:"执行任务",value:"86"},{label:"完成率",value:"48.8%"},{label:"待审批",value:"12"},{label:"证据文件",value:"286"}],
    evidence:[{label:"全部举措",value:"86项"},{label:"关键路径",value:"18项"},{label:"逾期风险",value:"9项"},{label:"经营增量",value:"已验证2,840万元"}],
    outputs:[{label:"一体化实施计划",status:"已生成"},{label:"责任矩阵与里程碑",status:"已生成"},{label:"周报/月报及决策议题",status:"生成中"},{label:"经营结果验证报告",status:"生成中"}],
    automations:commonAutomations(["方案自动拆解任务","逾期自动催办升级","完成证据自动归档","指标达成自动复盘"])
  },
  capital: {
    id:"capital",title:"资本化前置Agent",description:"从资产、现金流、治理和资料出发研究工具适配，形成整改清单与机构进场包",target:"不预设发行工具，不替代持牌机构的专业判断。",version:"V08",phases:phases.capital,
    fields:[{label:"研究路径",value:"IPO前置、REITs、ABS、项目融资和政策资金"},{label:"主体范围",value:"集团本部及8家项目公司"},{label:"基本原则",value:"先改善经营与治理，不预设发行工具"},{label:"数据范围",value:"财务3年、经营36个月、项目全周期"}],
    stats:[{label:"适配项目",value:"9"},{label:"整改事项",value:"42"},{label:"资料完整度",value:"72%"},{label:"准备度",value:"64"}],
    evidence:[{label:"资产权属",value:"准备度78"},{label:"现金流质量",value:"准备度71"},{label:"数字治理",value:"准备度58"},{label:"机构进场",value:"准备度52"}],
    outputs:[{label:"五类工具适配矩阵",status:"已生成"},{label:"资本化差距与整改清单",status:"已生成"},{label:"现金流资产池测算",status:"生成中"},{label:"持牌机构分角色进场包",status:"生成中"}],
    automations:commonAutomations(["资料分类与缺口提醒","准备度按月自动更新","整改任务自动追踪","审批后组装机构数据室"])
  }
};
