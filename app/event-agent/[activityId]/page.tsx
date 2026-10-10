import { notFound } from "next/navigation";
import { ActivityWorkbench } from "@/components/activity/activity-workbench";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function ActivityPage({ params }: { params: Promise<{ activityId: string }> }) {
  const { activityId } = await params;
  if (!UUID_PATTERN.test(activityId)) notFound();
  return <ActivityWorkbench activityId={activityId} />;
}
