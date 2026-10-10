import {
  authenticatedFastApiFetch,
  authenticationRequired,
  forwardFastApiResponse
} from "@/lib/server/fastapi";

type ActivityRouteContext = { params: Promise<{ activityId: string }> };

export async function POST(_request: Request, context: ActivityRouteContext) {
  const { activityId } = await context.params;
  const upstream = await authenticatedFastApiFetch(
    `/api/activities/${encodeURIComponent(activityId)}/pause`,
    { method: "POST" }
  );
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}
