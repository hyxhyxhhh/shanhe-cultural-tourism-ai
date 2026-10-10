import {
  jsonRequest,
  parsePatchStepRequest,
  proxyAuthenticated,
  resolveStepRoute,
  stepPath,
  type StepRouteContext
} from "@/app/api/activities/_lib/step-route";

export async function GET(_request: Request, context: StepRouteContext) {
  const route = await resolveStepRoute(context);
  if (route.response) return route.response;
  return proxyAuthenticated(stepPath(route.value.activityId, route.value.stepNo));
}

export async function PATCH(request: Request, context: StepRouteContext) {
  const route = await resolveStepRoute(context);
  if (route.response) return route.response;
  const body = await parsePatchStepRequest(request);
  if (body.response) return body.response;
  return proxyAuthenticated(
    stepPath(route.value.activityId, route.value.stepNo),
    jsonRequest("PATCH", body.value)
  );
}
