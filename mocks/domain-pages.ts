import type { DomainPageData } from "@/lib/types/platform";

export const domainPages: Record<string, DomainPageData> = {
  design:{title:"专业设计",description:"连接策划目标、经营约束、投资条件与设计生产",eyebrow:"PROFESSIONAL DESIGN INTELLIGENCE",heroTitle:"从策划条件到空间方案，让专业设计成为经营决策的可视化推演",heroDescription:"建筑、景观、市政、室内、三维、渲染与影像能力共享同一项目条件。",sections:[
    {title:"十项设计能力",subtitle:"从概念到可交付成果",items:[{icon:"建",label:"建筑智能设计",value:"总图/单体/功能布局"},{icon:"景",label:"景观智能设计",value:"场地/动线/植物/节点"},{icon:"市",label:"市政专项设计",value:"道路/管网/照明/标识"},{icon:"室",label:"室内空间设计",value:"业态/平面/材质/软装"},{icon:"3D",label:"三维智能设计",value:"体块/场景/BIM轻模型"},{icon:"绘",label:"手绘创作",value:"草图/概念/风格探索"},{icon:"染",label:"模型渲染",value:"材质/光照/环境/镜头"},{icon:"改",label:"照片改造",value:"建筑立面/街区/室内焕新"},{icon:"优",label:"效果图优化",value:"清晰度/材质/氛围/细节"},{icon:"影",label:"图生视频",value:"运镜/人流/昼夜/季节"}]},
    {title:"设计任务编排",subtitle:"策划指标、经营约束、场地资料和设计规范统一输入",action:"新建设计任务",items:[{label:"游客中心功能与立面焕新",value:"建筑+室内+景观",status:"方案比选 · 8/24"},{label:"古街夜游照明与导视系统",value:"景观+市政+效果图",status:"专家审核 · 8/27"},{label:"山地度假酒店公共空间",value:"室内+三维+渲染",status:"模型生成 · 9/02"}]},
    {title:"经营约束校验",subtitle:"不是只追求视觉效果",items:[{label:"投资限额",value:"¥3,600万",status:"符合"},{label:"可经营面积",value:"≥68%",status:"需优化"},{label:"游客峰值承载",value:"3,200人/h",status:"符合"},{label:"运营维护成本",value:"≤180万/年",status:"测算中"}]}
  ]},
  "project-control":{title:"项目管控",description:"面向业主、EPC和施工单位的全过程项目经营管理",eyebrow:"PROJECT CONTROL",heroTitle:"从投资决策到竣工运营，把项目进度、成本、质量与现金流放在同一条证据链上",heroDescription:"按角色提供投资、合规、设计、招采、施工、交付与运营衔接能力。",sections:[
    {title:"文旅业主 / 城投建设方",subtitle:"投资、合规与交付 · 当前入口能力",items:[{label:"前期报批与投资决策",status:"正常"},{label:"概预算与合约规划",status:"关注"},{label:"设计/招采/合同统筹",status:"预警"},{label:"进度质量安全穿透",status:"正常"},{label:"竣工移交与运营衔接",status:"关注"}]},
    {title:"项目健康度",subtitle:"AI预测与负责人确认结合",items:[{label:"投资与成本",value:"76",status:"概算内"},{label:"总控进度",value:"63",status:"关键路径延迟"},{label:"合同与变更",value:"71",status:"签证待确认"},{label:"质量与安全",value:"88",status:"总体稳定"},{label:"资金与现金流",value:"59",status:"回款偏慢"}]},
    {title:"全过程能力模块",items:[{label:"概预算/投资控制",value:"估算·概算·预算·五算对比"},{label:"设计与图纸",value:"任务·会审·BIM·设计检查"},{label:"招采与合同",value:"合约规划·招投标·合同履约"},{label:"进度与现场",value:"WBS·里程碑·挣值·施工日志"},{label:"变更与签证",value:"问题·洽商·签证·设计变更"},{label:"质量与安全",value:"检查·整改·验收·风险预警"},{label:"成本与资金",value:"核算·计量·支付·现金流"},{label:"档案与看板",value:"全过程归档·多项目驾驶舱"}]}
  ]},
  creative:{title:"文创暨工业设计",description:"让文化资源形成可验证、可量产和可持续销售的产品",eyebrow:"CULTURAL & INDUSTRIAL DESIGN",heroTitle:"把文化资源变成可验证、可量产、可持续销售的产品资产",heroDescription:"区域文化、客群需求、渠道数据和供应链能力共同驱动产品定义。",sections:[
    {title:"文创产品机会矩阵",subtitle:"区域文化热度 × 客群需求 × 渠道数据 × 供应链能力",action:"发起产品企划",items:[{icon:"◉",label:"石刻艺术数字衍生系列",value:"年轻客群 / 礼赠",status:"88 · 概念验证"},{icon:"◉",label:"山水城市出行用品",value:"都市游客 / 零售",status:"81 · 工业设计"},{icon:"◉",label:"非遗家居生活系列",value:"家庭客群 / 电商",status:"76 · 供应链匹配"},{icon:"◉",label:"研学教育模块化教具",value:"学校 / B端",status:"72 · 小批量测试"}]},
    {title:"设计到商业验证",subtitle:"不止产出效果图，持续追踪经营结果",items:[{label:"文化转译与IP规范",value:"12套",status:"完成"},{label:"产品定义与CMF设计",value:"8款",status:"进行中"},{label:"打样与成本工程",value:"6款",status:"进行中"},{label:"渠道测试与复购验证",value:"3渠道",status:"待启动"}]},
    {title:"全链路能力",items:[{label:"文化与市场情报",value:"资源库 · 游客偏好 · 爆品价格带"},{label:"工业设计能力",value:"造型 · 工艺 · CMF · 成本工程"},{label:"供应链协同",value:"厂商 · 打样 · 质检 · 版权"},{label:"经营验证",value:"渠道测试 · 毛利 · 周转 · 复购"}]}
  ]},
  "data-hub":{title:"数据产品中台",description:"统一数据连接、业务对象、质量、血缘与授权",eyebrow:"TRUSTED DATA PRODUCTS",heroTitle:"所有策划、设计和经营判断，先回答“数据从哪里来、口径是什么、能否追溯”",heroDescription:"连接企业经营、游客交易、区域市场、建设项目和资本规则数据。",sections:[
    {title:"数据源与授权状态",subtitle:"采集范围、授权用途、质量和责任人统一治理",action:"管理连接",items:[{label:"企业经营数据",value:"ERP·财务·合同·OA",status:"92% · 已连接"},{label:"游客与交易数据",value:"票务·PMS·CRM·会员",status:"86% · 已连接"},{label:"区域市场数据",value:"客流·OTA·舆情·消费",status:"74% · 授权核验"},{label:"项目建设数据",value:"进度·成本·BIM·GIS",status:"81% · 已连接"},{label:"资本规则与证据",value:"政策·监管·机构清单",status:"96% · 持续更新"},{label:"行业标杆数据库",value:"同区域·同类型·同规模",status:"68% · 样本扩充"}]},
    {title:"统一业务对象",subtitle:"一个对象一个ID，跨系统保持同一语义",action:"打开Ontology",items:[{label:"资产",value:"SH-AST",status:"126"},{label:"项目",value:"SH-PRJ",status:"48"},{label:"空间",value:"SH-SPC",status:"286"},{label:"产品",value:"SH-PDT",status:"342"},{label:"客群",value:"SH-AUD",status:"32"},{label:"合同",value:"SH-CTR",status:"1,284"},{label:"商户",value:"SH-MER",status:"186"},{label:"现金流",value:"SH-CFL",status:"4,862"}]},
    {title:"治理质量",items:[{label:"数据质量",value:"完整性86% · 及时性82% · 一致性78%"},{label:"数据血缘",value:"268项指标 · 2,846份证据 · 12条异常"},{label:"安全与授权",value:"46个敏感字段 · 28条脱敏规则"},{label:"行业基准",value:"168个标杆 · 36,420项样本"}]}
  ]},
  metrics:{title:"指标语义中心",description:"统一集团经营、建设与资本化指标口径",eyebrow:"METRIC SEMANTICS",heroTitle:"一个指标一个口径，一个数字一条血缘，一个结论一组证据",heroDescription:"公式、来源、周期、负责人和质量等级在同一指标字典中维护。",sections:[
    {title:"集团统一指标字典",action:"新建指标",items:[{label:"游客综合收入",value:"门票+二消+住宿+商业",status:"票务/PMS/ERP · A级"},{label:"获客成本CAC",value:"营销费用/新增付费游客",status:"投放/CRM/交易 · B级"},{label:"可经营现金流",value:"经营净流入-维持性投入",status:"财务/合同/项目 · B级"},{label:"资产权属清晰率",value:"权属完整资产/全部资产",status:"资产台账/权证 · A级"},{label:"项目投资偏差率",value:"(预计完工成本-目标成本)/目标成本",status:"项目管控/ERP · B级"},{label:"资本化整改完成率",value:"已验证整改项/全部整改项",status:"任务/证据/机构意见 · A级"}]},
    {title:"指标域",items:[{label:"经营指标域",value:"客流与转化46项 · 产品和商户38项 · 收入成本52项"},{label:"建设指标域",value:"投资成本28项 · 进度质量36项 · 设计变更18项"},{label:"资本化指标域",value:"资产权属14项 · 治理规范20项 · 现金流16项"}]}
  ]},
  digital:{title:"数字治理",description:"把经营事实治理为可用、可追溯、可审计的数据资产",eyebrow:"DIGITAL GOVERNANCE",heroTitle:"数字化治理不是大屏，而是把经营事实变成决策、任务和审计证据",heroDescription:"用统一语义和项目数字资产底座连接跨系统经营事实。",sections:[
    {title:"文旅产业 Ontology",subtitle:"统一资源、空间、资产、项目、产品、客群、合同和现金流关系",items:[{label:"实体类型",value:"126"},{label:"关系类型",value:"286"},{label:"映射实体",value:"18,462"}]},
    {title:"项目数字资产底座",subtitle:"保留原始证据与版本历史",items:[{label:"资产档案",value:"126"},{label:"经营指标",value:"48"},{label:"证据文件",value:"2,846"}]},
    {title:"治理运行",items:[{label:"接入系统",value:"财务ERP · 票务/PMS · 合同与OA"},{label:"数据问题",value:"三套收入科目待映射 · 两家公司数据缺失"},{label:"治理产出",value:"统一指标字典 · 资产现金流映射 · 可审计数据包"}]}
  ]},
  governance:{title:"合规、权限与审计",description:"客户、项目、角色与字段四级权限控制",eyebrow:"GOVERNANCE & AUDIT",heroTitle:"明确数据控制、AI边界、专业责任与全程审计",heroDescription:"高风险决策强制人工审批，依法需资质的判断转交持牌机构。",sections:[
    {title:"数据权限矩阵",action:"配置权限",items:[{label:"政府决策层",value:"战略/投资/绩效",status:"汇总视图"},{label:"集团经营层",value:"资产/经营/项目",status:"全量业务"},{label:"项目执行组",value:"本项目任务与数据",status:"项目范围"},{label:"外部专业机构",value:"授权数据室",status:"限时只读"},{label:"山河顾问团队",value:"约定服务范围",status:"全程留痕"}]},
    {title:"AI与专业风险控制",items:[{label:"投资、融资与证券路径",value:"模型计算+专家审核",status:"高风险"},{label:"法律、审计、保荐结论",value:"转交持牌机构",status:"禁止AI出具"},{label:"经营诊断与改进建议",value:"引用数据+负责人确认",status:"中风险"},{label:"摘要、抽取与格式转换",value:"自动校验后执行",status:"低风险"}]},
    {title:"治理保障",items:[{label:"审计留痕",value:"模型版本 · 数据来源 · 人工修改 · 审批记录"},{label:"客户隔离",value:"独立空间 · 行列权限 · 文件水印"},{label:"合规表达",value:"明确前置顾问属性 · 持牌业务清晰转交"}]}
  ]},
  architecture:{title:"平台目标架构",description:"统一数据、决策、任务、经营结果与资本化证据",eyebrow:"TARGET ARCHITECTURE",heroTitle:"数据驱动的文旅产业决策操作系统",heroDescription:"十大能力域共享统一ID、指标语义、行业基准和证据链。",sections:[
    {title:"01 · 经营增长闭环",subtitle:"数据 → 策划 → 产品与招商 → 营销 → 收入 → 复盘",items:[{label:"可信经营事实",value:"客流、交易、渠道、商户和竞品"},{label:"专业研判",value:"活动、招商、营销增长协同"},{label:"经营验证",value:"收入与成本结果持续回写"}]},
    {title:"02 · 资产资本闭环",subtitle:"资产 → 运营 → 现金流 → 治理 → 工具适配 → 机构进场",items:[{label:"资产治理",value:"权属、经营、财务和合同统一"},{label:"整改证据",value:"每项整改沉淀可审计证据"},{label:"机构协同",value:"不替代持牌机构专业判断"}]},
    {title:"03 · 投资建设闭环",subtitle:"经营目标 → 专业设计 → 投资管控 → 建成交付 → 运营验证",items:[{label:"经营条件",value:"目标、客群、产品与投资约束"},{label:"建设交付",value:"设计、招采、施工与验收"},{label:"运营衔接",value:"避免设计建设与经营脱节"}]}
  ]}
};
