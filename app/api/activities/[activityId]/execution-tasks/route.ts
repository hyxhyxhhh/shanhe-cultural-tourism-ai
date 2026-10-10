import {
  jsonRequest,
  parseExecutionTaskCreateRequest,
  proxyAuthenticated,
  resolveAgentActivityRoute,
  type AgentActivityRouteContext
} from "@/app/api/activities/_lib/agent-route";

function executionTasksPath(activityId: string) {
  return `/api/activities/${encodeURIComponent(activityId)}/execution-tasks`;
}

export async function GET(_request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  return proxyAuthenticated(executionTasksPath(route.value.activityId));
}

export async function POST(request: Request, context: AgentActivityRouteContext) {
  const route = await resolveAgentActivityRoute(context);
  if (route.response) return route.response;
  const body = await parseExecutionTaskCreateRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    executionTasksPath(route.value.activityId),
    jsonRequest("POST", body.value)
  );
}
