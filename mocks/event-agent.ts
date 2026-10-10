import type { ProfessionalAgentData } from "@/lib/types/platform";

export const eventAgent: ProfessionalAgentData = {
  id:"event-planning",title:"活动策划Agent",description:"从目标和数据研判出发，自动生成创意、预算、内容、任务并完成经营复盘",target:"从一句活动目标，到执行任务与经营复盘",version:"云山非遗奇遇夜 · V08",phases:["活动简报","数据研判","主题故事","内容空间","传播素材","预算资源","审批执行","渠道联动","效果复盘"],
  fields:[{label:"活动目标",value:"暑期夜间客流提升20%，二消收入提升15%"},{label:"地点",value:"云山核心景区 · 古城街区"},{label:"时间",value:"2026.08.22—08.24 · 17:30—22:30"},{label:"预算",value:"总额 ¥50万 · 投放上限 ¥8万"},{label:"核心客群",value:"重庆主城亲子家庭、年轻情侣、周边自驾"}],
  stats:[{label:"当前方案完整度",value:"70%"}],
  evidence:[{label:"历史活动",value:"12场 · 夜游类转化最高"},{label:"区域客流",value:"+18.6% · 周末亲子客群上升"},{label:"天气",value:"24—31℃ · 晚间阵雨概率30%"},{label:"节假日",value:"暑期周末 · 停留时间预计+0.8h"},{label:"热点趋势",value:"非遗夜游 · 近30日热度+42%"}],
  outputs:[{label:"内容与演艺",value:"¥18.6万",status:"3家待询价"},{label:"场景搭建",value:"¥12.4万",status:"方案已生成"},{label:"传播投放",value:"¥8.0万",status:"待审批"},{label:"人员与保障",value:"¥6.8万",status:"排班完成"},{label:"机动费用",value:"¥4.2万",status:"预算锁定"}],
  automations:[{icon:"供",label:"供应商询价",value:"3家",status:"审批后发送"},{icon:"任",label:"项目任务",value:"28项",status:"已创建"},{icon:"短",label:"会员短信",value:"12,840人",status:"待审批"},{icon:"公",label:"公众号",value:"1篇",status:"待品牌审核"},{icon:"广",label:"广告平台",value:"¥8万",status:"待预算审批"},{icon:"人",label:"现场排班",value:"86人次",status:"已确认"}]
};
