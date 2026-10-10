"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { ActivityContractError } from "@/lib/api/activity-contract";
import { activitiesApi } from "@/lib/api/activities";
import { deliverablesApi } from "@/lib/api/deliverables";
import { researchApi } from "@/lib/api/research";
import type { ResearchEvidenceSelection, ResearchGenerationProgress, ResearchScope } from "@/lib/types/activity-agent";
import type {
  Activity,
  ActivityBriefInput,
  ActivityStep,
  ActivityStepNo,
  JsonObject,
  PlanningGenerationProgress
} from "@/lib/types/activity";
import {
  ArrowLeft,
  Check,
  LockKeyhole,
  PencilLine,
  RefreshCw,
  RotateCcw,
  Save,
  Sparkles
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { LoginAgainLink } from "@/components/access/login-again-link";
import { ActivityStepEditor } from "@/components/activity/activity-step-editor";
import { ActivityExecutionTasks } from "@/components/activity/activity-execution-tasks";
import { ActivityDeliverables } from "@/components/activity/activity-deliverables";
import {
  ACTIVITY_STATUS_LABELS,
  STEP_NAMES,
  STEP_STATUS_LABELS,
  activityStatusClass,
  asObjectArray,
  asString,
  getApiErrorCode,
  isAuthenticationError,
  isoToLocalInput,
  localInputToIso,
  readableError,
  stepStatusClass
} from "@/components/activity/activity-ui";

function briefJson(brief: ActivityBriefInput): JsonObject {
  return JSON.parse(JSON.stringify({
    ...brief,
    plannedStartAt: localInputToIso(brief.plannedStartAt),
    plannedEndAt: localInputToIso(brief.plannedEndAt)
  })) as JsonObject;
}

function briefForForm(brief: ActivityBriefInput): ActivityBriefInput {
  return {
    ...brief,
    plannedStartAt: isoToLocalInput(brief.plannedStartAt),
    plannedEndAt: isoToLocalInput(brief.plannedEndAt)
  };
}

function draftSignature(
  stepNo: ActivityStepNo,
  brief: ActivityBriefInput,
  input: JsonObject,
  output: JsonObject
) {
  return JSON.stringify(stepNo === 1 ? { brief } : { input, output });
}

function stepSubtitle(step: ActivityStep) {
  if (step.status === "locked") return "等待前序步骤";
  if (step.status === "confirmed") return `版本 ${step.version} · 已确认`;
  return `版本 ${step.version}`;
}

export function ActivityWorkbench({ activityId }: { activityId: string }) {
  const router = useRouter();
  const [activity, setActivity] = useState<Activity | null>(null);
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [selectedStepNo, setSelectedStepNo] = useState<ActivityStepNo>(1);
  const [brief, setBrief] = useState<ActivityBriefInput>({ idea: "" });
  const [input, setInput] = useState<JsonObject>({});
  const [output, setOutput] = useState<JsonObject>({});
  const [baseline, setBaseline] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelError, setModelError] = useState<string | null>(null);
  const [researchNotice, setResearchNotice] = useState<string | null>(null);
  const [researchSelection, setResearchSelection] = useState<ResearchEvidenceSelection | null>(null);
  const [researchSelectionError, setResearchSelectionError] = useState<string | null>(null);
  const [researchProgress, setResearchProgress] = useState<ResearchGenerationProgress | null>(null);
  const [researchProgressError, setResearchProgressError] = useState<string | null>(null);
  const [researchRequestRunning, setResearchRequestRunning] = useState(false);
  const [planningProgress, setPlanningProgress] = useState<PlanningGenerationProgress | null>(null);
  const [planningProgressError, setPlanningProgressError] = useState<string | null>(null);
  const researchGenerationController = useRef<AbortController | null>(null);
  const researchGenerationActivity = useRef<string | null>(activityId);
  const [researchQuery, setResearchQuery] = useState("");
  const [researchScopes, setResearchScopes] = useState<ResearchScope[]>([
    "weather",
    "holiday",
    "similar_events",
    "public_trend"
  ]);
  const [deliverablesRefreshToken, setDeliverablesRefreshToken] = useState(0);

  const selectedStep = useMemo(
    () => steps.find((step) => step.stepNo === selectedStepNo) ?? null,
    [selectedStepNo, steps]
  );
  const currentSignature = selectedStep
    ? draftSignature(selectedStepNo, brief, input, output)
    : "";
  const dirty = Boolean(baseline && currentSignature !== baseline);

  useEffect(() => {
    researchGenerationActivity.current = activityId;
    return () => {
      researchGenerationActivity.current = null;
      researchGenerationController.current?.abort();
    };
  }, [activityId]);

  async function generateResearchStep(version: number) {
    if (researchGenerationActivity.current !== activityId) throw new DOMException("The research page was closed", "AbortError");
    if (researchGenerationController.current) throw new ActivityContractError("当前范围归纳仍在执行，请等待完成。");
    const controller = new AbortController();
    researchGenerationController.current = controller;
    setResearchRequestRunning(true);
    try {
      return await researchApi.generateGrouped(activityId, { version, model: selectedModel }, setResearchProgress, controller.signal);
    } finally {
      if (researchGenerationController.current === controller) researchGenerationController.current = null;
      setResearchRequestRunning(false);
    }
  }

  async function generatePlanningStep(stepNo: ActivityStepNo, version: number) {
    if (researchGenerationActivity.current !== activityId) throw new DOMException("The planning page was closed", "AbortError");
    if (researchGenerationController.current) throw new ActivityContractError("当前策划生成仍在执行，请等待完成。");
    const controller = new AbortController();
    researchGenerationController.current = controller;
    setPlanningProgress(null);
    setPlanningProgressError(null);
    try { return await activitiesApi.generatePlanning(activityId, stepNo, { version, model: selectedModel }, setPlanningProgress, controller.signal); }
    finally { if (researchGenerationController.current === controller) researchGenerationController.current = null; }
  }

  const load = useCallback(async (initial = false, followCurrentStep = false) => {
    if (initial) setLoading(true);
    else setRefreshing(true);
    setError(null);
    setSessionExpired(false);
    try {
      const nextActivity = await activitiesApi.get(activityId);
      setActivity(nextActivity);
      setSteps(nextActivity.steps);
      setMissing(false);
      if (initial || followCurrentStep) {
        setSelectedStepNo(nextActivity.currentStep);
      }
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 404) {
        setMissing(true);
      } else {
        setSessionExpired(isAuthenticationError(reason));
        if (reason instanceof ActivityContractError) {
          setActivity(null);
          setSteps([]);
          setMissing(false);
        }
        setError(readableError(reason));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activityId]);

  useEffect(() => {
    let active = true;
    activitiesApi.get(activityId).then((nextActivity) => {
      if (!active) return;
      setActivity(nextActivity);
      setSteps(nextActivity.steps);
      setMissing(false);
      setSelectedStepNo(nextActivity.currentStep);
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ApiError && reason.status === 404) setMissing(true);
      else {
        setSessionExpired(isAuthenticationError(reason));
        if (reason instanceof ActivityContractError) {
          setActivity(null);
          setSteps([]);
          setMissing(false);
        }
        setError(readableError(reason));
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [activityId]);

  useEffect(() => {
    let active = true;
    activitiesApi.listModels().then((availableModels) => {
      if (!active) return;
      setModels(availableModels);
      setModelError(null);
    }).catch((reason: unknown) => {
      if (!active) return;
      setModels([]);
      setSelectedModel("");
      setModelError(readableError(reason));
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!activity || selectedStepNo !== 2) return;
    let active = true;
    researchApi.selection(activity.id).then((selection) => {
      if (!active) return;
      setResearchSelection(selection);
      setResearchSelectionError(null);
    }).catch((reason: unknown) => {
      if (!active) return;
      setResearchSelection(null);
      setResearchSelectionError(readableError(reason));
    });
    return () => { active = false; };
  }, [activity, selectedStepNo]);

  useEffect(() => {
    if (!activity || selectedStepNo !== 2 || busyAction !== null || activity.steps.find((step) => step.stepNo === 2)?.inputJson.useWebSearch !== true) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const wasGenerating = activity.steps.find((step) => step.stepNo === 2)?.status === "generating";
    async function readProgress() {
      try {
        const progress = await researchApi.progress(activityId);
        if (!active) return;
        setResearchProgress(progress);
        setResearchProgressError(null);
        if (progress?.status === "running") timer = setTimeout(() => void readProgress(), 1500);
        else if (wasGenerating && progress) await load();
      } catch (reason) {
        if (active) {
          setResearchProgressError(readableError(reason));
          if (isAuthenticationError(reason)) setSessionExpired(true);
        }
      }
    }
    void readProgress();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [activity, activityId, selectedStepNo, busyAction, load]);

  useEffect(() => {
    const step = activity?.steps.find((item) => item.stepNo === selectedStepNo);
    if (!step || busyAction !== null || (step.stepNo === 2 && step.inputJson.useWebSearch === true)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const progress = await activitiesApi.planningProgress(activityId, selectedStepNo);
        if (!active) return;
        setPlanningProgress(progress);
        setPlanningProgressError(null);
        if (progress?.status === "running") timer = setTimeout(() => void poll(), 1500);
        else if (step?.status === "generating" && progress) await load();
      } catch (reason) { if (active) { setPlanningProgressError(readableError(reason)); if (isAuthenticationError(reason)) setSessionExpired(true); } }
    }
    void poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [activity, activityId, selectedStepNo, busyAction, load]);

  useEffect(() => {
    if (!activity || !selectedStep) return;
    const timer = window.setTimeout(() => {
      const nextBrief = briefForForm(activity.input);
      const nextInput = { ...selectedStep.inputJson };
      const nextOutput = { ...selectedStep.outputJson };
      setBrief(nextBrief);
      setInput(nextInput);
      setOutput(nextOutput);
      setBaseline(draftSignature(selectedStep.stepNo, nextBrief, nextInput, nextOutput));
      if (selectedStep.stepNo === 2) {
        setResearchQuery((current) => {
          if (current) return current;
          const defaultQuery = [activity.title, activity.input.location].filter(Boolean).join(" ");
          return defaultQuery.length <= 70 ? defaultQuery : "";
        });
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activity, selectedStep]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function selectStep(stepNo: ActivityStepNo) {
    if (stepNo === selectedStepNo) return;
    if (dirty && !window.confirm("当前步骤有未保存修改，确定切换吗？")) return;
    setSelectedStepNo(stepNo);
  }

  async function handleConflict(reason: unknown) {
    if (reason instanceof ApiError && reason.status === 409 && getApiErrorCode(reason) === "VERSION_CONFLICT") {
      await load();
      toast.warning("内容已被更新，已加载最新版本");
      return true;
    }
    return false;
  }

  function handleAuthenticationFailure(reason: unknown) {
    if (!isAuthenticationError(reason)) return false;
    setSessionExpired(true);
    setError(readableError(reason));
    return true;
  }

  async function saveDraft() {
    if (!activity || !selectedStep) return;
    if (selectedStep.stepNo === 1) {
      if (!brief.idea.trim()) {
        toast.error("基础想法不能为空");
        return;
      }
      if (brief.planningMode === "annual" && (!brief.annualPeriod?.trim() || !brief.annualGoals?.trim() || !Number.isInteger(brief.plannedEventCount) || Number(brief.plannedEventCount) < 2 || Number(brief.plannedEventCount) > 12)) {
        toast.error("请填写年度周期、目标及 2 至 12 场计划活动数量");
        return;
      }
      if (brief.budgetMin !== undefined && brief.budgetMax !== undefined && brief.budgetMin > brief.budgetMax) {
        toast.error("预算下限不能高于预算上限");
        return;
      }
      if (brief.plannedStartAt && brief.plannedEndAt && new Date(brief.plannedStartAt) > new Date(brief.plannedEndAt)) {
        toast.error("结束时间不能早于开始时间");
        return;
      }
    }
    setBusyAction("save");
    try {
      if (selectedStep.stepNo === 1) {
        await activitiesApi.updateStep(activity.id, selectedStep.stepNo, {
          version: selectedStep.version,
          inputJson: briefJson(brief)
        });
      } else if (selectedStep.stepNo >= 4) {
        await activitiesApi.updateStep(activity.id, selectedStep.stepNo, {
          version: selectedStep.version,
          outputJson: output
        });
      } else {
        await activitiesApi.updateStep(activity.id, selectedStep.stepNo, {
          version: selectedStep.version,
          inputJson: input,
          outputJson: output
        });
      }
      await load();
      toast.success("草稿已保存");
    } catch (reason) {
      if (!(await handleConflict(reason)) && !handleAuthenticationFailure(reason)) toast.error(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  }

  async function generate() {
    if (!activity || !selectedStep) return;
    if (!selectedModel) {
      setModelError("请先选择生成模型。");
      return;
    }
    if (dirty) {
      toast.error("请先保存当前修改再生成");
      return;
    }
    setBusyAction("generate");
    try {
      if (selectedStep.stepNo === 2 && input.useWebSearch === true) {
        setResearchProgress(null);
        setResearchProgressError(null);
        await generateResearchStep(selectedStep.version);
      } else {
        await generatePlanningStep(selectedStep.stepNo, selectedStep.version);
      }
      if (selectedStep.stepNo === 2) setResearchNotice(null);
      await load();
      toast.success(selectedStep.stepNo === 9 && asObjectArray(output.actualMetrics).length > 0 ? "复盘结论已生成" : "草稿已生成");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (handleAuthenticationFailure(reason)) {
        return;
      }
      if (!(await handleConflict(reason))) {
        await load();
        toast.error(readableError(reason));
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function confirm() {
    if (!activity || !selectedStep) return;
    if (dirty) {
      toast.error("请先保存当前修改再确认");
      return;
    }
    if (selectedStep.stepNo === 3 && activity.input.planningMode !== "annual") {
      const candidateIds = asObjectArray(output.candidates).map((candidate) => asString(candidate.id));
      if (typeof input.selectedThemeId !== "string" || !candidateIds.includes(input.selectedThemeId)) {
        toast.error("请选择当前候选主题中的一个方案并保存");
        return;
      }
    }
    setBusyAction("confirm");
    try {
      await activitiesApi.confirmStep(activity.id, selectedStep.stepNo, { version: selectedStep.version });
      await load(false, true);
      toast.success("步骤已确认，下一步已更新");
    } catch (reason) {
      if (!(await handleConflict(reason)) && !handleAuthenticationFailure(reason)) toast.error(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  }

  async function generateReport() {
    if (!activity || !selectedStep || selectedStep.stepNo !== 9) return;
    if (dirty) {
      toast.error("请先保存当前修改再生成报告");
      return;
    }
    setBusyAction("report");
    const needsConfirmation = ["review", "needs_review"].includes(selectedStep.status);
    try {
      if (needsConfirmation) {
        await activitiesApi.confirmStep(activity.id, 9, { version: selectedStep.version });
      }
      await deliverablesApi.generate(activity.id);
      setDeliverablesRefreshToken((current) => current + 1);
      await load();
      toast.success(
        needsConfirmation
          ? "第 9 步已确认，报告及三个成果文件已生成"
          : "报告及三个成果文件已生成新版本"
      );
    } catch (reason) {
      if (handleAuthenticationFailure(reason)) return;
      if (!(await handleConflict(reason))) {
        await load();
        toast.error(readableError(reason));
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function reopen() {
    if (!activity || !selectedStep) return;
    setBusyAction("reopen");
    try {
      await activitiesApi.reopenStep(activity.id, selectedStep.stepNo, {
        version: selectedStep.version
      });
      await load();
      toast.success("步骤已重新打开，后续步骤将等待复核");
    } catch (reason) {
      if (!(await handleConflict(reason)) && !handleAuthenticationFailure(reason)) toast.error(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  }

  async function toggleSearch(enabled: boolean) {
    if (!activity || !selectedStep || selectedStep.stepNo !== 2) return;
    if (dirty) {
      toast.error("请先保存当前修改再调整联网搜索选项");
      return;
    }
    setBusyAction("search");
    try {
      await activitiesApi.updateStep(activity.id, 2, {
        version: selectedStep.version,
        inputJson: { useWebSearch: enabled }
      });
      await load();
      toast.success(enabled ? "已选择联网搜索" : "已取消联网搜索");
    } catch (reason) {
      if (!(await handleConflict(reason)) && !handleAuthenticationFailure(reason)) toast.error(readableError(reason));
    } finally {
      setBusyAction(null);
    }
  }

  async function runResearch() {
    if (!activity || !selectedStep || selectedStep.stepNo !== 2) return;
    if (!selectedModel) {
      setModelError("请先选择生成模型。");
      toast.error("请先选择生成模型");
      return;
    }
    if (input.useWebSearch !== true) {
      toast.error("请先启用联网搜索");
      return;
    }
    if (dirty) {
      toast.error("请先保存当前修改再执行联网搜索");
      return;
    }
    if (!researchQuery || researchQuery !== researchQuery.trim() || researchQuery.length > 70) {
      toast.error("搜索主题需为 1 至 70 个字符且不能包含首尾空格");
      return;
    }
    if (researchScopes.length === 0) {
      toast.error("请至少选择一个搜索范围");
      return;
    }
    setBusyAction("research");
    setResearchNotice(null);
    setResearchProgress(null);
    setResearchProgressError(null);
    let searchCompleted = false;
    try {
      await researchApi.run(activity.id, {
        version: selectedStep.version,
        useWebSearch: true,
        query: researchQuery,
        queryScope: researchScopes
      });
      searchCompleted = true;
      setResearchNotice("联网搜索已完成，正在按搜索范围依次归纳全部资料。归纳完成前不能确认或进入下一步。");
      const latestActivity = await activitiesApi.get(activity.id);
      const latestResearchStep = latestActivity.steps.find((step) => step.stepNo === 2);
      if (!latestResearchStep) {
        throw new ActivityContractError("活动缺少第 2 步研究数据。");
      }
      await generateResearchStep(latestResearchStep.version);
      setResearchNotice(null);
      await load();
      toast.success("联网搜索与模型研判已完成");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (searchCompleted) {
        setResearchNotice("联网搜索已完成，模型归纳未完成。可点击“重试模型归纳”使用已保存的资料继续。");
      }
      if (handleAuthenticationFailure(reason)) {
        return;
      }
      if (!(await handleConflict(reason))) {
        await load();
        toast.error(readableError(reason));
      }
    } finally {
      setBusyAction(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="loading-shimmer h-20 rounded-lg" />
        <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)]">
          <div className="loading-shimmer h-[560px] rounded-lg" />
          <div className="loading-shimmer h-[560px] rounded-lg" />
        </div>
      </div>
    );
  }

  if (missing) {
    return (
      <div className="rounded-lg border border-line bg-white px-6 py-10 text-center">
        <h1 className="text-base font-semibold text-ink">未找到活动任务</h1>
        <p className="mt-2 text-xs text-moss">活动可能已归档、删除，或当前账号无权访问。</p>
        <Link href="/event-agent" className="primary-button mt-5 inline-flex items-center gap-2">
          <ArrowLeft size={14} />
          返回活动列表
        </Link>
      </div>
    );
  }

  if (!activity || !selectedStep) {
    return (
      <div role="alert" className="rounded-lg border border-[#e5c9c3] bg-white px-6 py-10 text-center">
        <h1 className="text-base font-semibold text-ink">活动数据加载失败</h1>
        <p className="mt-2 text-xs text-moss">{error ?? "请稍后重试。"}</p>
        {sessionExpired ? (
          <LoginAgainLink className="mt-5" />
        ) : (
          <Button className="mt-5" onClick={() => void load(true)}><RefreshCw size={13} />重新加载</Button>
        )}
      </div>
    );
  }

  const stepNames = activity.input.planningMode === "annual"
    ? STEP_NAMES.map((name, index) => index === 2 ? "年度活动架构" : name)
    : STEP_NAMES;
  const activityReadOnly = activity.status === "paused" || activity.status === "archived";
  const stepReadOnly = selectedStep.status === "locked" || selectedStep.status === "generating" || selectedStep.status === "confirmed";
  const editorDisabled = activityReadOnly || stepReadOnly || busyAction !== null;
  const canSave = !editorDisabled && dirty;
  const usesWebResearch = selectedStep.stepNo === 2 && input.useWebSearch === true;
  const researchGenerating = researchProgress?.status === "running"
    || (researchRequestRunning && researchProgress?.status !== "completed" && researchProgress?.status !== "failed");
  const displayedStepStatus = selectedStep.stepNo === 2 && researchGenerating ? "generating" : selectedStep.status;
  const planningGenerating = planningProgress?.stepNo === selectedStepNo && planningProgress.status === "running" || (busyAction === "generate" && !usesWebResearch && planningProgress?.status !== "failed" && planningProgress?.status !== "completed");
  const effectiveStepStatus = planningGenerating ? "generating" : displayedStepStatus;
  const canGenerate = Boolean(selectedModel) && !activityReadOnly && !busyAction && !dirty && !["locked", "generating", "confirmed"].includes(selectedStep.status);
  const canConfirm = !activityReadOnly && !busyAction && !dirty && Object.keys(output).length > 0 && ["review", "needs_review"].includes(selectedStep.status);
  const canReopen = !activityReadOnly && !busyAction && selectedStep.status === "confirmed";
  const canGenerateReport = selectedStep.stepNo === 9
    && !activityReadOnly
    && !busyAction
    && !dirty
    && ["review", "needs_review", "confirmed"].includes(selectedStep.status);
  const hasSavedActualMetrics = selectedStep.stepNo === 9 && (asObjectArray(output.actualMetrics).length > 0 || asObjectArray(output.eventPlans).some((item) => asObjectArray((item.output as JsonObject).actualMetrics).length > 0) || asObjectArray((output.annualPlan as JsonObject | undefined)?.actualMetrics).length > 0);
  const generateLabel = hasSavedActualMetrics
    ? "生成复盘结论"
    : (usesWebResearch
      ? (selectedStep.status === "failed" || researchNotice ? "重试模型归纳" : "生成模型归纳")
      : (["review", "needs_review", "failed"].includes(selectedStep.status) ? "重新生成" : "生成草稿"));

  return (
    <div className="space-y-4">
      <header className="rounded-lg border border-line bg-white px-5 py-4 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <Link href="/event-agent" className="inline-flex items-center gap-1 text-[10px] font-medium text-moss hover:text-pine">
              <ArrowLeft size={12} />
              活动列表
            </Link>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <h1 className="max-w-3xl break-words text-lg font-semibold text-ink">{activity.title}</h1>
              <span className={`rounded-full px-2 py-1 text-[10px] font-medium ${activityStatusClass((researchGenerating || planningGenerating) && !activityReadOnly ? "running" : activity.status)}`}>{researchGenerating && !activityReadOnly ? "数据研判中" : planningGenerating && !activityReadOnly ? "策划生成中" : ACTIVITY_STATUS_LABELS[activity.status]}</span>
            </div>
            <p className="mt-1 text-[10px] text-moss">当前第 {activity.currentStep} 步 · 更新于 {new Date(activity.updatedAt).toLocaleString("zh-CN")}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => {
            if (dirty && !window.confirm("当前步骤有未保存修改，确定刷新吗？")) return;
            void load();
          }} disabled={refreshing || busyAction !== null}>
            <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
            刷新
          </Button>
        </div>
        {activityReadOnly ? (
          <div className="mt-4 border-t border-line pt-3 text-xs text-[#866936]">
            {activity.status === "paused" ? "活动已暂停，恢复后可继续编辑步骤。" : "活动已归档，当前仅可查看。"}
          </div>
        ) : null}
      </header>

      {error ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#e5c9c3] bg-white px-4 py-3 text-xs text-[#9b4d42]">
          <span>{error}</span>
          {sessionExpired ? <LoginAgainLink /> : null}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)]">
        <nav className="overflow-x-auto rounded-lg border border-line bg-white p-2 shadow-card xl:overflow-visible" aria-label="活动策划步骤">
          <div className="flex min-w-max gap-2 xl:min-w-0 xl:flex-col">
            {steps.map((step) => {
              const active = step.stepNo === selectedStepNo;
              const displayedStatus = step.stepNo === 2 && researchGenerating || step.stepNo === planningProgress?.stepNo && planningProgress.status === "running" || step.stepNo === selectedStepNo && planningGenerating ? "generating" : step.status;
              return (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => selectStep(step.stepNo)}
                  className={`grid w-[220px] grid-cols-[30px_minmax(0,1fr)] gap-2 rounded-md border px-3 py-3 text-left transition xl:w-full ${active ? "border-[#7f9c93] bg-mist" : "border-transparent hover:border-line hover:bg-[#f8f9f7]"}`}
                >
                  <span className={`grid h-7 w-7 place-items-center rounded-full text-[10px] font-semibold ${active ? "bg-forest text-white" : "bg-[#edf0ee] text-moss"}`}>
                    {step.status === "locked" ? <LockKeyhole size={11} /> : step.stepNo}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs font-medium text-ink">{stepNames[step.stepNo - 1]}</span>
                    <span className="mt-1 flex items-center justify-between gap-2">
                      <span className="text-[9px] text-moss">{stepSubtitle(step)}</span>
                      <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] ${stepStatusClass(displayedStatus)}`}>{STEP_STATUS_LABELS[displayedStatus]}</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </nav>

        <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-white shadow-card">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div>
              <div className="text-[10px] font-medium text-moss">第 {selectedStep.stepNo} 步</div>
              <h2 className="mt-1 text-base font-semibold text-ink">{stepNames[selectedStep.stepNo - 1]}</h2>
              <div className="mt-1 flex items-center gap-2 text-[10px] text-moss">
                <span>版本 {selectedStep.version}</span>
                <span>·</span>
                <span>{STEP_STATUS_LABELS[effectiveStepStatus]}</span>
                {dirty ? <span className="font-medium text-[#91613c]">· 有未保存修改</span> : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <label className="flex items-center gap-2 text-xs text-moss">
                  <span>生成模型</span>
                  <select
                    className="h-8 max-w-[220px] rounded-md border border-line bg-white px-2 text-xs text-ink"
                    value={selectedModel}
                    onChange={(event) => {
                      const model = event.target.value;
                      setSelectedModel(model);
                      if (models.includes(model)) setModelError(null);
                    }}
                    disabled={busyAction !== null || models.length === 0}
                  >
                    <option value="">请选择模型</option>
                    {models.map((model) => <option key={model} value={model}>{model}</option>)}
                  </select>
              </label>
              <Button variant="outline" size="sm" onClick={() => void saveDraft()} disabled={!canSave}>
                {busyAction === "save" ? <RefreshCw size={12} className="animate-spin" /> : <Save size={12} />}
                保存草稿
              </Button>
              <Button variant="outline" size="sm" onClick={() => void generate()} disabled={!canGenerate}>
                  {busyAction === "generate" || effectiveStepStatus === "generating" ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {busyAction === "generate" || effectiveStepStatus === "generating" ? "生成中" : generateLabel}
              </Button>
              {canReopen ? (
                <Button variant="outline" size="sm" onClick={() => void reopen()} disabled={busyAction !== null}>
                  {busyAction === "reopen" ? <RefreshCw size={12} className="animate-spin" /> : <PencilLine size={12} />}
                  重新打开
                </Button>
              ) : null}
              {selectedStep.stepNo === 9 ? (
                <Button size="sm" onClick={() => void generateReport()} disabled={!canGenerateReport}>
                  {busyAction === "report" ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {busyAction === "report" ? "生成中" : "生成报告"}
                </Button>
              ) : (
                <Button size="sm" onClick={() => void confirm()} disabled={!canConfirm}>
                  {busyAction === "confirm" ? <RefreshCw size={12} className="animate-spin" /> : <Check size={12} />}
                  确认并进入下一步
                </Button>
              )}
            </div>
          </div>

          {!selectedModel ? (
            <div className="border-b border-[#ead7bd] bg-[#fbf5eb] px-5 py-3 text-xs text-[#7f5a35]">
              {modelError ?? (models.length === 0 ? "暂无可用模型，无法生成。" : "请选择模型后再生成。")}
            </div>
          ) : modelError ? (
            <div role="alert" className="border-b border-[#e5c9c3] bg-[#fbf1ef] px-5 py-3 text-xs text-[#8f493e]">{modelError}</div>
          ) : null}

          {effectiveStepStatus === "needs_review" ? (
            <div className="border-b border-[#ead7bd] bg-[#fbf5eb] px-5 py-3 text-xs text-[#7f5a35]">
              前序内容已修改，请复核当前结果后重新确认。
            </div>
          ) : null}
          {effectiveStepStatus === "failed" ? (
            <div className="border-b border-[#e5c9c3] bg-[#fbf1ef] px-5 py-3 text-xs text-[#8f493e]">
              {usesWebResearch
                ? "第 2 步模型归纳未完成。已完成搜索的资料会保留，可点击“重试模型归纳”继续；归纳成功前不能确认或进入下一步。"
                : "上次生成未完成，可检查模型服务状态后重新生成。"}
            </div>
          ) : null}
          {selectedStep.stepNo === 2 && researchNotice ? (
            <div role="status" className="border-b border-line bg-mist px-5 py-3 text-xs text-pine">{researchNotice}</div>
          ) : null}
          {planningProgressError && !usesWebResearch ? <p role="alert" className="border-b border-line px-5 py-3 text-xs text-[#8f493e]">进度读取失败：{planningProgressError}</p> : null}
          {planningProgress?.stepNo === selectedStep.stepNo && !usesWebResearch ? <PlanningGenerationStatus progress={planningProgress} stepStatus={selectedStep.status} /> : null}

          <ActivityStepEditor
            activity={activity}
            step={selectedStep}
            brief={brief}
            input={input}
            output={output}
            disabled={editorDisabled}
            onBriefChange={setBrief}
            onInputChange={setInput}
            onOutputChange={setOutput}
            onSearchToggle={(enabled) => void toggleSearch(enabled)}
            researchQuery={researchQuery}
            researchScopes={researchScopes}
            researchRunning={busyAction === "research"}
            researchSelection={researchSelection}
            researchSelectionError={researchSelectionError}
            researchProgress={researchProgress}
            researchProgressError={researchProgressError}
            onResearchQueryChange={setResearchQuery}
            onResearchScopesChange={setResearchScopes}
            onResearchRun={() => void runResearch()}
            canOpenPlanItem={selectedStep.stepNo === 3 && selectedStep.status === "confirmed" && !activityReadOnly && !dirty && !busyAction}
            onPlanItemOpen={(eventId) => {
              setBusyAction("child");
              activitiesApi.createPlanItemActivity(activity.id, eventId, selectedStep.version).then((child) => router.push(`/event-agent/${child.id}`)).catch((reason) => { if (!handleAuthenticationFailure(reason)) toast.error(readableError(reason)); }).finally(() => setBusyAction(null));
            }}
          />

          {selectedStep.stepNo === 7 ? (
            <ActivityExecutionTasks
              activityId={activity.id}
              writable={!activityReadOnly && selectedStep.status !== "locked"}
            />
          ) : null}
          {selectedStep.stepNo === 9 ? (
            <ActivityDeliverables
              activityId={activity.id}
              refreshToken={deliverablesRefreshToken}
            />
          ) : null}
        </section>
      </div>

      {dirty ? (
        <div className="sticky bottom-3 z-20 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#d9c7a3] bg-white px-4 py-3 shadow-lg">
          <span className="text-xs text-[#7f5a35]">当前步骤有未保存修改</span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => {
              setBrief(briefForForm(activity.input));
              setInput({ ...selectedStep.inputJson });
              setOutput({ ...selectedStep.outputJson });
            }} disabled={busyAction !== null}>
              <RotateCcw size={12} />
              放弃修改
            </Button>
            <Button size="sm" onClick={() => void saveDraft()} disabled={!canSave}>
              <Save size={12} />
              保存草稿
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PlanningGenerationStatus({ progress, stepStatus }: { progress: PlanningGenerationProgress; stepStatus: ActivityStep["status"] }) {
  const labels = { waiting: "等待生成", running: "生成中", completed: "已完成", failed: "失败", cancelled: "未执行" };
  const current = progress.units.find((unit) => unit.status === "running");
  return <section className="border-b border-line bg-mist px-5 py-4" aria-label="策划生成进度">
    <p role="status" className="text-xs font-medium text-pine">生成进度：{progress.completedUnits} / {progress.totalUnits} 个单元 · {Math.floor(progress.completedUnits / progress.totalUnits * 100)}%</p>
    <p className="mt-1 text-xs text-moss">{progress.status === "failed" ? "本次生成结果未保存，可手动重试。" : progress.status === "completed" ? stepStatus === "confirmed" ? "生成结果已确认。" : stepStatus === "review" ? "生成结果已保存，等待复核确认。" : "上次生成已完成，当前内容待重新生成。" : current ? `正在生成：${current.label}` : progress.completedUnits === progress.totalUnits ? "各单元已完成，正在保存草稿…" : "正在准备生成…"}</p>
    <progress className="mt-3 h-2 w-full accent-[#2f6554]" value={progress.completedUnits} max={progress.totalUnits} aria-label="已完成策划单元" />
    <ul className="mt-3 grid gap-2 sm:grid-cols-2">{progress.units.map((unit) => <li key={unit.key} className="flex justify-between gap-3 rounded border border-line bg-white px-3 py-2 text-xs"><span>{unit.label}</span><span>{labels[unit.status]}</span></li>)}</ul>
    {progress.errorCode ? <p role="alert" className="mt-3 text-xs text-[#8f493e]">{readableError(new ApiError(422, progress.errorCode, { detail: { code: progress.errorCode } }))}</p> : null}
  </section>;
}
