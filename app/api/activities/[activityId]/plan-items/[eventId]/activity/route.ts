import { authenticatedFastApiFetch, authenticationRequired, forwardFastApiResponse, readJsonObject } from "@/lib/server/fastapi";
export async function POST(request: Request, context: { params: Promise<{ activityId: string; eventId: string }> }) {
 const { activityId, eventId } = await context.params;
 const body = await readJsonObject(request);
 if (!body || Object.keys(body).length !== 1 || !Number.isSafeInteger(body.version) || Number(body.version) < 1) return Response.json({ detail: { code: "INVALID_VERSION" } }, { status: 400 });
 if (!/^[0-9a-f-]{36}$/i.test(activityId) || !eventId.trim()) return Response.json({ detail: { code: "INVALID_PLAN_ITEM" } }, { status: 400 });
 const upstream = await authenticatedFastApiFetch(`/api/activities/${encodeURIComponent(activityId)}/plan-items/${encodeURIComponent(eventId)}/activity`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
 return upstream ? forwardFastApiResponse(upstream) : authenticationRequired();
}
