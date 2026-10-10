import {
  jsonRequest,
  parseResearchRequest,
  proxyAuthenticated,
  resolveAgentActivityRoute,
  type AgentActivityRouteContext
} from "@/app/api/activities/_lib/agent-route";

export async function POST(request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  const body = await parseResearchRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    `/api/activities/${encodeURIComponent(route.value.activityId)}/research`,
    jsonRequest("POST", body.value)
  );
}
