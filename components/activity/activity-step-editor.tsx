"use client";

import { ExternalLink, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { decimalSum } from "@/lib/decimal-arithmetic";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import type { ResearchEvidenceSelection, ResearchGenerationProgress, ResearchScope } from "@/lib/types/activity-agent";
import type {
  Activity,
  ActivityBriefInput,
  ActivityStep,
  JsonObject,
  JsonValue
} from "@/lib/types/activity";
import {
  SOURCE_LABELS,
  asObject,
  asObjectArray,
  asString,
  asStringArray,
  fieldClass,
  labelClass,
  lines,
  readableError
} from "@/components/activity/activity-ui";
import { ActivityLaterStepEditor } from "@/components/activity/activity-later-step-editor";

interface ActivityStepEditorProps {
  activity: Activity;
  step: ActivityStep;
  brief: ActivityBriefInput;
  input: JsonObject;
  output: JsonObject;
  disabled: boolean;
  onBriefChange: (brief: ActivityBriefInput) => void;
  onInputChange: (input: JsonObject) => void;
  onOutputChange: (output: JsonObject) => void;
  onSearchToggle: (enabled: boolean) => void;
  researchQuery: string;
  researchScopes: ResearchScope[];
  researchRunning: boolean;
  researchSelection: ResearchEvidenceSelection | null;
  researchSelectionError: string | null;
  researchProgress: ResearchGenerationProgress | null;
  researchProgressError: string | null;
  onResearchQueryChange: (query: string) => void;
  onResearchScopesChange: (scopes: ResearchScope[]) => void;
  onResearchRun: () => void;
  onPlanItemOpen: (eventId: string) => void;
  canOpenPlanItem: boolean;
}

const RESEARCH_SCOPE_OPTIONS: Array<{ value: ResearchScope; label: string }> = [
  { value: "weather", label: "天气与气候" },
  { value: "holiday", label: "节假日与客流" },
  { value: "similar_events", label: "同类活动" },
  { value: "public_trend", label: "公共趋势" }
];

const RESEARCH_SCOPE_LABELS = Object.fromEntries(
  RESEARCH_SCOPE_OPTIONS.map((option) => [option.value, option.label])
) as Record<ResearchScope, string>;

const AUTHORITY_LABELS: Record<string, string> = {
  very_high: "非常权威",
  high: "较高权威",
  normal: "一般来源"
};

function EmptyResult({ locked }: { locked: boolean }) {
  return (
    <div className="border-t border-line px-5 py-12 text-center">
      <p className="text-sm font-medium text-ink">{locked ? "等待前序步骤确认" : "尚无生成结果"}</p>
      <p className="mt-1 text-xs text-moss">服务端结果生成后将在此处显示。</p>
    </div>
  );
}

function SchemaError() {
  return (
    <div role="alert" className="border-t border-[#e5c9c3] bg-[#fbf1ef] px-5 py-8 text-center">
      <p className="text-sm font-medium text-[#8f493e]">服务端结果结构异常</p>
      <p className="mt-1 text-xs text-[#8f493e]">请重新生成；若问题持续，请联系开发人员检查输出契约。</p>
    </div>
  );
}

function isStringArray(value: JsonValue | undefined): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isObjectArray(value: JsonValue | undefined): value is JsonObject[] {
  return Array.isArray(value) && value.every((item) => Boolean(item && typeof item === "object" && !Array.isArray(item)));
}

interface FindingListEditorProps {
  findings: string[];
  disabled: boolean;
  onChange: (findings: string[]) => void;
}

function FindingListEditor({ findings, disabled, onChange }: FindingListEditorProps) {
  const updateFinding = (index: number, value: string) => {
    onChange(findings.map((finding, findingIndex) => findingIndex === index ? value : finding));
  };
  const removeFinding = (index: number) => {
    onChange(findings.filter((_, findingIndex) => findingIndex !== index));
  };

  return (
    <section className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-medium text-ink">主要发现（{findings.length} 条）</h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => onChange([...findings, ""])}
        >
          <Plus size={12} />
          添加一条
        </Button>
      </div>
      {findings.length > 0 ? (
        <div className="mt-3 space-y-3">
          {findings.map((finding, index) => {
            const fieldId = `finding-${index}`;
            return (
              <div key={fieldId} className="min-w-0">
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor={fieldId} className="text-[10px] font-medium text-moss">发现 {index + 1}</label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 text-moss hover:text-[#8f493e]"
                    disabled={disabled}
                    aria-label={`删除发现 ${index + 1}`}
                    title={`删除发现 ${index + 1}`}
                    onClick={() => removeFinding(index)}
                  >
                    <Trash2 size={13} />
                  </Button>
                </div>
                <textarea
                  id={fieldId}
                  className={`${fieldClass} min-h-20 w-full min-w-0 resize-y whitespace-pre-wrap [overflow-wrap:anywhere]`}
                  disabled={disabled}
                  value={finding}
                  onChange={(event) => updateFinding(index, event.target.value)}
                />
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-xs text-moss">暂无主要发现。</p>
      )}
    </section>
  );
}

const STANDARDIZED_BRIEF_FIELDS = [
  ["objective", "活动目标"],
  ["location", "活动地点"],
  ["plannedStartAt", "开始时间"],
  ["plannedEndAt", "结束时间"],
  ["target", "经营目标"],
  ["budgetMin", "预算下限"],
  ["budgetMax", "预算上限"],
  ["targetAudience", "目标客群"],
  ["knownConstraints", "已知约束"]
] as const;

function exactKeys(value: JsonObject, allowed: readonly string[]) {
  const allowedSet = new Set(allowed);
  return Object.keys(value).every((key) => allowedSet.has(key));
}

function briefDisplayValue(value: JsonValue | undefined) {
  if (value === undefined || value === "") return "待补充";
  return String(value);
}

function BriefStep(props: ActivityStepEditorProps) {
  const standardized = asObject(props.output.standardizedBrief);
  const missing = asStringArray(props.output.missingFields);
  const hasOutput = Object.keys(props.output).length > 0;
  const allowedBriefKeys = [...STANDARDIZED_BRIEF_FIELDS.map(([key]) => key), "planningMode", "annualPeriod", "annualGoals", "plannedEventCount"];
  const validOutput = standardized !== null
    && exactKeys(props.output, ["standardizedBrief", "missingFields"])
    && exactKeys(standardized, allowedBriefKeys)
    && typeof standardized.objective === "string"
    && standardized.objective.trim().length > 0
    && allowedBriefKeys.every((key) => {
      const value = standardized[key];
      if (key === "objective" || value === undefined) return true;
      if (key === "budgetMin" || key === "budgetMax") return typeof value === "number" && Number.isFinite(value) && value >= 0;
      if (key === "plannedEventCount") return Number.isInteger(value) && Number(value) >= 2 && Number(value) <= 12;
      return typeof value === "string";
    })
    && isStringArray(props.output.missingFields);
  const setBrief = <K extends keyof ActivityBriefInput>(key: K, value: ActivityBriefInput[K]) => {
    props.onBriefChange({ ...props.brief, [key]: value });
  };

  return (
    <div>
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <label className={`${labelClass} sm:col-span-2`}>规划模式
          <select className={fieldClass} disabled={props.disabled || props.activity.steps.some((step) => Object.keys(step.outputJson).length > 0)} value={props.brief.planningMode ?? "single"} onChange={(event) => {
            const next = { ...props.brief, planningMode: event.target.value as "single" | "annual" };
            if (next.planningMode === "single") { delete next.annualPeriod; delete next.annualGoals; delete next.plannedEventCount; }
            props.onBriefChange(next);
          }}><option value="single">单场活动策划</option><option value="annual">年度活动规划</option></select>
          {props.activity.steps.some((step) => Object.keys(step.outputJson).length > 0) ? <p className="mt-1 text-[10px] text-moss">已有生成结果，规划模式已固定；如需另一模式请新建任务。</p> : null}
        </label>
        {props.brief.planningMode === "annual" ? <>
          <label className={labelClass}>年度周期 *<input className={fieldClass} disabled={props.disabled} value={props.brief.annualPeriod ?? ""} onChange={(event) => setBrief("annualPeriod", event.target.value)} /></label>
          <label className={labelClass}>计划活动数量（2 至 12 场） *<input type="number" min="2" max="12" className={fieldClass} disabled={props.disabled} value={props.brief.plannedEventCount ?? ""} onChange={(event) => setBrief("plannedEventCount", event.target.value === "" ? undefined : Number(event.target.value))} /></label>
          <label className={`${labelClass} sm:col-span-2`}>年度目标 *<textarea className={`${fieldClass} min-h-20`} disabled={props.disabled} value={props.brief.annualGoals ?? ""} onChange={(event) => setBrief("annualGoals", event.target.value)} /></label>
        </> : null}
        <label className={`${labelClass} sm:col-span-2`}>基础想法 *
          <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={props.brief.idea} onChange={(event) => setBrief("idea", event.target.value)} />
        </label>
        <label className={labelClass}>活动地点
          <input className={fieldClass} disabled={props.disabled} value={props.brief.location ?? ""} onChange={(event) => setBrief("location", event.target.value || undefined)} />
        </label>
        <label className={labelClass}>活动目标
          <input className={fieldClass} disabled={props.disabled} value={props.brief.target ?? ""} onChange={(event) => setBrief("target", event.target.value || undefined)} />
        </label>
        <label className={labelClass}>计划开始时间
          <input type="datetime-local" className={fieldClass} disabled={props.disabled} value={props.brief.plannedStartAt ?? ""} onChange={(event) => setBrief("plannedStartAt", event.target.value || undefined)} />
        </label>
        <label className={labelClass}>计划结束时间
          <input type="datetime-local" className={fieldClass} disabled={props.disabled} value={props.brief.plannedEndAt ?? ""} onChange={(event) => setBrief("plannedEndAt", event.target.value || undefined)} />
        </label>
        <label className={labelClass}>预算下限（元）
          <input type="number" min="0" step="1000" className={fieldClass} disabled={props.disabled} value={props.brief.budgetMin ?? ""} onChange={(event) => setBrief("budgetMin", event.target.value === "" ? undefined : Number(event.target.value))} />
        </label>
        <label className={labelClass}>预算上限（元）
          <input type="number" min="0" step="1000" className={fieldClass} disabled={props.disabled} value={props.brief.budgetMax ?? ""} onChange={(event) => setBrief("budgetMax", event.target.value === "" ? undefined : Number(event.target.value))} />
        </label>
        <label className={`${labelClass} sm:col-span-2`}>目标客群
          <input className={fieldClass} disabled={props.disabled} value={props.brief.targetAudience ?? ""} onChange={(event) => setBrief("targetAudience", event.target.value || undefined)} />
        </label>
        <label className={`${labelClass} sm:col-span-2`}>已知约束
          <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={props.brief.knownConstraints ?? ""} onChange={(event) => setBrief("knownConstraints", event.target.value || undefined)} />
        </label>
      </div>
      {hasOutput && !validOutput ? <SchemaError /> : standardized ? (
        <section className="border-t border-line px-5 py-5">
          <h3 className="text-sm font-semibold text-ink">标准化简报</h3>
          <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {[...STANDARDIZED_BRIEF_FIELDS, ["planningMode", "规划模式"], ["annualPeriod", "年度周期"], ["annualGoals", "年度目标"], ["plannedEventCount", "计划活动数量"]].filter(([key]) => Object.hasOwn(standardized, key)).map(([key, label]) => (
              <div key={key}>
                <dt className="text-[10px] font-medium text-moss">{label}</dt>
                <dd className="mt-1 text-xs leading-5 text-ink">{key === "planningMode" ? ({ annual: "年度活动规划", single: "单场活动策划" } as const)[standardized[key] as "annual" | "single"] : briefDisplayValue(standardized[key])}</dd>
              </div>
            ))}
          </dl>
          {missing.length ? (
            <div className="mt-5 border-l-2 border-[#c5a76b] pl-3">
              <div className="text-[10px] font-medium text-[#866936]">待补充项</div>
              <div className="mt-1 text-xs text-ink">{missing.join("、")}</div>
            </div>
          ) : null}
        </section>
      ) : <EmptyResult locked={props.step.status === "locked"} />}
    </div>
  );
}

function ResearchStep(props: ActivityStepEditorProps) {
  const sources = asObjectArray(props.output.sources);
  const hasOutput = Object.keys(props.output).length > 0;
  const validSources = isObjectArray(props.output.sources) && sources.every((source) => {
    const sourceType = source.sourceType;
    return typeof source.label === "string"
      && source.label.trim().length > 0
      && typeof sourceType === "string"
      && Object.hasOwn(SOURCE_LABELS, sourceType);
  });
  const validOutput = typeof props.output.summary === "string"
    && props.output.summary.trim().length > 0
    && isStringArray(props.output.findings)
    && isStringArray(props.output.risks)
    && validSources
    && sources.length > 0;
  if (hasOutput && !validOutput) return <SchemaError />;
  function toggleScope(scope: ResearchScope) {
    props.onResearchScopesChange(
      props.researchScopes.includes(scope)
        ? props.researchScopes.filter((item) => item !== scope)
        : [...props.researchScopes, scope]
    );
  }
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <div className="text-xs font-medium text-ink">公开资料联网搜索</div>
          <div className="mt-1 text-[10px] text-moss">当前选择：{props.input.useWebSearch === true ? "已选择" : "未选择"}</div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={props.input.useWebSearch === true}
          disabled={props.disabled}
          onClick={() => props.onSearchToggle(props.input.useWebSearch !== true)}
          className={`relative h-6 w-11 rounded-full transition disabled:cursor-not-allowed disabled:opacity-45 ${props.input.useWebSearch === true ? "bg-forest" : "bg-[#bdc7c2]"}`}
        >
          <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${props.input.useWebSearch === true ? "left-6" : "left-1"}`} />
        </button>
      </div>
      {props.input.useWebSearch === true ? (
        <section className="border-t border-line px-5 py-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <label className={labelClass}>搜索主题
              <input
                className={fieldClass}
                maxLength={70}
                disabled={props.disabled}
                value={props.researchQuery}
                onChange={(event) => props.onResearchQueryChange(event.target.value)}
              />
            </label>
            <Button
              className="min-w-36"
              type="button"
              onClick={props.onResearchRun}
              disabled={props.disabled || props.researchRunning || !props.researchQuery || props.researchScopes.length === 0}
            >
              <Search size={13} />
              {props.researchRunning ? "处理中" : "搜索并生成研判"}
            </Button>
          </div>
          <fieldset className="mt-4" disabled={props.disabled}>
            <legend className="text-[10px] font-medium text-moss">搜索范围</legend>
            <div className="mt-2 flex flex-wrap gap-3">
              {RESEARCH_SCOPE_OPTIONS.map((option) => (
                <label key={option.value} className="flex items-center gap-2 text-xs text-ink">
                  <input
                    type="checkbox"
                    checked={props.researchScopes.includes(option.value)}
                    onChange={() => toggleScope(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>
          <p className="mt-3 text-[10px] leading-5 text-moss">每个已搜索范围分别归纳一次，全部检索摘要参与；修改范围后需重新搜索才会用于本次归纳。</p>
          {props.researchProgressError ? <p role="alert" className="mt-3 text-xs text-[#8f493e]">进度读取失败：{props.researchProgressError}</p> : null}
          {props.researchProgress ? (
            <ResearchGenerationStatus progress={props.researchProgress} stepStatus={props.step.status} />
          ) : props.researchRunning ? <p role="status" className="mt-3 text-xs text-pine">正在搜索资料，归纳进度将在搜索完成后显示。</p> : null}
        </section>
      ) : null}
      {props.input.useWebSearch === true ? (
        <section className="border-t border-line px-5 py-4">
          <h3 className="text-xs font-medium text-ink">本次研判资料范围</h3>
          {props.researchSelectionError ? (
            <p role="alert" className="mt-2 text-xs text-[#8f493e]">资料纳入记录加载失败：{props.researchSelectionError}</p>
          ) : props.researchSelection ? (
            <>
              <p className="mt-2 text-xs text-ink">{props.researchSelection.totalCount} 条来源，{props.researchSelection.selectedCount} 条纳入，{props.researchSelection.omittedCount} 条未纳入</p>
              <p className="mt-1 text-[10px] text-moss">全部有效搜索来源的完整检索摘要均参与模型归纳；研判只保留简短结论和直接支撑结论的引用。</p>
            </>
          ) : <p className="mt-2 text-xs text-moss">正在加载资料纳入记录…</p>}
        </section>
      ) : null}
      {hasOutput ? (
        <div className="border-t border-line px-5 py-5">
          <label className={labelClass}>研判摘要
            <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(props.output.summary)} onChange={(event) => props.onOutputChange({ ...props.output, summary: event.target.value })} />
          </label>
          <div className="mt-5 space-y-5">
            <FindingListEditor
              findings={asStringArray(props.output.findings)}
              disabled={props.disabled}
              onChange={(findings) => props.onOutputChange({ ...props.output, findings })}
            />
            <label className={labelClass}>风险提示（每行一项）
              <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={asStringArray(props.output.risks).join("\n")} onChange={(event) => props.onOutputChange({ ...props.output, risks: lines(event.target.value) })} />
            </label>
          </div>
          <section className="mt-6 border-t border-line pt-5">
            <h3 className="text-sm font-semibold text-ink">直接支撑研判的引用（{sources.length} 条）</h3>
            <p className="mt-1 text-[10px] text-moss">以下是本次研判使用的引用；完整检索资料可在下方查看。</p>
            <div className="mt-3 divide-y divide-line border-y border-line">
              {sources.map((source, index) => {
                const sourceType = asString(source.sourceType);
                const sourceLabel = SOURCE_LABELS[sourceType as keyof typeof SOURCE_LABELS];
                const url = asString(source.url);
                const scope = asString(source.scope) as ResearchScope;
                const authority = asString(source.authorityLevel);
                return (
                  <div key={`${asString(source.label)}-${index}`} className="py-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-mist px-2 py-1 text-[10px] font-medium text-pine">{sourceLabel}</span>
                      <span className="text-xs font-medium text-ink">{asString(source.label) || "未命名来源"}</span>
                      {url ? <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[10px] text-pine hover:underline">查看来源<ExternalLink size={10} /></a> : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-moss">
                      {source.siteName ? <span>站点：{asString(source.siteName)}</span> : null}
                      {scope && RESEARCH_SCOPE_LABELS[scope] ? <span>范围：{RESEARCH_SCOPE_LABELS[scope]}</span> : null}
                      {authority && AUTHORITY_LABELS[authority] ? <span>权威度：{AUTHORITY_LABELS[authority]}</span> : null}
                      {typeof source.rank === "number" ? <span>排序：{source.rank + 1}</span> : null}
                      {source.publishedAt ? <span>发布时间：{asString(source.publishedAt)}</span> : null}
                    </div>
                    {asString(source.excerpt) ? <p className="mt-2 text-xs leading-5 text-moss">{asString(source.excerpt)}</p> : null}
                    {asString(source.reasoning) ? <p className="mt-2 text-[10px] leading-5 text-moss">依据：{asString(source.reasoning)}</p> : null}
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      ) : <EmptyResult locked={props.step.status === "locked"} />}
      {props.input.useWebSearch === true && props.researchSelection ? (
        <section className="border-t border-line px-5 py-5">
          <h3 className="text-sm font-semibold text-ink">全部检索来源（{props.researchSelection.totalCount} 条）</h3>
          <p className="mt-1 text-[10px] leading-5 text-moss">全部 {props.researchSelection.selectedCount} 条来源的完整检索摘要均纳入本次模型归纳。研判仅引用直接支撑结论的资料，其他来源也可在此核查。</p>
          {props.researchSelection.totalCount > 0 ? (
            <ul aria-label="全部检索来源" tabIndex={0} className="mt-3 max-h-80 overflow-y-auto overscroll-contain divide-y divide-line rounded-md border border-line px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-moss">
              {props.researchSelection.selected.map((source, index) => (
                <li key={`${source.scope}-${source.rank}-${index}`} className="py-3">
                  <div className="flex flex-wrap items-start gap-2">
                    <span className="shrink-0 rounded-full bg-mist px-2 py-0.5 text-[10px] text-pine">已纳入研判</span>
                    <a href={source.url} target="_blank" rel="noreferrer" className="min-w-0 break-words text-xs font-medium text-pine hover:underline">{source.label}<ExternalLink size={10} className="ml-1 inline" /></a>
                  </div>
                  <p className="mt-1 text-[10px] text-moss">{RESEARCH_SCOPE_LABELS[source.scope]} · 搜索排名 {source.rank + 1}{source.siteName ? ` · ${source.siteName}` : ""}{source.authorityLevel ? ` · ${AUTHORITY_LABELS[source.authorityLevel]}` : ""}</p>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] text-pine">查看完整检索摘要</summary>
                    <div className="mt-2 text-[10px] text-moss">采集时间：{source.capturedAt}{source.publishedAt ? ` · 发布时间：${source.publishedAt}` : ""}</div>
                    <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-6 text-ink">{source.excerpt}</p>
                  </details>
                </li>
              ))}
            </ul>
          ) : <p className="mt-3 text-xs text-moss">尚无检索来源。</p>}
        </section>
      ) : null}
    </div>
  );
}

function ResearchGenerationStatus({ progress, stepStatus }: { progress: ResearchGenerationProgress; stepStatus: ActivityStep["status"] }) {
  const percent = Math.floor(progress.completedScopes / progress.totalScopes * 100);
  const labels = { waiting: "等待归纳", running: "归纳中", completed: "已完成", failed: "失败", cancelled: "未执行" };
  const current = progress.scopes.find((entry) => entry.status === "running");
  const message = progress.status === "completed" ? (stepStatus === "confirmed" ? "全部范围已归纳，研判已确认。" : stepStatus === "review" ? "全部范围已归纳，草稿已保存，等待确认。" : "上次归纳已完成，当前资料待重新归纳。")
    : progress.status === "failed" ? "本次归纳结果未保存。可手动重试。"
    : current ? `正在归纳：${RESEARCH_SCOPE_LABELS[current.scope]}`
    : percent === 100 ? "各范围归纳完成，正在保存草稿…" : "正在准备分范围归纳…";
  return (
    <section aria-label="分范围归纳进度" className="mt-4 rounded-md border border-line bg-mist p-3">
      <div role="status" aria-live="polite" className="text-xs text-pine">
        <p className="font-medium">归纳进度：{progress.completedScopes} / {progress.totalScopes} 个范围 · {percent}%</p>
        <p className="mt-1 leading-5">{message}</p>
      </div>
      <progress className="mt-2 h-2 w-full accent-[#2f6554]" value={progress.completedScopes} max={progress.totalScopes} aria-label="已完成归纳范围" />
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {progress.scopes.map((entry) => (
          <li key={entry.scope} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-white px-3 py-2 text-xs">
            <span>{RESEARCH_SCOPE_LABELS[entry.scope]} · {entry.sourceCount} 条来源</span>
            <span className={entry.status === "failed" ? "text-[#8f493e]" : "text-pine"}>{labels[entry.status]}</span>
          </li>
        ))}
      </ul>
      {progress.errorCode ? <p role="alert" className="mt-3 break-words text-xs text-[#8f493e]">{readableError(new ApiError(422, progress.errorCode, { detail: { code: progress.errorCode } }))}</p> : null}
    </section>
  );
}

function ThemeStep(props: ActivityStepEditorProps) {
  const candidates = asObjectArray(props.output.candidates);
  const hasOutput = Object.keys(props.output).length > 0;
  const validOutput = isObjectArray(props.output.candidates)
    && candidates.length >= 2
    && candidates.length <= 3
    && new Set(candidates.map((candidate) => candidate.id)).size === candidates.length
    && candidates.every((candidate) => typeof candidate.id === "string"
      && candidate.id.trim().length > 0
      && typeof candidate.name === "string"
      && candidate.name.trim().length > 0
      && typeof candidate.storyline === "string"
      && candidate.storyline.trim().length > 0
      && typeof candidate.visualDirection === "string"
      && candidate.visualDirection.trim().length > 0
      && isStringArray(candidate.highlights)
      && candidate.highlights.length > 0);
  const selectedThemeId = asString(props.input.selectedThemeId);
  const updateCandidate = (index: number, patch: JsonObject) => {
    const next = candidates.map((candidate, candidateIndex) => candidateIndex === index ? { ...candidate, ...patch } : candidate);
    props.onOutputChange({ ...props.output, candidates: next });
  };
  if (hasOutput && !validOutput) return <SchemaError />;
  if (!hasOutput) return <EmptyResult locked={props.step.status === "locked"} />;

  return (
    <div className="divide-y divide-line">
      {candidates.map((candidate, index) => {
        const id = asString(candidate.id);
        const selected = selectedThemeId === id;
        return (
          <section key={id || index} className={`px-5 py-5 ${selected ? "bg-[#f4f7f5]" : "bg-white"}`}>
            <label className="flex cursor-pointer items-start gap-3">
              <input type="radio" name="selected-theme" className="mt-1 h-4 w-4 accent-[#17372f]" disabled={props.disabled} checked={selected} onChange={() => props.onInputChange({ ...props.input, selectedThemeId: id })} />
              <span className="min-w-0 flex-1">
                <span className="text-[10px] font-medium text-moss">候选主题 {index + 1}</span>
                <input className={`${fieldClass} mt-1 text-base font-semibold`} disabled={props.disabled} value={asString(candidate.name)} onChange={(event) => updateCandidate(index, { name: event.target.value })} />
              </span>
            </label>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <label className={labelClass}>故事线
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(candidate.storyline)} onChange={(event) => updateCandidate(index, { storyline: event.target.value })} />
              </label>
              <label className={labelClass}>视觉方向
                <textarea className={`${fieldClass} min-h-28 resize-y`} disabled={props.disabled} value={asString(candidate.visualDirection)} onChange={(event) => updateCandidate(index, { visualDirection: event.target.value })} />
              </label>
              <label className={`${labelClass} lg:col-span-2`}>核心亮点（每行一项）
                <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asStringArray(candidate.highlights).join("\n")} onChange={(event) => updateCandidate(index, { highlights: lines(event.target.value) })} />
              </label>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function ContentSpaceStep(props: ActivityStepEditorProps) {
  const schedule = asObjectArray(props.output.schedule);
  const zones = asObjectArray(props.output.zones);
  const personnel = asObjectArray(props.output.personnel);
  const safety = asStringArray(props.output.safetyRequirements);
  const hasOutput = Object.keys(props.output).length > 0;
  const validOutput = isObjectArray(props.output.schedule)
    && schedule.length > 0
    && schedule.every((item) => typeof item.time === "string" && item.time.trim().length > 0 && typeof item.title === "string" && item.title.trim().length > 0 && typeof item.description === "string" && item.description.trim().length > 0)
    && isObjectArray(props.output.zones)
    && zones.length > 0
    && zones.every((item) => typeof item.name === "string" && item.name.trim().length > 0 && typeof item.purpose === "string" && item.purpose.trim().length > 0 && isStringArray(item.activities) && isStringArray(item.requirements))
    && isObjectArray(props.output.personnel)
    && personnel.length > 0
    && personnel.every((item) => typeof item.role === "string" && item.role.trim().length > 0 && typeof item.count === "number" && Number.isInteger(item.count) && item.count > 0 && isStringArray(item.responsibilities) && item.responsibilities.length > 0)
    && isStringArray(props.output.safetyRequirements)
    && safety.length > 0;
  const setArrayItem = (key: "schedule" | "zones" | "personnel", items: JsonObject[], index: number, patch: JsonObject) => {
    props.onOutputChange({
      ...props.output,
      [key]: items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)
    });
  };
  if (hasOutput && !validOutput) return <SchemaError />;
  if (!hasOutput) return <EmptyResult locked={props.step.status === "locked"} />;

  return (
    <div className="divide-y divide-line">
      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">活动日程</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {schedule.map((item, index) => (
            <div key={index} className="grid gap-3 py-4 sm:grid-cols-[140px_minmax(0,1fr)]">
              <label className={labelClass}>时间
                <input className={fieldClass} disabled={props.disabled} value={asString(item.time)} onChange={(event) => setArrayItem("schedule", schedule, index, { time: event.target.value })} />
              </label>
              <div className="grid gap-3">
                <label className={labelClass}>环节名称
                  <input className={fieldClass} disabled={props.disabled} value={asString(item.title)} onChange={(event) => setArrayItem("schedule", schedule, index, { title: event.target.value })} />
                </label>
                <label className={labelClass}>环节内容
                  <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asString(item.description)} onChange={(event) => setArrayItem("schedule", schedule, index, { description: event.target.value })} />
                </label>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">空间分区</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {zones.map((item, index) => (
            <div key={index} className="grid gap-3 py-4 lg:grid-cols-2">
              <label className={labelClass}>分区名称
                <input className={fieldClass} disabled={props.disabled} value={asString(item.name)} onChange={(event) => setArrayItem("zones", zones, index, { name: event.target.value })} />
              </label>
              <label className={labelClass}>分区用途
                <input className={fieldClass} disabled={props.disabled} value={asString(item.purpose)} onChange={(event) => setArrayItem("zones", zones, index, { purpose: event.target.value })} />
              </label>
              <label className={labelClass}>活动内容（每行一项）
                <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asStringArray(item.activities).join("\n")} onChange={(event) => setArrayItem("zones", zones, index, { activities: lines(event.target.value) })} />
              </label>
              <label className={labelClass}>配置要求（每行一项）
                <textarea className={`${fieldClass} min-h-24 resize-y`} disabled={props.disabled} value={asStringArray(item.requirements).join("\n")} onChange={(event) => setArrayItem("zones", zones, index, { requirements: lines(event.target.value) })} />
              </label>
            </div>
          ))}
        </div>
      </section>
      <section className="px-5 py-5">
        <h3 className="text-sm font-semibold text-ink">人员配置</h3>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {personnel.map((item, index) => (
            <div key={index} className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_120px]">
              <label className={labelClass}>岗位
                <input className={fieldClass} disabled={props.disabled} value={asString(item.role)} onChange={(event) => setArrayItem("personnel", personnel, index, { role: event.target.value })} />
              </label>
              <label className={labelClass}>人数
                <input type="number" min="1" className={fieldClass} disabled={props.disabled} value={typeof item.count === "number" ? item.count : ""} onChange={(event) => setArrayItem("personnel", personnel, index, { count: Number(event.target.value) })} />
              </label>
              <label className={`${labelClass} sm:col-span-2`}>职责（每行一项）
                <textarea className={`${fieldClass} min-h-20 resize-y`} disabled={props.disabled} value={asStringArray(item.responsibilities).join("\n")} onChange={(event) => setArrayItem("personnel", personnel, index, { responsibilities: lines(event.target.value) })} />
              </label>
            </div>
          ))}
        </div>
      </section>
      <section className="px-5 py-5">
        <label className={labelClass}>安全要求（每行一项）
          <textarea className={`${fieldClass} min-h-32 resize-y`} disabled={props.disabled} value={safety.join("\n")} onChange={(event) => props.onOutputChange({ ...props.output, safetyRequirements: lines(event.target.value) })} />
        </label>
      </section>
    </div>
  );
}

export function ActivityStepEditor(props: ActivityStepEditorProps) {
  if (props.step.stepNo === 1) return <BriefStep {...props} />;
  if (props.step.stepNo === 2) return <ResearchStep {...props} />;
  if (props.step.stepNo === 3) return props.activity.input.planningMode === "annual" ? <AnnualEventBriefs {...props} /> : <ThemeStep {...props} />;
  if (props.activity.input.planningMode === "annual" && Object.keys(props.output).length > 0) return <AnnualStepUnits {...props} />;
  if (props.step.stepNo === 4) return <ContentSpaceStep {...props} />;
  return (
    <ActivityLaterStepEditor
      step={props.step}
      output={props.output}
      disabled={props.disabled}
      onOutputChange={props.onOutputChange}
    />
  );
}

function AnnualEventBriefs(props: ActivityStepEditorProps) {
  if (!Object.keys(props.output).length) return <EmptyResult locked={props.step.status === "locked"} />;
  const events = asObjectArray(props.output.eventBriefs);
  const update = (index: number, patch: JsonObject) => props.onOutputChange({ ...props.output, eventBriefs: events.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) });
  return <div className="space-y-5 p-5">
    <label className={labelClass}>年度叙事与活动架构<textarea className={`${fieldClass} min-h-28`} disabled={props.disabled} value={asString(props.output.annualNarrative)} onChange={(event) => props.onOutputChange({ ...props.output, annualNarrative: event.target.value })} /></label>
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-sm font-semibold">年度活动简案（{events.length} 场）</h3><Button type="button" variant="outline" disabled={props.disabled || events.length >= 12} onClick={() => {
      const ids = new Set(events.map((item) => asString(item.id)));
      let ordinal = 1; while (ids.has(`event-${ordinal}`)) ordinal++;
      props.onOutputChange({ ...props.output, eventBriefs: [...events, { id: `event-${ordinal}`, name: "", timeWindow: "", targetAudience: "", positioning: "", themeDirection: "", scale: "", sharedAssets: [], highlights: [] }] });
    }}><Plus size={12} />添加活动简案</Button></div>
    <p className="text-xs text-moss">确认后整体推进年度策划；各活动可单独进入完整的单场策划流程。</p>
    {events.map((item, index) => <section key={asString(item.id)} className="rounded-md border border-line p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h4 className="text-xs font-medium">活动 {index + 1}</h4><div className="flex gap-2"><Button type="button" variant="outline" size="sm" disabled={!props.canOpenPlanItem} onClick={() => props.onPlanItemOpen(asString(item.id))}>单独深入策划</Button><Button type="button" variant="ghost" size="sm" disabled={props.disabled || events.length <= 2} onClick={() => props.onOutputChange({ ...props.output, eventBriefs: events.filter((_, ordinal) => ordinal !== index) })}><Trash2 size={12} />删除</Button></div></div>
      <div className="grid gap-3 sm:grid-cols-2">{([ ["name", "活动名称"], ["timeWindow", "时间窗口"], ["targetAudience", "目标客群"], ["positioning", "活动定位"], ["themeDirection", "主题方向"], ["scale", "活动规模"] ] as const).map(([key, label]) => <label key={key} className={labelClass}>{label}<input className={fieldClass} disabled={props.disabled} value={asString(item[key])} onChange={(event) => update(index, { [key]: event.target.value })} /></label>)}
      {([ ["sharedAssets", "共享资产（每行一项）"], ["highlights", "活动亮点（每行一项）"] ] as const).map(([key, label]) => <label key={key} className={labelClass}>{label}<textarea className={`${fieldClass} min-h-20`} disabled={props.disabled} value={asStringArray(item[key]).join("\n")} onChange={(event) => update(index, { [key]: lines(event.target.value) })} /></label>)}</div>
    </section>)}
  </div>;
}

function AnnualStepUnits(props: ActivityStepEditorProps) {
  const [selectedUnit, setSelectedUnit] = useState("annual");
  const events = asObjectArray(props.output.eventPlans);
  const briefs = asObjectArray(props.activity.steps.find((step) => step.stepNo === 3)?.outputJson.eventBriefs);
  const key = selectedUnit === "annual" || events.some((item) => item.eventId === selectedUnit) ? selectedUnit : "annual";
  const unitOutput = key === "annual" ? asObject(props.output.annualPlan) : asObject(events.find((item) => item.eventId === key)?.output);
  if (!unitOutput) return <SchemaError />;
  const onChange = (value: JsonObject) => {
    const annualPlan = key === "annual" ? value : props.output.annualPlan;
    const eventPlans = events.map((item) => item.eventId === key ? { ...item, output: value } : item);
    const next: JsonObject = { ...props.output, annualPlan, eventPlans };
    if (props.step.stepNo === 5) next.annualTotalAmount = decimalSum([Number((annualPlan as JsonObject).totalAmount), ...eventPlans.map((item) => Number((item.output as JsonObject).totalAmount))]);
    props.onOutputChange(next);
  };
  return <div><div className="border-b border-line p-5"><label className={labelClass}>查看与编辑策划单元<select className={fieldClass} value={key} onChange={(event) => setSelectedUnit(event.target.value)}><option value="annual">年度统筹</option>{events.map((item) => <option key={asString(item.eventId)} value={asString(item.eventId)}>{asString(briefs.find((brief) => brief.id === item.eventId)?.name) || asString(item.eventId)}</option>)}</select></label>{props.step.stepNo === 5 ? <p className="mt-3 text-sm font-medium">年度预算总额：¥ {Number(props.output.annualTotalAmount).toLocaleString("zh-CN")}</p> : null}</div>
    {props.step.stepNo === 4 ? <ContentSpaceStep {...props} output={unitOutput} onOutputChange={onChange} /> : <ActivityLaterStepEditor step={props.step} output={unitOutput} disabled={props.disabled} onOutputChange={onChange} />}
  </div>;
}
