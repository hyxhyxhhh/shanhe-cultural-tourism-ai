import { ActivityContractError, parseActivityStep } from "@/lib/api/activity-contract";
import { ApiError } from "@/lib/api/client";
import type { ActivityStep } from "@/lib/types/activity";
import type { ResearchGenerationProgress, ResearchScope } from "@/lib/types/activity-agent";

const scopeOrder = ["weather", "holiday", "similar_events", "public_trend"];
const scopes = new Set(scopeOrder);
const scopeStatuses = new Set(["waiting", "running", "completed", "failed", "cancelled"]);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function fail(message: string): never { throw new ActivityContractError(`分范围归纳数据异常：${message}`); }
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

export function parseResearchGenerationProgress(value: unknown, activityId: string): ResearchGenerationProgress {
  const item = record(value, ["activityId", "generationId", "status", "totalScopes", "completedScopes", "scopes", "errorCode"]);
  if (item.activityId !== activityId || !uuid.test(activityId)) fail("活动标识不一致。");
  if (typeof item.generationId !== "string" || !uuid.test(item.generationId)) fail("生成标识无效。");
  if (!["running", "completed", "failed"].includes(item.status as string)) fail("生成状态无效。");
  if (!Array.isArray(item.scopes)) fail("缺少范围列表。");
  const entries = item.scopes.map((value) => {
    const entry = record(value, ["scope", "status", "sourceCount"]);
    if (typeof entry.scope !== "string" || !scopes.has(entry.scope)) fail("搜索范围无效。");
    if (typeof entry.status !== "string" || !scopeStatuses.has(entry.status)) fail("范围状态无效。");
    return { scope: entry.scope as ResearchScope, status: entry.status as ResearchGenerationProgress["scopes"][number]["status"], sourceCount: integer(entry.sourceCount, 1) };
  });
  const totalScopes = integer(item.totalScopes, 1);
  const completedScopes = integer(item.completedScopes);
  if (totalScopes > 4 || totalScopes !== entries.length || new Set(entries.map((entry) => entry.scope)).size !== totalScopes) fail("范围数量不一致。");
  if (entries.some((entry, index) => index > 0 && scopeOrder.indexOf(entry.scope) <= scopeOrder.indexOf(entries[index - 1].scope))) fail("范围顺序无效。");
  if (completedScopes !== entries.filter((entry) => entry.status === "completed").length) fail("已完成数量不一致。");
  if (entries.some((entry, index) => entry.status === "completed" && index >= completedScopes)) fail("完成范围必须依次执行。");
  if (entries.filter((entry) => entry.status === "running").length > 1) fail("范围必须依次归纳。");
  if (entries.some((entry, index) => entry.status === "running" && index !== completedScopes)) fail("运行范围必须为下一个待完成范围。");
  if (item.status === "completed" && completedScopes !== totalScopes) fail("尚未完成全部范围。");
  if (item.status === "running" && entries.some((entry) => entry.status === "failed" || entry.status === "cancelled")) fail("运行状态包含终止范围。");
  if (item.status === "failed") {
    if (typeof item.errorCode !== "string" || !item.errorCode.trim()) fail("失败缺少错误码。");
    if (entries.some((entry) => entry.status === "running" || entry.status === "waiting")) fail("终止后仍有执行范围。");
    const unfinished = entries.slice(completedScopes);
    if (unfinished.filter((entry) => entry.status === "failed").length > 1 || unfinished.some((entry, index) => entry.status === "failed" && index !== 0)) fail("失败范围必须是首个未完成范围。");
  } else if (Object.hasOwn(item, "errorCode")) fail("非失败状态包含错误码。");
  return { activityId, generationId: item.generationId, status: item.status as ResearchGenerationProgress["status"], totalScopes, completedScopes, scopes: entries, ...(item.status === "failed" ? { errorCode: item.errorCode as string } : {}) };
}

export function parseResearchGenerationEnvelope(value: unknown, activityId: string): ResearchGenerationProgress | null {
  const envelope = record(value, ["activityId", "progress"]);
  if (envelope.activityId !== activityId || !Object.hasOwn(envelope, "progress")) fail("进度响应无效。");
  return envelope.progress === null ? null : parseResearchGenerationProgress(envelope.progress, activityId);
}

export function checkResearchProgressTransition(previous: ResearchGenerationProgress | null, next: ResearchGenerationProgress) {
  if (!previous) {
    if (next.status !== "running" || next.completedScopes !== 0 || next.scopes.some((entry) => entry.status !== "waiting")) fail("缺少开始事件。");
    return;
  }
  if (previous.status !== "running" || previous.generationId !== next.generationId || previous.activityId !== next.activityId || previous.totalScopes !== next.totalScopes) fail("生成顺序不一致。");
  for (let index = 0; index < previous.scopes.length; index++) {
    const before = previous.scopes[index];
    const after = next.scopes[index];
    if (before.scope !== after.scope || before.sourceCount !== after.sourceCount) fail("归纳范围发生变化。");
    const allowed = before.status === "waiting" ? ["waiting", "running", "cancelled"] : before.status === "running" ? ["running", "completed", "failed", "cancelled"] : [before.status];
    if (!allowed.includes(after.status)) fail("范围状态回退或跳跃。");
  }
}

/** POST SSE is consumed as bytes arrive; no fabricated progress or implicit retry. */
export async function consumeResearchGenerationStream(response: Response, activityId: string, onProgress: (progress: ResearchGenerationProgress) => void): Promise<ActivityStep> {
  if (!response.ok) {
    const payload: unknown = await response.json();
    throw new ApiError(response.status, `归纳请求失败（${response.status}）`, payload);
  }
  if (!response.headers.get("content-type")?.startsWith("text/event-stream") || !response.body) fail("服务未返回进度流。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  let previous: ResearchGenerationProgress | null = null;
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
        if (!event || !["research_progress", "research_completed", "research_failed"].includes(event) || data.length === 0) fail("事件类型无效。");
        let value: unknown;
        try { value = JSON.parse(data.join("\n")); }
        catch (reason) { if (reason instanceof SyntaxError) fail("事件正文不是有效 JSON。"); throw reason; }
        const payload = record(value, ["activityId", "generationId", "status", "totalScopes", "completedScopes", "scopes", "errorCode", ...(event === "research_completed" ? ["step"] : [])]);
        const { step, ...snapshot } = payload;
        const progress = parseResearchGenerationProgress(snapshot, activityId);
        if (progress.status !== (event === "research_progress" ? "running" : event === "research_completed" ? "completed" : "failed")) fail("事件与状态不一致。");
        checkResearchProgressTransition(previous, progress);
        previous = progress;
        onProgress(progress);
        if (event === "research_completed") {
          completedStep = parseActivityStep(step, activityId);
          if (completedStep.stepNo !== 2 || completedStep.status !== "review") fail("完成事件未保存第二步草稿。");
        } else if (event === "research_failed") failureCode = progress.errorCode!;
      }
      if (done) { streamEnded = true; break; }
    }
    if (buffer.trim()) fail("进度流事件不完整。");
    if (failureCode) throw new ApiError(422, failureCode, { detail: { code: failureCode } });
    if (!completedStep) throw new ApiError(502, "归纳进度连接中断，请刷新查看实际状态。", { detail: { code: "GENERATION_INTERRUPTED" } });
    return completedStep;
  } catch (reason) {
    if (!streamEnded && !(reason instanceof DOMException && reason.name === "AbortError")) {
      try { await reader.cancel(); }
      catch (cancelReason) {
        // Keep the actual contract/domain failure primary, while retaining cancellation diagnostics.
        if (reason instanceof Error) Object.defineProperty(reason, "streamCancellationError", { value: cancelReason });
        console.error("Research stream cancellation failed", cancelReason);
      }
    }
    throw reason;
  } finally {
    reader.releaseLock();
  }
}
