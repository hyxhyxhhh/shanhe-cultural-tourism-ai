import { notFound } from "next/navigation";
import { CockpitWorkspace } from "@/components/access/cockpit-workspace";
import { COCKPITS, getCockpit } from "@/lib/platform/access";
import type { CockpitId } from "@/lib/types/access";

export function generateStaticParams() {
  return COCKPITS.map((cockpit) => ({ cockpitId: cockpit.id }));
}

export default async function CockpitPage({ params }: { params: Promise<{ cockpitId: string }> }) {
  const { cockpitId } = await params;
  if (!getCockpit(cockpitId)) notFound();
  return <CockpitWorkspace cockpitId={cockpitId as CockpitId} />;
}
