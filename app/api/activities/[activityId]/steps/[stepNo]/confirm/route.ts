import {
  jsonRequest,
  parseConfirmStepRequest,
  proxyAuthenticated,
  resolveStepRoute,
  stepPath,
  type StepRouteContext
} from "@/app/api/activities/_lib/step-route";

export async function POST(request: Request, context: StepRouteContext) {
  const route = await resolveStepRoute(context);
  if (route.response) return route.response;
  const body = await parseConfirmStepRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    stepPath(route.value.activityId, route.value.stepNo, "confirm"),
    jsonRequest("POST", body.value)
  );
}
