"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Plus, RefreshCw, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { fieldClass, isoToLocalInput, labelClass, localInputToIso, readableError } from "@/components/activity/activity-ui";
import { executionApi } from "@/lib/api/execution";
import type { ExecutionTask, ExecutionTaskInput, ExecutionTaskStatus, ExecutionTaskUpdateInput } from "@/lib/types/activity-agent";

const STATUS_LABELS: Record<ExecutionTaskStatus, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  ready: "待执行",
  in_progress: "执行中",
  blocked: "已阻塞",
  completed: "已完成"
};

const EDITABLE_STATUSES: ExecutionTaskStatus[] = ["ready", "in_progress", "blocked", "completed"];

interface TaskDraft {
  owner: string;
  dueAt: string;
  status: ExecutionTaskStatus;
}

function draftFromTask(task: ExecutionTask): TaskDraft {
  return {
    owner: task.owner ?? "",
    dueAt: task.dueAt ? isoToLocalInput(task.dueAt) ?? "" : "",
    status: task.status
  };
}

function draftMap(tasks: ExecutionTask[]) {
  return Object.fromEntries(tasks.map((task) => [task.id, draftFromTask(task)]));
}

export function ActivityExecutionTasks({ activityId, writable }: { activityId: string; writable: boolean }) {
  const [tasks, setTasks] = useState<ExecutionTask[]>([]);
  const [drafts, setDrafts] = useState<Record<string, TaskDraft>>({});
  const [loading, setLoading] = useState(true);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", owner: "", dueAt: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await executionApi.list(activityId);
      setTasks(next);
      setDrafts(draftMap(next));
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setLoading(false);
    }
  }, [activityId]);

  useEffect(() => {
    let active = true;
    executionApi.list(activityId).then((next) => {
      if (!active) return;
      setTasks(next);
      setDrafts(draftMap(next));
    }).catch((reason: unknown) => {
      if (active) toast.error(readableError(reason));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [activityId]);

  async function createTask() {
    const title = form.title.trim();
    if (!title) {
      toast.error("任务名称不能为空");
      return;
    }
    const payload: ExecutionTaskInput = { title };
    if (form.description.trim()) payload.description = form.description.trim();
    if (form.owner.trim()) payload.owner = form.owner.trim();
    if (form.dueAt) payload.dueAt = localInputToIso(form.dueAt);
    setCreating(true);
    try {
      await executionApi.create(activityId, payload);
      setForm({ title: "", description: "", owner: "", dueAt: "" });
      await load();
      toast.success("执行任务草稿已创建");
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setCreating(false);
    }
  }

  async function saveTask(task: ExecutionTask) {
    const draft = drafts[task.id];
    if (!draft) return;
    const payload: ExecutionTaskUpdateInput = {};
    const originalOwner = task.owner ?? "";
    if (draft.owner !== originalOwner) payload.owner = draft.owner.trim() ? draft.owner.trim() : null;
    const originalDueAt = task.dueAt ? isoToLocalInput(task.dueAt) ?? "" : "";
    if (draft.dueAt !== originalDueAt) payload.dueAt = draft.dueAt ? localInputToIso(draft.dueAt) : null;
    if (draft.status !== task.status) payload.status = draft.status;
    if (!Object.keys(payload).length) return;

    setBusyTaskId(task.id);
    try {
      await executionApi.update(activityId, task.id, payload);
      await load();
      toast.success("执行任务已更新");
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setBusyTaskId(null);
    }
  }

  async function confirmTask(task: ExecutionTask) {
    setBusyTaskId(task.id);
    try {
      await executionApi.confirm(activityId, task.id);
      await load();
      toast.success("执行任务已确认，进入待执行状态");
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setBusyTaskId(null);
    }
  }

  return (
    <section className="border-t border-line">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-ink">执行任务表</h3>
          <p className="mt-1 text-[10px] text-moss">{tasks.length} 项任务</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading || busyTaskId !== null || creating} title="刷新执行任务">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          刷新
        </Button>
      </div>

      {writable ? (
        <div className="border-t border-line bg-[#f8f9f7] px-5 py-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <label className={labelClass}>任务名称
              <input className={fieldClass} value={form.title} maxLength={300} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </label>
            <label className={labelClass}>负责人
              <input className={fieldClass} value={form.owner} maxLength={200} onChange={(event) => setForm({ ...form, owner: event.target.value })} />
            </label>
            <label className={labelClass}>截止时间
              <input type="datetime-local" className={fieldClass} value={form.dueAt} onChange={(event) => setForm({ ...form, dueAt: event.target.value })} />
            </label>
            <label className={labelClass}>任务说明
              <textarea className={`${fieldClass} min-h-20 resize-y`} value={form.description} maxLength={5000} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
          </div>
          <div className="mt-4 flex justify-end">
            <Button size="sm" onClick={() => void createTask()} disabled={creating || busyTaskId !== null}>
              {creating ? <RefreshCw size={12} className="animate-spin" /> : <Plus size={12} />}
              创建任务草稿
            </Button>
          </div>
        </div>
      ) : null}

      {loading && !tasks.length ? (
        <div className="px-5 py-10 text-center text-xs text-moss">正在加载执行任务…</div>
      ) : tasks.length ? (
        <div className="divide-y divide-line border-t border-line">
          {tasks.map((task) => {
            const draft = drafts[task.id] ?? draftFromTask(task);
            const statusOptions: readonly ExecutionTaskStatus[] = task.status === "pending_confirmation"
              ? ["pending_confirmation"]
              : EDITABLE_STATUSES;
            const changed = draft.owner !== (task.owner ?? "")
              || draft.dueAt !== (task.dueAt ? isoToLocalInput(task.dueAt) ?? "" : "")
              || draft.status !== task.status;
            const busy = busyTaskId === task.id;
            return (
              <div key={task.id} className="px-5 py-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-ink">{task.title}</div>
                    {task.description ? <p className="mt-1 break-words text-[10px] leading-5 text-moss">{task.description}</p> : null}
                  </div>
                  <span className="rounded-full bg-mist px-2 py-1 text-[10px] font-medium text-pine">{STATUS_LABELS[task.status]}</span>
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_220px_180px]">
                  <label className={labelClass}>负责人
                    <input className={fieldClass} disabled={!writable || busy} value={draft.owner} maxLength={200} onChange={(event) => setDrafts({ ...drafts, [task.id]: { ...draft, owner: event.target.value } })} />
                  </label>
                  <label className={labelClass}>截止时间
                    <input type="datetime-local" className={fieldClass} disabled={!writable || busy} value={draft.dueAt} onChange={(event) => setDrafts({ ...drafts, [task.id]: { ...draft, dueAt: event.target.value } })} />
                  </label>
                  <label className={labelClass}>状态
                    <select
                      className={fieldClass}
                      disabled={!writable || busy || task.status === "pending_confirmation"}
                      value={draft.status}
                      onChange={(event) => setDrafts({ ...drafts, [task.id]: { ...draft, status: event.target.value as ExecutionTaskStatus } })}
                    >
                      {statusOptions.map((status) => (
                        <option key={status} value={status}>{STATUS_LABELS[status]}</option>
                      ))}
                    </select>
                  </label>
                </div>
                {writable ? (
                  <div className="mt-4 flex flex-wrap justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => void saveTask(task)} disabled={!changed || busy || busyTaskId !== null}>
                      {busy ? <RefreshCw size={12} className="animate-spin" /> : <Save size={12} />}
                      保存任务
                    </Button>
                    {task.status === "pending_confirmation" ? (
                      <Button size="sm" onClick={() => void confirmTask(task)} disabled={busy || busyTaskId !== null || changed}>
                        {busy ? <RefreshCw size={12} className="animate-spin" /> : <Check size={12} />}
                        确认待执行
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="border-t border-line px-5 py-10 text-center text-xs text-moss">暂无执行任务</div>
      )}
    </section>
  );
}
