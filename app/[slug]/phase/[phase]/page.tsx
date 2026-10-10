import { notFound } from "next/navigation";
import { AgentWorkbench } from "@/components/agent/agent-workbench";
import { professionalAgents } from "@/mocks/professional-agents";
import { eventAgent } from "@/mocks/event-agent";

export default async function AgentPhasePage({ params }: { params: Promise<{ slug: string; phase: string }> }) {
  const { slug, phase } = await params;
  const data = slug === eventAgent.id || slug === "event-agent" ? eventAgent : professionalAgents[slug];
  const phaseNumber = Number(phase);
  if (!data || !Number.isInteger(phaseNumber) || phaseNumber < 1 || phaseNumber > data.phases.length) notFound();
  return <AgentWorkbench data={data} initialPhase={phaseNumber} />;
}
