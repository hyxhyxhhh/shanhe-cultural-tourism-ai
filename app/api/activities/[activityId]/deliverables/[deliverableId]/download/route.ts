import {
  fetchAuthenticated,
  resolveDeliverableRoute,
  type DeliverableRouteContext
} from "@/app/api/activities/_lib/agent-route";

export async function GET(_request: Request, context: DeliverableRouteContext) {
  const route = await resolveDeliverableRoute(context);
  if (route.response) return route.response;
  const upstream = await fetchAuthenticated(
    `/api/activities/${encodeURIComponent(route.value.activityId)}/deliverables/${encodeURIComponent(route.value.deliverableId)}/download`
  );
  const headers = new Headers();
  for (const name of ["content-type", "content-disposition", "www-authenticate"] as const) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
