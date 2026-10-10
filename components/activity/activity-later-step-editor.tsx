"use client";

import type { ActivityStep, JsonObject, JsonValue } from "@/lib/types/activity";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { decimalMultiply, decimalSum } from "@/lib/decimal-arithmetic";
import {
  SOURCE_LABELS,
  asObjectArray,
  asString,
  asStringArray,
  fieldClass,
  isoToLocalInput,
  labelClass,
  lines,
  localInputToIso
} from "@/components/activity/activity-ui";

interface LaterStepEditorProps {
  step: ActivityStep;
  output: JsonObject;
  disabled: boolean;
  onOutputChange: (output: JsonObject) => void;
}

const PHASE_LABELS = {
  warmup: "预热期",
  peak: "爆发期",
  followup: "尾声期"
} as const;

function EmptyResult({ locked }: { locked: boolean }) {
  return (
    <div className="border-t border-line px-5 py-12 text-center">
      <p className="text-sm font-medium text-ink">{locked ? "等待前序步骤确认" : "尚无生成结果"}</p>
      <p className="mt-1 text-xs text-moss">选择模型生成草稿后，可在这里逐项复核和修改。</p>
    </div>
  );
}

function numberValue(value: JsonValue | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function updateArrayItem(
  props: LaterStepEditorProps,
  key: string,
  items: JsonObject[],
  index: number,
  patch: JsonObject
) {
  props.onOutputChange({
    ...props.output,
    [key]: items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)
  });
}

function omitOrSet(item: JsonObject, key: string, value: JsonValue | undefined) {
  const next = { ...item };
  if (value === undefined || value === "") delete next[key];
  else next[key] = value;
  return next;
}

function DraftOnlyNotice() {
  return (
    <div className="border-t border-[#ead7bd] bg-[#fbf5eb] px-5 py-3 text-xs text-[#7f5a35]">
      本步骤只生成待确认草稿，不会自动审批、询价、发布或执行任何外部动作。
    </div>
  );
}

function BudgetStep(props: LaterStepEditorProps) {
  const items = asObjectArray(props.output.items);
  const savings = asObjectArray(props.output.savings);
  const resources = asObjectArray(props.output.resources);

  function updateBudgetItem(index: number, patch: JsonObject) {
    const nextItems = items.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      const next = { ...item, ...patch };
      next.subtotal = decimalMultiply(numberValue(next.quantity), numberValue(next.unitPrice));
      return next;
    });
    props.onOutputChange({
      ...props.output,
      items: nextItems,
      totalAmount: decimalSum(nextItems.map((item) => numberValue(item.subtotal)))
    });
  }

  return (
    <div className="divide-y divide-line">
      <section className="px-5 py-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">预算明细</h3>
            <p className="mt-1 text-[10px] text-moss">小计与预算合计由数量和单价自动计算。</p>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-moss">预算合计</div>
            <div className="mt-1 text-lg font-semibold text-ink">¥ {numberValue(props.output.totalAmount).toLocaleString("zh-CN")}</div>
          </div>
        </div>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {items.map((item, index) => (
            <div key={index} className="grid gap-3 py-4 md:grid-cols-2 xl:grid-cols-6">
              <label className={`${labelClass} xl:col-span-2`}>项目
                <input className={fieldClass} disabled={props.disabled} value={asString(item.item)} onChange={(event) => updateBudgetItem(index, { item: event.target.value })} />
              </label>
              <label className={labelClass}>分类
                <input className={fieldClass} disabled={props.disabled} value={asString(item.category)} onChange={(event) => updateBudgetItem(index, { category: event.target.value })} />
              </label>
              <label className={labelClass}>数量
                <input type="number" min="0.01" step="0.01" className={fieldClass} disabled={props.disabled} value={numberValue(item.quantity)} onChange={(event) => updateBudgetItem(index, { quantity: Number(event.target.value) })} />
              </label>
              <label className={labelClass}>单位
                <input className={fieldClass} disabled={props.disabled} value={asString(item.unit)} onChange={(event) => updateBudgetItem(index, { unit: event.target.value })} />
              </label>
              <label className={labelClass}>单价（元）
                <input type="number" min="0" step="0.01" className={fieldClass} disabled={props.disabled} value={numberValue(item.unitPrice)} onChange={(event) => updateBudgetItem(index, { unitPrice: Number(event.target.value) })} />
              </label>
              <label className={labelClass}>小计（元）
                <input className={fieldClass} disabled value={numberValue(item.subtotal).toFixed(2)} />
              </label>
              <label className={labelClass}>来源类型
                <select className={fieldClass} disabled={props.disabled} value={asString(item.sourceType)} onChange={(event) => updateBudgetItem(index, { sourceType: event.target.value })}>
                  {Object.entries(SOURCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className={`${labelClass} md:col-span-2 xl:col-span-4`}>测算依据
                <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(item.basis)} onChange={(event) => updateBudgetItem(index, { basis: event.target.value })} />
              </label>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">降本方案</h3>
        {savings.length ? (
          <div className="mt-4 divide-y divide-line border-y border-line">
            {savings.map((item, index) => (
              <div key={index} className="grid gap-3 py-4 lg:grid-cols-[minmax(0,1.4fr)_180px_minmax(0,1fr)]">
                <label className={labelClass}>措施
                  <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(item.action)} onChange={(event) => updateArrayItem(props, "savings", savings, index, { action: event.target.value })} />
                </label>
                <label className={labelClass}>预计节省（元）
                  <input type="number" min="0" step="0.01" className={fieldClass} disabled={props.disabled} value={numberValue(item.estimatedSaving)} onChange={(event) => updateArrayItem(props, "savings", savings, index, { estimatedSaving: Number(event.target.value) })} />
                </label>
                <label className={labelClass}>影响说明
                  <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(item.impact)} onChange={(event) => updateArrayItem(props, "savings", savings, index, { impact: event.target.value })} />
                </label>
              </div>
            ))}
          </div>
        ) : <p className="mt-3 text-xs text-moss">当前草稿没有降本方案。</p>}
      </section>

      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">资源清单</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {resources.map((item, index) => (
            <div key={index} className="grid gap-3 py-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_120px_120px_minmax(0,1.5fr)]">
              <label className={labelClass}>资源
                <input className={fieldClass} disabled={props.disabled} value={asString(item.name)} onChange={(event) => updateArrayItem(props, "resources", resources, index, { name: event.target.value })} />
              </label>
              <label className={labelClass}>数量
                <input type="number" min="0.01" step="0.01" className={fieldClass} disabled={props.disabled} value={numberValue(item.quantity)} onChange={(event) => updateArrayItem(props, "resources", resources, index, { quantity: Number(event.target.value) })} />
              </label>
              <label className={labelClass}>单位
                <input className={fieldClass} disabled={props.disabled} value={asString(item.unit)} onChange={(event) => updateArrayItem(props, "resources", resources, index, { unit: event.target.value })} />
              </label>
              <label className={labelClass}>用途
                <input className={fieldClass} disabled={props.disabled} value={asString(item.purpose)} onChange={(event) => updateArrayItem(props, "resources", resources, index, { purpose: event.target.value })} />
              </label>
            </div>
          ))}
        </div>
        <label className={`${labelClass} mt-5`}>预算说明
          <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asString(props.output.budgetNote)} onChange={(event) => props.onOutputChange({ ...props.output, budgetNote: event.target.value })} />
        </label>
      </section>
    </div>
  );
}

function PromotionStep(props: LaterStepEditorProps) {
  const phases = asObjectArray(props.output.phases);
  return (
    <div className="divide-y divide-line">
      <section className="px-5 py-5">
        <label className={labelClass}>传播策略
          <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(props.output.strategy)} onChange={(event) => props.onOutputChange({ ...props.output, strategy: event.target.value })} />
        </label>
      </section>
      {phases.map((phase, index) => {
        const phaseKey = asString(phase.phase) as keyof typeof PHASE_LABELS;
        return (
          <section key={phaseKey} className="px-5 py-5">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">{PHASE_LABELS[phaseKey]}</h3>
              <span className="rounded-full bg-mist px-2 py-1 text-[10px] text-pine">{phaseKey}</span>
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <label className={`${labelClass} lg:col-span-2`}>阶段目标
                <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(phase.objective)} onChange={(event) => updateArrayItem(props, "phases", phases, index, { objective: event.target.value })} />
              </label>
              <label className={labelClass}>渠道（每行一项）
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(phase.channels).join("\n")} onChange={(event) => updateArrayItem(props, "phases", phases, index, { channels: lines(event.target.value) })} />
              </label>
              <label className={labelClass}>素材清单（每行一项）
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(phase.materials).join("\n")} onChange={(event) => updateArrayItem(props, "phases", phases, index, { materials: lines(event.target.value) })} />
              </label>
              <label className={`${labelClass} lg:col-span-2`}>内容草稿（每行一项）
                <textarea className={`${fieldClass} min-h-36 resize-y`} disabled={props.disabled} value={asStringArray(phase.contentDrafts).join("\n")} onChange={(event) => updateArrayItem(props, "phases", phases, index, { contentDrafts: lines(event.target.value) })} />
              </label>
            </div>
          </section>
        );
      })}
      <DraftOnlyNotice />
    </div>
  );
}

function ExecutionPlanStep(props: LaterStepEditorProps) {
  const tasks = asObjectArray(props.output.tasks);
  return (
    <div className="divide-y divide-line">
      <section className="px-5 py-5">
        <label className={labelClass}>审批汇总草稿
          <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(props.output.approvalSummary)} onChange={(event) => props.onOutputChange({ ...props.output, approvalSummary: event.target.value })} />
        </label>
      </section>
      {tasks.map((task, index) => (
        <section key={index} className="px-5 py-5">
          <div className="text-[10px] font-medium text-moss">WBS 任务 {index + 1}</div>
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            <label className={labelClass}>任务名称
              <input className={fieldClass} disabled={props.disabled} value={asString(task.title)} onChange={(event) => updateArrayItem(props, "tasks", tasks, index, { title: event.target.value })} />
            </label>
            <label className={labelClass}>负责人
              <input className={fieldClass} disabled={props.disabled} value={asString(task.owner)} onChange={(event) => {
                const next = omitOrSet(task, "owner", event.target.value || undefined);
                updateArrayItem(props, "tasks", tasks, index, next);
              }} />
            </label>
            <label className={`${labelClass} lg:col-span-2`}>任务说明
              <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asString(task.description)} onChange={(event) => updateArrayItem(props, "tasks", tasks, index, { description: event.target.value })} />
            </label>
            <label className={labelClass}>截止时间
              <input type="datetime-local" className={fieldClass} disabled={props.disabled} value={typeof task.dueAt === "string" ? isoToLocalInput(task.dueAt) ?? "" : ""} onChange={(event) => {
                const next = omitOrSet(task, "dueAt", event.target.value ? localInputToIso(event.target.value) : undefined);
                updateArrayItem(props, "tasks", tasks, index, next);
              }} />
            </label>
            <label className={labelClass}>依赖项（每行一项）
              <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asStringArray(task.dependencies).join("\n")} onChange={(event) => updateArrayItem(props, "tasks", tasks, index, { dependencies: lines(event.target.value) })} />
            </label>
            <label className={labelClass}>审批文本草稿
              <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={asString(task.approvalDraft)} onChange={(event) => updateArrayItem(props, "tasks", tasks, index, { approvalDraft: event.target.value })} />
            </label>
            <label className={labelClass}>供应商询价草稿
              <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={asString(task.supplierInquiryDraft)} onChange={(event) => updateArrayItem(props, "tasks", tasks, index, { supplierInquiryDraft: event.target.value })} />
            </label>
          </div>
        </section>
      ))}
      <DraftOnlyNotice />
    </div>
  );
}

function ChannelBusinessStep(props: LaterStepEditorProps) {
  const channelActions = asObjectArray(props.output.channelActions);
  const packages = asObjectArray(props.output.sponsorshipPackages);
  return (
    <div className="divide-y divide-line">
      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">渠道联动</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {channelActions.map((item, index) => (
            <div key={index} className="grid gap-4 py-4 lg:grid-cols-2">
              <label className={labelClass}>渠道
                <input className={fieldClass} disabled={props.disabled} value={asString(item.channel)} onChange={(event) => updateArrayItem(props, "channelActions", channelActions, index, { channel: event.target.value })} />
              </label>
              <label className={labelClass}>目标
                <input className={fieldClass} disabled={props.disabled} value={asString(item.objective)} onChange={(event) => updateArrayItem(props, "channelActions", channelActions, index, { objective: event.target.value })} />
              </label>
              <label className={labelClass}>行动项（每行一项）
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(item.actions).join("\n")} onChange={(event) => updateArrayItem(props, "channelActions", channelActions, index, { actions: lines(event.target.value) })} />
              </label>
              <label className={labelClass}>收益模式
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(item.revenueModel)} onChange={(event) => updateArrayItem(props, "channelActions", channelActions, index, { revenueModel: event.target.value })} />
              </label>
              <label className={`${labelClass} lg:col-span-2`}>合作条款草稿
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(item.draftTerms)} onChange={(event) => updateArrayItem(props, "channelActions", channelActions, index, { draftTerms: event.target.value })} />
              </label>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">招商赞助包</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {packages.map((item, index) => (
            <div key={index} className="grid gap-4 py-4 lg:grid-cols-2">
              <label className={labelClass}>方案名称
                <input className={fieldClass} disabled={props.disabled} value={asString(item.name)} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { name: event.target.value })} />
              </label>
              <label className={labelClass}>目标合作方
                <input className={fieldClass} disabled={props.disabled} value={asString(item.targetPartner)} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { targetPartner: event.target.value })} />
              </label>
              <label className={labelClass}>权益（每行一项）
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(item.benefits).join("\n")} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { benefits: lines(event.target.value) })} />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className={labelClass}>参考价格（元）
                  <input type="number" min="0" step="0.01" className={fieldClass} disabled={props.disabled} value={numberValue(item.referencePrice)} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { referencePrice: Number(event.target.value) })} />
                </label>
                <label className={labelClass}>来源类型
                  <select className={fieldClass} disabled={props.disabled} value={asString(item.sourceType)} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { sourceType: event.target.value })}>
                    <option value="calculated">参考测算</option>
                    <option value="missing">待补充</option>
                  </select>
                </label>
              </div>
              <label className={`${labelClass} lg:col-span-2`}>定价依据
                <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asString(item.basis)} onChange={(event) => updateArrayItem(props, "sponsorshipPackages", packages, index, { basis: event.target.value })} />
              </label>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 px-5 py-5 lg:grid-cols-2">
        <label className={labelClass}>票务方案
          <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={asString(props.output.ticketingPlan)} onChange={(event) => props.onOutputChange({ ...props.output, ticketingPlan: event.target.value })} />
        </label>
        <label className={labelClass}>二次销售方案
          <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={asString(props.output.secondarySalesPlan)} onChange={(event) => props.onOutputChange({ ...props.output, secondarySalesPlan: event.target.value })} />
        </label>
      </section>
      <DraftOnlyNotice />
    </div>
  );
}

function MetricRows({
  props,
  outputKey,
  title,
  sourceLabel
}: {
  props: LaterStepEditorProps;
  outputKey: "forecastMetrics" | "actualMetrics";
  title: string;
  sourceLabel: string;
}) {
  const metrics = asObjectArray(props.output[outputKey]);
  const isActualMetrics = outputKey === "actualMetrics";

  function addActualMetric() {
    props.onOutputChange({
      ...props.output,
      actualMetrics: [
        ...metrics,
        {
          metric: "",
          value: 0,
          unit: "",
          sourceType: "actual",
          basis: ""
        }
      ]
    });
  }

  function deleteActualMetric(index: number) {
    props.onOutputChange({
      ...props.output,
      actualMetrics: metrics.filter((_, itemIndex) => itemIndex !== index)
    });
  }

  return (
    <section className="px-5 py-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {isActualMetrics ? <p className="mt-1 text-[10px] text-moss">活动执行后回填真实业务数据；已确认步骤需先重新打开才能修改。</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-mist px-2 py-1 text-[10px] text-pine">{sourceLabel}</span>
          {isActualMetrics ? (
            <Button type="button" variant="outline" size="sm" disabled={props.disabled} onClick={addActualMetric}>
              <Plus size={12} />
              添加实际指标
            </Button>
          ) : null}
        </div>
      </div>
      {metrics.length ? (
        <div className="mt-4 divide-y divide-line border-y border-line">
          {metrics.map((item, index) => (
            <div key={index} className={`grid gap-3 py-4 sm:grid-cols-2 ${isActualMetrics ? "lg:grid-cols-[minmax(0,1fr)_140px_120px_minmax(0,1.5fr)_auto]" : "lg:grid-cols-[minmax(0,1fr)_140px_120px_minmax(0,1.5fr)]"}`}>
              <label className={labelClass}>指标
                <input className={fieldClass} disabled={props.disabled} value={asString(item.metric)} onChange={(event) => updateArrayItem(props, outputKey, metrics, index, { metric: event.target.value })} />
              </label>
              <label className={labelClass}>数值
                <input type="number" step="any" className={fieldClass} disabled={props.disabled} value={numberValue(item.value)} onChange={(event) => updateArrayItem(props, outputKey, metrics, index, { value: Number(event.target.value) })} />
              </label>
              <label className={labelClass}>单位
                <input className={fieldClass} disabled={props.disabled} value={asString(item.unit)} onChange={(event) => updateArrayItem(props, outputKey, metrics, index, { unit: event.target.value })} />
              </label>
              <label className={labelClass}>依据
                <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(item.basis)} onChange={(event) => updateArrayItem(props, outputKey, metrics, index, { basis: event.target.value })} />
              </label>
              {isActualMetrics ? (
                <div className="flex items-end">
                  <Button type="button" variant="ghost" size="sm" disabled={props.disabled} onClick={() => deleteActualMetric(index)} title="删除实际指标">
                    <Trash2 size={14} />
                    删除
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : <p className="mt-3 text-xs text-moss">{isActualMetrics ? "暂无已回填的实际指标。" : "暂无预测指标。"}</p>}
    </section>
  );
}

function ReviewStep(props: LaterStepEditorProps) {
  return (
    <div className="divide-y divide-line">
      <MetricRows props={props} outputKey="forecastMetrics" title="活动前预测指标" sourceLabel="参考测算" />
      <MetricRows props={props} outputKey="actualMetrics" title="活动后实际指标" sourceLabel="实际数据" />
      <section className="grid gap-4 px-5 py-5 lg:grid-cols-2">
        <label className={labelClass}>待回填实际指标（每行一项）
          <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(props.output.missingActualMetrics).join("\n")} onChange={(event) => props.onOutputChange({ ...props.output, missingActualMetrics: lines(event.target.value) })} />
        </label>
        <label className={labelClass}>复盘结论（每行一项）
          <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(props.output.conclusions).join("\n")} onChange={(event) => props.onOutputChange({ ...props.output, conclusions: lines(event.target.value) })} />
        </label>
        <label className={`${labelClass} lg:col-span-2`}>改进建议（每行一项）
          <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asStringArray(props.output.improvements).join("\n")} onChange={(event) => props.onOutputChange({ ...props.output, improvements: lines(event.target.value) })} />
        </label>
      </section>
    </div>
  );
}

export function ActivityLaterStepEditor(props: LaterStepEditorProps) {
  if (!Object.keys(props.output).length) return <EmptyResult locked={props.step.status === "locked"} />;
  if (props.step.stepNo === 5) return <BudgetStep {...props} />;
  if (props.step.stepNo === 6) return <PromotionStep {...props} />;
  if (props.step.stepNo === 7) return <ExecutionPlanStep {...props} />;
  if (props.step.stepNo === 8) return <ChannelBusinessStep {...props} />;
  return <ReviewStep {...props} />;
}
