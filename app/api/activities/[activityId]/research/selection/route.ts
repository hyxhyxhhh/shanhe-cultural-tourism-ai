import {
  proxyAuthenticated,
  resolveAgentActivityRoute,
  type AgentActivityRouteContext
} from "@/app/api/activities/_lib/agent-route";

export async function GET(_request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  return proxyAuthenticated(
    `/api/activities/${encodeURIComponent(route.value.activityId)}/research/selection`,
    { method: "GET" }
  );
}
