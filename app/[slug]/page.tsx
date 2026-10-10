import { notFound } from "next/navigation";
import { AgentWorkbench } from "@/components/agent/agent-workbench";
import { DomainPage } from "@/components/common/domain-page";
import { professionalAgents } from "@/mocks/professional-agents";
import { domainPages } from "@/mocks/domain-pages";

export default async function SlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (professionalAgents[slug]) return <AgentWorkbench data={professionalAgents[slug]}/>;
  if (domainPages[slug]) return <DomainPage data={domainPages[slug]}/>;
  notFound();
}
