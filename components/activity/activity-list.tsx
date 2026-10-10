"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Archive, ArrowRight, CalendarDays, MapPin, Pause, Play, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { activitiesApi } from "@/lib/api/activities";
import { ActivityContractError } from "@/lib/api/activity-contract";
import type { Activity, ActivityBriefInput, CreateActivityRequest } from "@/lib/types/activity";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { LoginAgainLink } from "@/components/access/login-again-link";
import {
  ACTIVITY_STATUS_LABELS,
  activityStatusClass,
  fieldClass,
  isAuthenticationError,
  labelClass,
  localInputToIso,
  readableError
} from "@/components/activity/activity-ui";

const EMPTY_FORM = {
  planningMode: "single" as "single" | "annual",
  annualPeriod: "",
  annualGoals: "",
  plannedEventCount: "",
  title: "",
  idea: "",
  location: "",
  plannedStartAt: "",
  plannedEndAt: "",
  target: "",
  budgetMin: "",
  budgetMax: "",
  targetAudience: "",
  knownConstraints: ""
};

function compactBrief(form: typeof EMPTY_FORM): ActivityBriefInput {
  const brief: ActivityBriefInput = { idea: form.idea.trim(), planningMode: form.planningMode };
  if (form.planningMode === "annual") {
    brief.annualPeriod = form.annualPeriod.trim();
    brief.annualGoals = form.annualGoals.trim();
    brief.plannedEventCount = Number(form.plannedEventCount);
  }
  if (form.location.trim()) brief.location = form.location.trim();
  const plannedStartAt = localInputToIso(form.plannedStartAt);
  const plannedEndAt = localInputToIso(form.plannedEndAt);
  if (plannedStartAt) brief.plannedStartAt = plannedStartAt;
  if (plannedEndAt) brief.plannedEndAt = plannedEndAt;
  if (form.target.trim()) brief.target = form.target.trim();
  if (form.budgetMin !== "") brief.budgetMin = Number(form.budgetMin);
  if (form.budgetMax !== "") brief.budgetMax = Number(form.budgetMax);
  if (form.targetAudience.trim()) brief.targetAudience = form.targetAudience.trim();
  if (form.knownConstraints.trim()) brief.knownConstraints = form.knownConstraints.trim();
  return brief;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new ActivityContractError("活动日期不符合已确认的数据契约。");
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

export function ActivityList() {
  const router = useRouter();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Activity | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);

  async function loadActivities() {
    setLoading(true);
    setError(null);
    setSessionExpired(false);
    try {
      setActivities(await activitiesApi.list());
    } catch (reason) {
      setError(readableError(reason));
      setSessionExpired(isAuthenticationError(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    activitiesApi.list().then((items) => {
      if (active) setActivities(items);
    }).catch((reason: unknown) => {
      if (active) {
        setError(readableError(reason));
        setSessionExpired(isAuthenticationError(reason));
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  async function createActivity() {
    const title = form.title.trim();
    const idea = form.idea.trim();
    if (!title || !idea) {
      toast.error("请填写活动名称和基础想法");
      return;
    }
    if (form.planningMode === "annual" && (!form.annualPeriod.trim() || !form.annualGoals.trim() || !Number.isInteger(Number(form.plannedEventCount)) || Number(form.plannedEventCount) < 2 || Number(form.plannedEventCount) > 12)) {
      toast.error("请填写年度周期、年度目标及 2 至 12 场计划活动数量");
      return;
    }
    const minimum = form.budgetMin === "" ? null : Number(form.budgetMin);
    const maximum = form.budgetMax === "" ? null : Number(form.budgetMax);
    if ((minimum !== null && minimum < 0) || (maximum !== null && maximum < 0)) {
      toast.error("预算不能小于 0");
      return;
    }
    if (minimum !== null && maximum !== null && minimum > maximum) {
      toast.error("预算下限不能高于预算上限");
      return;
    }
    if (form.plannedStartAt && form.plannedEndAt && new Date(form.plannedStartAt) > new Date(form.plannedEndAt)) {
      toast.error("结束时间不能早于开始时间");
      return;
    }

    setCreating(true);
    try {
      const request: CreateActivityRequest = {
        title,
        input: compactBrief(form)
      };
      const activity = await activitiesApi.create(request);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast.success("活动任务已创建");
      router.push(`/event-agent/${activity.id}`);
    } catch (reason) {
      if (isAuthenticationError(reason)) {
        setError(readableError(reason));
        setSessionExpired(true);
      } else {
        toast.error(readableError(reason));
      }
    } finally {
      setCreating(false);
    }
  }

  async function changeStatus(activity: Activity) {
    setBusyId(activity.id);
    try {
      if (activity.status === "paused") {
        await activitiesApi.update(activity.id, { status: "running" });
        toast.success("活动已恢复");
      } else {
        await activitiesApi.pause(activity.id);
        toast.success("活动已暂停");
      }
      await loadActivities();
    } catch (reason) {
      if (isAuthenticationError(reason)) {
        setError(readableError(reason));
        setSessionExpired(true);
      } else {
        toast.error(readableError(reason));
      }
    } finally {
      setBusyId(null);
    }
  }

  async function archiveActivity() {
    if (!archiveTarget) return;
    setBusyId(archiveTarget.id);
    try {
      await activitiesApi.archive(archiveTarget.id);
      setActivities((items) => items.filter((item) => item.id !== archiveTarget.id));
      setArchiveTarget(null);
      toast.success("活动已归档");
    } catch (reason) {
      if (isAuthenticationError(reason)) {
        setError(readableError(reason));
        setSessionExpired(true);
      } else {
        toast.error(readableError(reason));
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">EVENT PLANNING</div>
          <h1 className="mt-2 text-xl font-semibold text-ink">活动策划工作台</h1>
          <p className="mt-1 text-xs text-moss">管理活动任务、策划步骤与确认进度</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void loadActivities()} disabled={loading}>
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            刷新
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus size={14} />
            新建活动
          </Button>
        </div>
      </header>

      {error ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#e5c9c3] bg-white px-5 py-4">
          <span className="text-xs text-[#9b4d42]">{error}</span>
          {sessionExpired ? (
            <LoginAgainLink />
          ) : (
            <Button variant="outline" size="sm" onClick={() => void loadActivities()}>重新加载</Button>
          )}
        </div>
      ) : null}

      <section className="overflow-hidden rounded-lg border border-line bg-white shadow-card">
        <div className="hidden grid-cols-[minmax(0,1fr)_120px_150px_230px] gap-4 border-b border-line bg-mist px-5 py-3 text-[10px] font-medium text-moss md:grid">
          <span>活动任务</span>
          <span>状态</span>
          <span>更新时间</span>
          <span className="text-right">操作</span>
        </div>
        {loading ? (
          <div className="space-y-1 p-4">
            {[1, 2, 3].map((item) => <div key={item} className="loading-shimmer h-16 rounded" />)}
          </div>
        ) : activities.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <h2 className="text-sm font-semibold text-ink">暂无活动任务</h2>
            <p className="mt-2 text-xs text-moss">创建首个活动后，策划进度将在这里持续保存。</p>
            <Button className="mt-5" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus size={14} />
              新建活动
            </Button>
          </div>
        ) : (
          <div className="divide-y divide-line">
            {activities.map((activity) => (
              <div key={activity.id} className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1fr)_120px_150px_230px] md:items-center">
                <div className="min-w-0">
                  <Link href={`/event-agent/${activity.id}`} className="font-medium text-ink hover:text-pine hover:underline">
                    {activity.title}
                  </Link>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-moss">
                    <span>当前第 {activity.currentStep} 步</span>
                    <span className="inline-flex items-center gap-1"><MapPin size={10} />{activity.input.location || "地点待补充"}</span>
                    <span className="inline-flex items-center gap-1"><CalendarDays size={10} />{activity.input.plannedStartAt ? formatDate(activity.input.plannedStartAt) : "时间待补充"}</span>
                  </div>
                </div>
                <div><span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-medium ${activityStatusClass(activity.status)}`}>{ACTIVITY_STATUS_LABELS[activity.status]}</span></div>
                <div className="text-[10px] text-moss">{formatDate(activity.updatedAt)}</div>
                <div className="flex flex-wrap justify-start gap-1.5 md:justify-end">
                  {(activity.status === "draft" || activity.status === "running" || activity.status === "paused") ? (
                    <Button variant="outline" size="sm" onClick={() => void changeStatus(activity)} disabled={busyId === activity.id}>
                      {activity.status === "paused" ? <Play size={12} /> : <Pause size={12} />}
                      {activity.status === "paused" ? "恢复" : "暂停"}
                    </Button>
                  ) : null}
                  <Button variant="ghost" size="sm" onClick={() => setArchiveTarget(activity)} disabled={busyId === activity.id}>
                    <Archive size={12} />
                    归档
                  </Button>
                  <Link href={`/event-agent/${activity.id}`} className="quiet-button inline-flex h-8 items-center gap-1.5 px-3 py-0">
                    进入
                    <ArrowRight size={12} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={(open) => !creating && setCreateOpen(open)}>
        <DialogContent className="max-h-[88vh] max-w-3xl overflow-y-auto rounded-lg">
          <DialogTitle>新建活动任务</DialogTitle>
          <DialogDescription>先保存已知信息，缺失项可在活动简报中继续补充。</DialogDescription>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className={`${labelClass} sm:col-span-2`}>规划模式<select className={fieldClass} value={form.planningMode} onChange={(event) => setForm({ ...form, planningMode: event.target.value as "single" | "annual" })}><option value="single">单场活动策划</option><option value="annual">年度活动规划</option></select></label>
            {form.planningMode === "annual" ? <>
              <label className={labelClass}>年度周期 *<input className={fieldClass} value={form.annualPeriod} onChange={(event) => setForm({ ...form, annualPeriod: event.target.value })} /></label>
              <label className={labelClass}>计划活动数量（2 至 12 场） *<input type="number" min="2" max="12" className={fieldClass} value={form.plannedEventCount} onChange={(event) => setForm({ ...form, plannedEventCount: event.target.value })} /></label>
              <label className={`${labelClass} sm:col-span-2`}>年度目标 *<textarea className={`${fieldClass} min-h-20`} value={form.annualGoals} onChange={(event) => setForm({ ...form, annualGoals: event.target.value })} /></label>
            </> : null}
            <label className={`${labelClass} sm:col-span-2`}>活动名称 *
              <input className={fieldClass} value={form.title} maxLength={200} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>基础想法 *
              <textarea className={`${fieldClass} min-h-24 resize-y`} value={form.idea} onChange={(event) => setForm({ ...form, idea: event.target.value })} />
            </label>
            <label className={labelClass}>活动地点
              <input className={fieldClass} value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} />
            </label>
            <label className={labelClass}>活动目标
              <input className={fieldClass} value={form.target} onChange={(event) => setForm({ ...form, target: event.target.value })} />
            </label>
            <label className={labelClass}>计划开始时间
              <input type="datetime-local" className={fieldClass} value={form.plannedStartAt} onChange={(event) => setForm({ ...form, plannedStartAt: event.target.value })} />
            </label>
            <label className={labelClass}>计划结束时间
              <input type="datetime-local" className={fieldClass} value={form.plannedEndAt} onChange={(event) => setForm({ ...form, plannedEndAt: event.target.value })} />
            </label>
            <label className={labelClass}>预算下限（元）
              <input type="number" min="0" step="1000" className={fieldClass} value={form.budgetMin} onChange={(event) => setForm({ ...form, budgetMin: event.target.value })} />
            </label>
            <label className={labelClass}>预算上限（元）
              <input type="number" min="0" step="1000" className={fieldClass} value={form.budgetMax} onChange={(event) => setForm({ ...form, budgetMax: event.target.value })} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>目标客群
              <input className={fieldClass} value={form.targetAudience} onChange={(event) => setForm({ ...form, targetAudience: event.target.value })} />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>已知约束
              <textarea className={`${fieldClass} min-h-20 resize-y`} value={form.knownConstraints} onChange={(event) => setForm({ ...form, knownConstraints: event.target.value })} />
            </label>
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>取消</Button>
            <Button onClick={() => void createActivity()} disabled={creating}>
              {creating ? <RefreshCw size={13} className="animate-spin" /> : <Plus size={13} />}
              {creating ? "创建中" : "创建活动"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(archiveTarget)} onOpenChange={(open) => !open && busyId === null && setArchiveTarget(null)}>
        <DialogContent className="max-w-md rounded-lg">
          <DialogTitle>确认归档活动</DialogTitle>
          <DialogDescription>归档后活动将从默认列表中移除，现有步骤和版本记录仍会保留。</DialogDescription>
          <div className="mt-5 rounded-md border border-line bg-mist px-4 py-3 text-sm font-medium text-ink">{archiveTarget?.title}</div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setArchiveTarget(null)} disabled={busyId !== null}>取消</Button>
            <Button onClick={() => void archiveActivity()} disabled={busyId !== null}>
              <Archive size={13} />
              {busyId ? "归档中" : "确认归档"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
