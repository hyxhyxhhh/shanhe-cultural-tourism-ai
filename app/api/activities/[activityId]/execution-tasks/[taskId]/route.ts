import {
  jsonRequest,
  parseExecutionTaskUpdateRequest,
  proxyAuthenticated,
  resolveExecutionTaskRoute,
  type ExecutionTaskRouteContext
} from "@/app/api/activities/_lib/agent-route";

export async function PATCH(request: Request, context: ExecutionTaskRouteContext) {
  const route = await resolveExecutionTaskRoute(context);
  if (route.response) return route.response;
  const body = await parseExecutionTaskUpdateRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    `/api/activities/${encodeURIComponent(route.value.activityId)}/execution-tasks/${encodeURIComponent(route.value.taskId)}`,
    jsonRequest("PATCH", body.value)
  );
}
