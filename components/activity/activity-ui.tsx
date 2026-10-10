import { ApiError } from "@/lib/api/client";
import { ActivityContractError } from "@/lib/api/activity-contract";
import type { ActivityStatus, ActivityStepStatus, JsonObject, JsonValue } from "@/lib/types/activity";

export const STEP_NAMES = [
  "活动简报",
  "数据收集与研判",
  "活动主题方案",
  "内容与空间设计",
  "预算控制与资源配置",
  "宣传内容与传播计划",
  "审批、任务分解与执行准备",
  "渠道联动与商业化",
  "效果预测与活动复盘"
] as const;

export const ACTIVITY_STATUS_LABELS: Record<ActivityStatus, string> = {
  draft: "草稿",
  running: "进行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "异常",
  archived: "已归档"
};

export const STEP_STATUS_LABELS: Record<ActivityStepStatus, string> = {
  locked: "未解锁",
  draft: "草稿",
  generating: "生成中",
  review: "待确认",
  confirmed: "已确认",
  needs_review: "需复核",
  failed: "生成失败"
};

export const SOURCE_LABELS = {
  actual: "实际数据",
  public: "公开数据",
  calculated: "参考测算",
  missing: "待补充"
} as const;

export function activityStatusClass(status: ActivityStatus) {
  if (status === "failed") return "bg-[#f7e8e5] text-[#9b4d42]";
  if (status === "paused" || status === "archived") return "bg-[#ecefed] text-[#63706c]";
  if (status === "completed") return "bg-[#e9efe1] text-[#526a35]";
  if (status === "draft") return "bg-[#f4eee2] text-[#866936]";
  return "bg-[#e5efeb] text-[#356458]";
}

export function stepStatusClass(status: ActivityStepStatus) {
  if (status === "failed") return "bg-[#f7e8e5] text-[#9b4d42]";
  if (status === "needs_review") return "bg-[#f5eadc] text-[#91613c]";
  if (status === "confirmed") return "bg-[#e9efe1] text-[#526a35]";
  if (status === "generating" || status === "review") return "bg-[#e5efeb] text-[#356458]";
  return "bg-[#ecefed] text-[#63706c]";
}

export function asObject(value: JsonValue | undefined): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null;
}

export function asObjectArray(value: JsonValue | undefined): JsonObject[] {
  return Array.isArray(value)
    ? value.filter((item): item is JsonObject => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];
}

export function asString(value: JsonValue | undefined) {
  return typeof value === "string" ? value : "";
}

export function asStringArray(value: JsonValue | undefined) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

export function isoToLocalInput(value: string | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new ActivityContractError("活动日期不符合已确认的数据契约。");
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function localInputToIso(value: string | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new ActivityContractError("活动日期输入无效，请重新选择日期和时间。");
  return date.toISOString();
}

export function getApiErrorCode(error: unknown): string | null {
  if (!(error instanceof ApiError) || !error.payload || typeof error.payload !== "object") return null;
  const detail = (error.payload as Record<string, unknown>).detail;
  if (!detail || typeof detail !== "object") return null;
  const code = (detail as Record<string, unknown>).code;
  return typeof code === "string" ? code : null;
}

export function isAuthenticationError(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

export function readableError(error: unknown) {
  const code = getApiErrorCode(error);
  const errorMessages: Record<string, string> = {
    PROVIDER_NOT_CONFIGURED: "模型服务尚未配置，请联系管理员完成配置。",
    PROVIDER_AUTH_ERROR: "模型服务凭据无效，请联系管理员检查配置。",
    PROVIDER_BALANCE_ERROR: "模型服务余额不足，请充值后重试。",
    PROVIDER_RATE_LIMITED: "模型服务请求过于频繁，请稍后重试。",
    PROVIDER_TIMEOUT: "模型生成超时，可稍后重新生成。",
    MODEL_UNAVAILABLE: "当前模型暂不可用，请联系管理员调整配置。",
    PROVIDER_UNAVAILABLE: "模型服务暂不可用，请稍后重试。",
    INVALID_MODEL_RESPONSE: "生成结果格式异常，请重新生成。",
    SEARCH_CONFIGURATION_ERROR: "联网搜索服务尚未配置，请联系管理员完成配置。",
    INVALID_SEARCH_REQUEST: "联网搜索条件无效，请检查搜索主题和范围。",
    SEARCH_INVALID_RESPONSE: "联网搜索结果格式异常，请稍后重试。",
    SEARCH_TIMEOUT: "联网搜索请求超时，请稍后重试。",
    SEARCH_UNAVAILABLE: "暂时无法连接联网搜索服务，请稍后重试。",
    SEARCH_RATE_LIMITED: "联网搜索请求过于频繁，请稍后重试。",
    SEARCH_AUTHENTICATION_FAILED: "联网搜索凭据无效，请联系管理员检查配置。",
    SEARCH_UPSTREAM_ERROR: "联网搜索服务请求失败，请稍后重试。",
    SEARCH_NO_RESULTS: "联网搜索没有找到相关结果，请调整搜索主题或范围。",
    WEB_SEARCH_NOT_ENABLED: "请先启用联网搜索并保存当前步骤。",
    VERSION_CONFLICT: "内容版本已变化，请刷新后重试。",
    ACTIVITY_NOT_WRITABLE: "当前活动状态不允许修改步骤。",
    STEP_LOCKED: "前置步骤尚未确认，当前步骤仍处于锁定状态。",
    STEP_GENERATING: "当前步骤正在生成，请等待生成完成。",
    PREVIOUS_STEP_NOT_CONFIRMED: "请先确认前置步骤，再操作当前步骤。",
    RESEARCH_GENERATION_REQUIRED: "第 2 步模型归纳尚未完成，请返回第 2 步完成归纳后再确认或继续。",
    GENERATION_INTERRUPTED: "归纳进度连接已中断，请刷新查看实际状态；如归纳失败，可手动重试。",
    USE_RESEARCH_STREAM_ENDPOINT: "联网资料须通过分范围归纳入口生成，请刷新页面后重试。",
    RESEARCH_EVIDENCE_REQUIRED: "尚无可归纳的联网资料，请先执行搜索。",
    PLANNING_MODE_LOCKED: "已有生成结果，规划模式已固定；如需另一模式请新建任务。",
    PLAN_ITEM_SOURCE_CHANGED: "年度活动简案版本已改变，请返回年度任务重新检查关联活动。",
    STEP_NOT_GENERATABLE: "当前步骤状态不允许生成内容。",
    STEP_NOT_CONFIRMABLE: "当前步骤还没有可确认的结果。",
    STEP_OUTPUT_REQUIRED: "当前步骤缺少输出内容，无法确认。",
    THEME_SELECTION_REQUIRED: "请先选择一个候选主题并保存。",
    INVALID_THEME_SELECTION: "所选主题不属于当前候选方案，请重新选择。",
    STEP_NOT_CONFIRMED: "只有已确认的步骤才能重新打开。",
    STEP_REOPEN_REQUIRED: "当前步骤已确认，请先重新打开后再修改。",
    STEP_NOT_IMPLEMENTED: "当前步骤尚未接入此操作。",
    GENERATION_STALE: "本次生成已失效，请刷新后重新操作。",
    INVALID_STEP_INPUT: "步骤输入不符合当前数据契约，请检查后重试。",
    INVALID_STEP_OUTPUT: "步骤输出不符合当前数据契约，请检查后重试。",
    PERSISTED_STEP_OUTPUT_INVALID: "已保存的步骤结果不符合当前数据契约，本次操作已停止。请检查当前步骤并重新生成；若无法打开任务，请联系开发人员修复保存的数据。",
    PUBLIC_CITATION_METADATA_MISMATCH: "模型引用的来源信息与已纳入的搜索来源不一致，本次研判未保存，请重新归纳。",
    PUBLIC_CITATION_EXCERPT_MISMATCH: "模型引用摘录不是来源中的连续原文，存在拼接或改写，本次研判未保存，请重新归纳。",
    USE_STEP_ENDPOINT: "请在对应步骤中修改该内容。"
  };
  if (code && errorMessages[code]) return errorMessages[code];
  if (error instanceof ActivityContractError) return error.message;
  if (error instanceof ApiError) {
    if (error.status === 401) return "登录状态已失效，请重新登录。";
    if (error.status === 404) return "未找到请求的数据。";
    if (code) return `服务返回未识别的错误（${code}），请联系管理员。`;
    if (error.status === 409) return "请求与当前业务状态冲突，请联系管理员检查。";
    if (error.status >= 500) return "服务暂时不可用，请稍后重试。";
  }
  return "操作失败，但服务未返回可识别的错误信息。";
}

export const fieldClass =
  "mt-1.5 w-full rounded-md border border-line bg-[#f8f9f7] px-3 py-2.5 text-sm text-ink outline-none transition focus:border-moss disabled:cursor-not-allowed disabled:bg-[#f0f2ef] disabled:text-[#7a8783]";

export const labelClass = "block text-xs font-medium text-ink";

export { ActivityContractError };
