import { proxyAuthenticated, resolveActivityRoute, stepsPath, type ActivityRouteContext } from "@/app/api/activities/_lib/step-route";

export async function GET(_request: Request, context: ActivityRouteContext) {
  const route = await resolveActivityRoute(context);
  if (route.response) return route.response;
  return proxyAuthenticated(stepsPath(route.value.activityId));
}
