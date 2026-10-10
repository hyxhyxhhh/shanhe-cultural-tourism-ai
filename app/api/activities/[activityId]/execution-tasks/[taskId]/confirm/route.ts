import {
  jsonRequest,
  parseEmptyObjectRequest,
  proxyAuthenticated,
  resolveExecutionTaskRoute,
  type ExecutionTaskRouteContext
} from "@/app/api/activities/_lib/agent-route";

export async function POST(request: Request, context: ExecutionTaskRouteContext) {
  const route = await resolveExecutionTaskRoute(context);
  if (route.response) return route.response;
  const body = await parseEmptyObjectRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    `/api/activities/${encodeURIComponent(route.value.activityId)}/execution-tasks/${encodeURIComponent(route.value.taskId)}/confirm`,
    jsonRequest("POST", body.value)
  );
}
