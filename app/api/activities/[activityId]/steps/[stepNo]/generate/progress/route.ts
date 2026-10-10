import { proxyAuthenticated, resolveStepRoute, stepPath, type StepRouteContext } from "@/app/api/activities/_lib/step-route";
export async function GET(_request: Request, context: StepRouteContext) {
 const route = await resolveStepRoute(context);
 if (route.response) return route.response;
 return proxyAuthenticated(stepPath(route.value.activityId, route.value.stepNo, "generate/progress"));
}
