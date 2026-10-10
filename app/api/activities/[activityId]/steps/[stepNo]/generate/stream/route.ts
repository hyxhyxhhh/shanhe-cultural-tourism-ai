import { resolveStepRoute, stepPath, type StepRouteContext } from "@/app/api/activities/_lib/step-route";
import { jsonRequest, parseGenerateStepRequest } from "@/app/api/activities/_lib/step-route";
import { authenticatedFastApiFetch, authenticationRequired, forwardFastApiResponse } from "@/lib/server/fastapi";

export async function POST(request: Request, context: StepRouteContext) {
  const route = await resolveStepRoute(context);
  if (route.response) return route.response;
  const body = await parseGenerateStepRequest(request);
  if (body.response) return body.response;
  const upstream = await authenticatedFastApiFetch(
    stepPath(route.value.activityId, route.value.stepNo, "generate/stream"),
    { ...jsonRequest("POST", body.value), signal: request.signal }
  );
  if (!upstream) return authenticationRequired();
  if (!upstream.ok) return forwardFastApiResponse(upstream);
  if (!upstream.headers.get("content-type")?.startsWith("text/event-stream") || !upstream.body) {
    return Response.json({ detail: { code: "INVALID_PLANNING_STREAM", message: "Backend did not return the required planning progress stream" } }, { status: 502 });
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store", "X-Accel-Buffering": "no" }
  });
}
