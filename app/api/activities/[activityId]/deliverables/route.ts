import {
  jsonRequest,
  parseEmptyObjectRequest,
  proxyAuthenticated,
  resolveAgentActivityRoute,
  type AgentActivityRouteContext
} from "@/app/api/activities/_lib/agent-route";

function deliverablesPath(activityId: string) {
  return `/api/activities/${encodeURIComponent(activityId)}/deliverables`;
}

export async function GET(_request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  return proxyAuthenticated(deliverablesPath(route.value.activityId));
}

export async function POST(request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  const body = await parseEmptyObjectRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    `${deliverablesPath(route.value.activityId)}/generate`,
    jsonRequest("POST", body.value)
  );
}
