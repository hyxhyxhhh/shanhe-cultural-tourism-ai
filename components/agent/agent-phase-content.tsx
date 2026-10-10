"use client";

import { ArrowRight, Check, MapPin, Megaphone, WalletCards } from "lucide-react";
import type { InsightItem, ProfessionalAgentData, StatItem } from "@/lib/types/platform";

interface AgentPhaseContentProps {
  data: ProfessionalAgentData;
  phaseIndex: number;
  fields: Record<string, string>;
  onFieldChange: (label: string, value: string) => void;
}

function ItemGrid({ items, columns = 2 }: { items: InsightItem[]; columns?: 2 | 3 }) {
  return <div className={`grid gap-3 ${columns === 3 ? "md:grid-cols-2 xl:grid-cols-3" : "md:grid-cols-2"}`}>{items.map((item, index)=><div key={`${item.label}-${index}`} className="rounded-lg bg-mist p-4"><div className="flex items-start justify-between gap-3"><div className="text-[10px] text-moss">{item.label}</div>{item.icon && <span className="grid h-6 min-w-6 place-items-center rounded bg-white px-1 text-[9px] font-medium text-pine">{item.icon}</span>}</div>{item.value && <div className="mt-2 text-sm font-semibold leading-5">{item.value}</div>}{item.note && <div className="mt-1 text-[10px] leading-4 text-moss">{item.note}</div>}{item.status && <div className="mt-2 text-[10px] font-medium text-pine">{item.status}</div>}</div>)}</div>;
}

function ItemList({ items }: { items: InsightItem[] }) {
  return <div className="divide-y divide-line overflow-hidden rounded-lg border border-line">{items.map((item,index)=><div key={`${item.label}-${index}`} className="flex min-h-[62px] items-center gap-3 px-4 py-3"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-mist text-[10px] font-medium text-pine">{item.icon ?? index+1}</span><div className="min-w-0 flex-1"><div className="text-xs font-medium">{item.label}</div>{item.note && <div className="mt-1 text-[10px] text-moss">{item.note}</div>}</div>{item.value && <div className="text-xs font-semibold">{item.value}</div>}{item.status && <div className="min-w-20 text-right text-[10px] text-pine">{item.status}</div>}</div>)}</div>;
}

function MetricGrid({ items }: { items: StatItem[] }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{items.map((item)=><div key={item.label} className="rounded-lg border border-line bg-white p-5"><div className="text-[10px] text-moss">{item.label}</div><div className="mt-2 text-2xl font-semibold tracking-[-.03em]">{item.value}</div>{item.note && <div className="mt-2 text-[10px] text-pine">{item.note}</div>}</div>)}</div>;
}

function InputPhase({ data, fields, onFieldChange }: Omit<AgentPhaseContentProps,"phaseIndex">) {
  return <div className="max-w-2xl space-y-4">{data.fields.map((field)=><label key={field.label} className="block text-[11px] text-moss">{field.label}<textarea value={fields[field.label] ?? ""} onChange={(event)=>onFieldChange(field.label,event.target.value)} className="mt-2 min-h-[58px] w-full resize-none rounded-md border border-line bg-[#f8f9f7] px-4 py-3 text-xs leading-5 text-ink outline-none transition focus:border-moss"/></label>)}</div>;
}

const eventStory = [
  { label:"故事主线", value:"山城少年寻找失落火种", note:"串联五段沉浸式任务" },
  { label:"核心记忆点", value:"会呼吸的非遗山城", note:"夜景、演艺与互动统一表达" },
  { label:"目标停留", value:"3.2小时", note:"较现状提升0.8小时" },
  { label:"目标客单", value:"¥186", note:"门票、餐饮与文创组合" }
];

const eventContent = [
  { icon:"1", label:"迎火入城", value:"入口广场", status:"17:30—18:20" },
  { icon:"2", label:"古巷寻迹", value:"古城街巷", status:"18:20—19:20" },
  { icon:"3", label:"非遗会演", value:"中心戏台", status:"19:30—20:30" },
  { icon:"4", label:"龙舞巡游", value:"滨水动线", status:"20:30—21:30" },
  { icon:"5", label:"火种归山", value:"山门广场", status:"21:30—22:30" }
];

const eventMedia = [
  { icon:"文", label:"主题海报文案", value:"3版", status:"待品牌审核" },
  { icon:"视", label:"短视频脚本", value:"6条", status:"分镜已生成" },
  { icon:"微", label:"公众号推文", value:"1篇", status:"待发布" },
  { icon:"会", label:"短信/会员触达", value:"4组", status:"人群已圈选" },
  { icon:"广", label:"广告素材组合", value:"12套", status:"待预算审批" }
];

const eventChannels = [
  { icon:"私", label:"会员私域", value:"12,840人", status:"待审批" },
  { icon:"公", label:"公众号", value:"1篇", status:"待品牌审核" },
  { icon:"短", label:"短视频平台", value:"6条", status:"排期完成" },
  { icon:"广", label:"广告平台", value:"¥8万", status:"待预算审批" },
  { icon:"旅", label:"OTA/旅行社", value:"18家", status:"联动确认" },
  { icon:"现", label:"现场触点", value:"26处", status:"物料待制作" }
];

const eventResults: StatItem[] = [
  { label:"到访客流", value:"36,800", note:"目标达成 108%" },
  { label:"活动转化率", value:"18.6%", note:"较基线 +5.2pp" },
  { label:"活动期收入", value:"¥286万", note:"投入产出比 5.72" },
  { label:"传播触达", value:"1,840万", note:"有效互动 12.6万" }
];

function EventPhase({ data, phaseIndex, fields, onFieldChange }: AgentPhaseContentProps) {
  if (phaseIndex === 0) return <InputPhase data={data} fields={fields} onFieldChange={onFieldChange}/>;
  if (phaseIndex === 1) return <ItemGrid items={data.evidence}/>;
  if (phaseIndex === 2) return <div className="space-y-4"><div className="relative min-h-[190px] rounded-lg bg-[#604c3b] p-6 text-white"><div className="eyebrow text-[#e4c785]">AI RECOMMENDED CONCEPT · 专家待审核</div><h3 className="mt-4 text-2xl font-semibold">云山非遗奇遇夜</h3><p className="mt-2 max-w-3xl text-[11px] leading-5 text-white/75">以“山城少年寻找失落火种”为故事主线，将川江号子、铜梁龙舞、古城夜巷和数字光影组织为五段式沉浸任务。</p><button className="absolute right-5 top-1/2 -translate-y-1/2 rounded-md border border-white/25 px-3 py-2 text-[10px] hover:bg-white/10 max-md:static max-md:mt-5 max-md:translate-y-0">打开完整策划案 →</button></div><div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">{eventStory.map((item)=><div key={item.label} className="rounded-lg border border-line bg-white p-4"><div className="text-[10px] text-moss">{item.label}</div><div className="mt-2 text-sm font-semibold">{item.value}</div><div className="mt-1 text-[10px] text-moss">{item.note}</div></div>)}</div></div>;
  if (phaseIndex === 3) return <div className="space-y-4"><div className="flex items-center gap-2 text-xs text-moss"><MapPin size={14}/>内容模块同步映射空间、时段与人员</div><ItemList items={eventContent}/></div>;
  if (phaseIndex === 4) return <div className="space-y-4"><div className="flex items-center gap-2 text-xs text-moss"><Megaphone size={14}/>一套主题生成跨渠道内容资产</div><ItemList items={eventMedia}/></div>;
  if (phaseIndex === 5) return <div className="space-y-4"><div className="flex items-center gap-2 text-xs text-moss"><WalletCards size={14}/>预算、供应商与现场资源统一校验</div><ItemList items={data.outputs}/><div className="flex justify-end rounded-lg bg-mist p-4 text-xs"><span className="text-moss">预算合计</span><strong className="ml-6 text-base">¥50.0万</strong></div></div>;
  if (phaseIndex === 6) return <div className="space-y-4"><ItemList items={data.automations}/><div className="rounded-lg border border-[#eadac9] bg-[#fbf6f0] p-4 text-[11px] leading-5 text-[#815c46]">涉及供应商询价、会员触达、内容发布和广告投放的动作，必须由对应责任人审批后执行。</div></div>;
  if (phaseIndex === 7) return <ItemGrid items={eventChannels} columns={3}/>;
  return <div className="space-y-5"><MetricGrid items={eventResults}/><div className="rounded-lg bg-mist p-4 text-[11px] leading-5 text-moss"><strong className="text-ink">模型学习：</strong>亲子任务卡对停留时间贡献最高；短视频达人渠道带来客流，但会员召回渠道的消费转化更高。</div></div>;
}

function GenericPhase({ data, phaseIndex, fields, onFieldChange }: AgentPhaseContentProps) {
  if (phaseIndex === 0) return <InputPhase data={data} fields={fields} onFieldChange={onFieldChange}/>;
  if (phaseIndex === 1) return <ItemGrid items={data.evidence}/>;
  if (phaseIndex === 2) return <MetricGrid items={data.stats}/>;
  if (phaseIndex === 3 || phaseIndex === 4) return <ItemList items={data.outputs}/>;
  if (phaseIndex === 5) return <div className="space-y-4"><ItemGrid items={data.evidence}/><div className="rounded-lg bg-mist p-4 text-[11px] text-moss">当前阶段结果由统一数据和前序成果生成，真实业务规则由后端 Agent 接入。</div></div>;
  if (phaseIndex === 6 || phaseIndex === 7) return <ItemList items={data.automations}/>;
  return <div className="space-y-5"><MetricGrid items={data.stats}/><div className="rounded-lg bg-mist p-4 text-[11px] text-moss">本轮流程完成后，结果将回写当前客户空间并保留版本与证据链。</div></div>;
}

export function AgentPhaseContent(props: AgentPhaseContentProps) {
  return props.data.id === "event-planning" ? <EventPhase {...props}/> : <GenericPhase {...props}/>;
}

export function getPhaseSubtitle(data: ProfessionalAgentData, phaseIndex: number) {
  if (phaseIndex === 0) return "结构化输入决定后续数据、内容与审核规则";
  if (phaseIndex === 1) return "所有结论保留来源、时间和可信度";
  if (phaseIndex === data.phases.length - 1) return "汇总结果并沉淀下一轮可复用经验";
  return `完成${data.phases[phaseIndex]}并确认本阶段成果`;
}

export function CompletedHint({ onBack }: { onBack: () => void }) {
  return <button onClick={onBack} className="inline-flex items-center gap-1 text-[10px] font-medium text-pine hover:text-forest"><Check size={12}/>已完成，可返回修改<ArrowRight size={11}/></button>;
}
