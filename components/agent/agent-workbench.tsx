"use client";

import { Check, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AgentPhaseContent, getPhaseSubtitle } from "@/components/agent/agent-phase-content";
import { PageHeading } from "@/components/common/page-heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { agentApi } from "@/lib/api/agents";
import type { ProfessionalAgentData } from "@/lib/types/platform";
import { delay } from "@/lib/utils";
import { useAgentStore } from "@/stores/agent-store";

const EMPTY_PHASES: number[] = [];

export function AgentWorkbench({ data, initialPhase }: { data: ProfessionalAgentData; initialPhase?: number }) {
  const router = useRouter();
  const routeSlug = data.id === "event-planning" ? "event-agent" : data.id;
  const [fields, setFields] = useState<Record<string, string>>(() => Object.fromEntries(data.fields.map((field) => [field.label, field.value])));
  const [submitting, setSubmitting] = useState(false);
  const currentRunId = useAgentStore((state) => state.currentRunByAgent[data.id]);
  const currentRun = useAgentStore((state) => currentRunId ? state.runs[currentRunId] : undefined);
  const selectedPhase = useAgentStore((state) => state.selectedPhaseByAgent[data.id] ?? 0);
  const completedPhases = useAgentStore((state) => state.completedPhasesByAgent[data.id] ?? EMPTY_PHASES);
  const setRun = useAgentStore((state) => state.setRun);
  const setSelectedPhase = useAgentStore((state) => state.setSelectedPhase);
  const markPhaseComplete = useAgentStore((state) => state.markPhaseComplete);
  const resetAgentFlow = useAgentStore((state) => state.resetAgentFlow);
  const routePhase = initialPhase === undefined ? undefined : Math.min(Math.max(initialPhase - 1, 0), data.phases.length - 1);
  const activePhase = routePhase ?? selectedPhase;
  const isLastPhase = activePhase === data.phases.length - 1;
  const currentComplete = completedPhases.includes(activePhase);

  useEffect(() => {
    if (initialPhase === undefined) return;
    const phase = Math.min(Math.max(initialPhase - 1, 0), data.phases.length - 1);
    setSelectedPhase(data.id, phase);
  }, [data.id, data.phases.length, initialPhase, setSelectedPhase]);

  const completeCurrentPhase = async () => {
    setSubmitting(true);
    try {
      let run = currentRun;
      if (!run || run.status === "cancelled" || run.status === "failed") {
        run = await agentApi.run(data.id, { fields, phases: data.phases });
        setRun(run);
      }
      await delay(activePhase === 0 ? 650 : 350);
      const updated = await agentApi.completePhase(data.id, run.id, activePhase);
      setRun(updated);
      markPhaseComplete(data.id, activePhase);
      if (!isLastPhase) {
        setSelectedPhase(data.id, activePhase + 1);
        router.push(`/${routeSlug}/phase/${activePhase + 2}`);
        toast.success(`${data.phases[activePhase]}已完成，进入${data.phases[activePhase + 1]}`);
      } else {
        toast.success("九步流程已完成");
      }
    } catch {
      toast.error("本阶段执行失败，请检查 Mock API");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    resetAgentFlow(data.id);
    setFields(Object.fromEntries(data.fields.map((field) => [field.label, field.value])));
    toast.info("九步流程已重置");
  };

  const actionLabel = activePhase === 0
    ? `运行${data.title}`
    : isLastPhase
      ? currentComplete ? "保存复盘修改" : "完成九步流程"
      : currentComplete ? "保存修改并进入下一步" : `确认${data.phases[selectedPhase]}并进入下一步`;
  const completeness = currentRun?.status === "completed" ? 100 : 70;

  return <div>
    <PageHeading title={data.title} description={data.description}/>
    <section className="relative mb-3 overflow-hidden rounded-[10px] bg-[#2d4651] px-6 py-7 text-white shadow-card sm:px-8">
      <div className="absolute right-8 top-3 select-none text-[72px] font-semibold tracking-[.15em] text-white/[.035]">AGENT</div>
      <div className="eyebrow text-[#d6bb84]">{data.title.toUpperCase()} · DATA TO DECISION</div>
      <h2 className="relative mt-3 max-w-3xl text-xl font-semibold sm:text-2xl">{data.target}</h2>
      <p className="relative mt-2 max-w-2xl text-[11px] leading-5 text-white/70">当前运行状态：{currentRun?.status === "completed" ? "已完成" : completedPhases.length > 0 ? "进行中" : "待启动"} · {data.version}</p>
      <div className="absolute right-7 top-7 text-right max-sm:hidden"><div className="text-[10px] text-white/60">当前方案完整度</div><div className="mt-1 text-4xl font-semibold text-[#d7ba76]">{completeness}%</div></div>
    </section>

    <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-9">
      {data.phases.map((phase, index) => {
        const complete = completedPhases.includes(index);
        const active = index === activePhase;
        return <button key={phase} type="button" aria-current={active ? "step" : undefined} onClick={() => { setSelectedPhase(data.id, index); router.push(`/${routeSlug}/phase/${index + 1}`); }} className={`flex min-h-[60px] flex-col items-center justify-center gap-1 rounded-md border px-2 text-center text-[10px] transition ${active ? "border-forest bg-[#294b52] text-white" : complete ? "border-[#8cb4a4] bg-white text-pine hover:border-forest" : "border-line bg-white text-moss hover:border-[#52786d] hover:bg-mist"}`}>
          <span className={`grid h-6 w-6 place-items-center rounded-full text-[9px] ${complete ? "bg-[#5d927d] text-white" : active ? "bg-white text-pine" : "border border-line bg-white text-moss"}`}>{complete ? <Check size={12}/> : index + 1}</span>
          <span className="max-w-full truncate">{phase}</span>
        </button>;
      })}
    </div>

    <Card className="overflow-hidden">
      <CardHeader className="px-6 py-5">
        <div><h3 className="text-base font-semibold">{String(activePhase + 1).padStart(2, "0")} · {data.phases[activePhase]}</h3><p className="mt-1 text-[10px] text-moss">{getPhaseSubtitle(data, activePhase)}</p></div>
        <span className="status-chip">{currentComplete ? "已完成 · 可修改" : submitting ? "执行中" : "待执行"}</span>
      </CardHeader>
      <CardContent className="p-6"><AgentPhaseContent data={data} phaseIndex={activePhase} fields={fields} onFieldChange={(label, value) => setFields((current) => ({ ...current, [label]: value }))}/></CardContent>
      <div className="flex items-center justify-between gap-4 border-t border-line bg-[#fbfcfa] px-6 py-4 max-sm:flex-col max-sm:items-stretch">
        <p className="text-[10px] leading-5 text-moss">九个步骤均可直接打开；已完成步骤可随时返回修改。</p>
        <div className="flex shrink-0 justify-end gap-2">
          {completedPhases.length > 0 && <Button variant="outline" size="sm" onClick={reset}><RotateCcw size={12}/>重置流程</Button>}
          <Button size="sm" onClick={completeCurrentPhase} disabled={submitting}>{activePhase === 0 ? <Play size={12}/> : <Check size={12}/>} {submitting ? "执行中..." : actionLabel}</Button>
        </div>
      </div>
    </Card>
  </div>;
}
