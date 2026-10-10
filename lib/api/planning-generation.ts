import { ActivityContractError, parseActivityStep } from "@/lib/api/activity-contract";
import { ApiError } from "@/lib/api/client";
import type { ActivityStep, ActivityStepNo, PlanningGenerationProgress } from "@/lib/types/activity";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function fail(message: string): never { throw new ActivityContractError(`策划生成数据异常：${message}`); }
function record(value: unknown, fields: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("预期对象。");
  const result = value as Record<string, unknown>;
  if (Object.keys(result).some((key) => !fields.includes(key))) fail("包含未知字段。");
  return result;
}
function integer(value: unknown, minimum = 0): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum) fail("数量无效。");
  return value;
}
export function parsePlanningGenerationProgress(value: unknown, activityId: string, stepNo: ActivityStepNo): PlanningGenerationProgress {
  const item = record(value, ["activityId", "generationId", "stepNo", "status", "totalUnits", "completedUnits", "units", "errorCode"]);
  if (item.activityId !== activityId || !uuid.test(activityId) || item.stepNo !== stepNo) fail("活动或步骤标识不一致。");
  if (typeof item.generationId !== "string" || !uuid.test(item.generationId)) fail("生成标识无效。");
  if (!["running", "completed", "failed"].includes(item.status as string) || !Array.isArray(item.units)) fail("生成状态或单元列表无效。");
  const units = item.units.map((value) => {
    const unit = record(value, ["key", "label", "status"]);
    if (typeof unit.key !== "string" || !unit.key.trim() || typeof unit.label !== "string" || !unit.label.trim() || !["waiting", "running", "completed", "failed", "cancelled"].includes(unit.status as string)) fail("单元数据无效。");
    return unit as PlanningGenerationProgress["units"][number];
  });
  const totalUnits = integer(item.totalUnits, 1), completedUnits = integer(item.completedUnits);
  if (totalUnits > 13 || totalUnits !== units.length || new Set(units.map((unit) => unit.key)).size !== totalUnits) fail("单元数量不一致。");
  if (units[0].key === "single" ? totalUnits !== 1 : units[0].key !== "annual" || units.slice(1).some((unit) => ["annual", "single"].includes(unit.key))) fail("单元规划模式无效。");
  if (completedUnits !== units.filter((unit) => unit.status === "completed").length || units.some((unit, index) => unit.status === "completed" && index >= completedUnits)) fail("完成单元必须依次执行。");
  if (units.filter((unit) => unit.status === "running").length > 1 || units.some((unit, index) => unit.status === "running" && index !== completedUnits)) fail("运行单元顺序无效。");
  if (item.status === "completed" && completedUnits !== totalUnits) fail("尚未完成全部单元。");
  if (item.status === "running" && units.some((unit) => ["failed", "cancelled"].includes(unit.status))) fail("运行状态包含终止单元。");
  if (item.status === "failed") {
    if (typeof item.errorCode !== "string" || !item.errorCode.trim() || units.some((unit) => ["waiting", "running"].includes(unit.status))) fail("失败状态不完整。");
    const unfinished = units.slice(completedUnits);
    if (unfinished.filter((unit) => unit.status === "failed").length > 1 || unfinished.some((unit, index) => unit.status === "failed" && index !== 0)) fail("失败单元必须是首个未完成单元。");
  } else if (Object.hasOwn(item, "errorCode")) fail("非失败状态包含错误码。");
  return { activityId, generationId: item.generationId, stepNo, status: item.status as PlanningGenerationProgress["status"], totalUnits, completedUnits, units, ...(item.status === "failed" ? { errorCode: item.errorCode as string } : {}) };
}
export function parsePlanningGenerationEnvelope(value: unknown, activityId: string, stepNo: ActivityStepNo): PlanningGenerationProgress | null {
  const item = record(value, ["activityId", "stepNo", "progress"]);
  if (item.activityId !== activityId || item.stepNo !== stepNo || !Object.hasOwn(item, "progress")) fail("进度响应无效。");
  return item.progress === null ? null : parsePlanningGenerationProgress(item.progress, activityId, stepNo);
}
export function checkPlanningProgressTransition(previous: PlanningGenerationProgress | null, next: PlanningGenerationProgress) {
  if (!previous) { if (next.status !== "running" || next.units.some((unit) => unit.status !== "waiting")) fail("缺少开始事件。"); return; }
  if (previous.status !== "running" || previous.generationId !== next.generationId || previous.activityId !== next.activityId || previous.stepNo !== next.stepNo || previous.totalUnits !== next.totalUnits) fail("生成顺序不一致。");
  for (let index = 0; index < previous.units.length; index++) {
    const before = previous.units[index], after = next.units[index];
    if (before.key !== after.key || before.label !== after.label) fail("生成单元发生变化。");
    const allowed = before.status === "waiting" ? ["waiting", "running", "cancelled"] : before.status === "running" ? ["running", "completed", "failed", "cancelled"] : [before.status];
    if (!allowed.includes(after.status)) fail("单元状态回退或跳跃。");
  }
}
/** POST SSE is consumed as bytes arrive; no fabricated progress or implicit retry. */
export async function consumePlanningGenerationStream(response: Response, activityId: string, stepNo: ActivityStepNo, onProgress: (progress: PlanningGenerationProgress) => void): Promise<ActivityStep> {
  if (!response.ok) {
    const payload: unknown = await response.json();
    throw new ApiError(response.status, `策划生成请求失败（${response.status}）`, payload);
  }
  if (!response.headers.get("content-type")?.startsWith("text/event-stream") || !response.body) fail("服务未返回进度流。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  let previous: PlanningGenerationProgress | null = null;
  let completedStep: ActivityStep | null = null;
  let failureCode: string | null = null;
  let streamEnded = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, separator.index);
        buffer = buffer.slice(separator.index + separator[0].length);
        if (!frame.trim() || frame.split(/\r?\n/).every((line) => line.startsWith(":"))) continue;
        if (completedStep || failureCode) fail("终结后仍有事件。");
        let event: string | null = null;
        const data: string[] = [];
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith(":")) continue;
          if (line.startsWith("event:") && event === null) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
          else fail("未知或重复事件字段。");
        }
        if (!event || !["planning_progress", "planning_completed", "planning_failed"].includes(event) || data.length === 0) fail("事件类型无效。");
        let value: unknown;
        try { value = JSON.parse(data.join("\n")); }
        catch (reason) { if (reason instanceof SyntaxError) fail("事件正文不是有效 JSON。"); throw reason; }
        const payload = record(value, ["activityId", "generationId", "stepNo", "status", "totalUnits", "completedUnits", "units", "errorCode", ...(event === "planning_completed" ? ["step"] : [])]);
        const { step, ...snapshot } = payload;
        const progress = parsePlanningGenerationProgress(snapshot, activityId, stepNo);
        if (progress.status !== (event === "planning_progress" ? "running" : event === "planning_completed" ? "completed" : "failed")) fail("事件与状态不一致。");
        checkPlanningProgressTransition(previous, progress);
        previous = progress;
        onProgress(progress);
        if (event === "planning_completed") {
          completedStep = parseActivityStep(step, activityId);
          if (completedStep.stepNo !== stepNo || completedStep.status !== "review") fail("完成事件未保存当前步骤草稿。");
        } else if (event === "planning_failed") failureCode = progress.errorCode!;
      }
      if (done) { streamEnded = true; break; }
    }
    if (buffer.trim()) fail("进度流事件不完整。");
    if (failureCode) throw new ApiError(422, failureCode, { detail: { code: failureCode } });
    if (!completedStep) throw new ApiError(502, "策划生成进度连接中断，请刷新查看实际状态。", { detail: { code: "GENERATION_INTERRUPTED" } });
    return completedStep;
  } catch (reason) {
    if (!streamEnded && !(reason instanceof DOMException && reason.name === "AbortError")) {
      try { await reader.cancel(); }
      catch (cancelReason) {
        // Keep the actual contract/domain failure primary, while retaining cancellation diagnostics.
        if (reason instanceof Error) Object.defineProperty(reason, "streamCancellationError", { value: cancelReason });
        console.error("Planning stream cancellation failed", cancelReason);
      }
    }
    throw reason;
  } finally {
    reader.releaseLock();
  }
}
