import {
  authenticatedFastApiFetch,
  authenticationRequired,
  containsClientCreatedBy,
  forwardFastApiResponse,
  readJsonObject
} from "@/lib/server/fastapi";

type ActivityRouteContext = { params: Promise<{ activityId: string }> };

function activityPath(activityId: string) {
  return `/api/activities/${encodeURIComponent(activityId)}`;
}

export async function GET(_request: Request, context: ActivityRouteContext) {
  const { activityId } = await context.params;
  const upstream = await authenticatedFastApiFetch(activityPath(activityId));
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}

export async function PATCH(request: Request, context: ActivityRouteContext) {
  const body = await readJsonObject(request);
  if (!body) return Response.json({ message: "Invalid JSON request body" }, { status: 400 });
  if (containsClientCreatedBy(body)) {
    return Response.json({ message: "createdBy cannot be changed by the client" }, { status: 400 });
  }

  const { activityId } = await context.params;
  const upstream = await authenticatedFastApiFetch(activityPath(activityId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}
