import {
  authenticatedFastApiFetch,
  authenticationRequired,
  containsClientCreatedBy,
  forwardFastApiResponse,
  readJsonObject
} from "@/lib/server/fastapi";

export async function GET(request: Request) {
  const search = new URL(request.url).search;
  const upstream = await authenticatedFastApiFetch(`/api/activities${search}`);
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}

export async function POST(request: Request) {
  const body = await readJsonObject(request);
  if (!body) return Response.json({ message: "Invalid JSON request body" }, { status: 400 });
  if (containsClientCreatedBy(body)) {
    return Response.json({ message: "createdBy is assigned from the authenticated session" }, { status: 400 });
  }

  const upstream = await authenticatedFastApiFetch("/api/activities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}
