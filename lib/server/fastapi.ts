import "server-only";

import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "shanhe_session";

function fastApiBaseUrl() {
  const configured = process.env.FASTAPI_BASE_URL?.trim();
  if (!configured) throw new Error("FASTAPI_BASE_URL must be configured");
  let url: URL;
  try {
    url = new URL(configured);
  } catch (reason) {
    throw new Error("FASTAPI_BASE_URL must be a valid absolute URL", { cause: reason });
  }
  if (!(["http:", "https:"] as const).includes(url.protocol as "http:" | "https:") || url.username || url.password || url.search || url.hash) {
    throw new Error("FASTAPI_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment");
  }
  return configured.replace(/\/$/, "");
}

export async function sessionToken() {
  return (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? null;
}

export async function fastApiFetch(path: string, init: RequestInit = {}) {
  const baseUrl = fastApiBaseUrl();
  try {
    return await fetch(`${baseUrl}${path}`, {
      cache: "no-store",
      ...init
    });
  } catch (reason) {
    if (!(reason instanceof TypeError)) throw reason;
    console.error("FastAPI network request failed", { baseUrl, path, reason });
    return Response.json(
      { detail: { code: "FASTAPI_NETWORK_ERROR", message: "Backend service is unavailable" } },
      { status: 502 }
    );
  }
}

export async function authenticatedFastApiFetch(path: string, init: RequestInit = {}) {
  const token = await sessionToken();
  if (!token) return null;

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fastApiFetch(path, { ...init, headers });
}

export function forwardFastApiResponse(response: Response) {
  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const authenticate = response.headers.get("www-authenticate");
  if (authenticate) headers.set("WWW-Authenticate", authenticate);

  return new Response(response.body, {
    status: response.status,
    headers
  });
}

export function authenticationRequired() {
  return Response.json(
    { detail: "Authentication required" },
    {
      status: 401,
      headers: { "WWW-Authenticate": "Bearer" }
    }
  );
}

export async function readJsonObject(request: Request) {
  try {
    const body = await request.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) return null;
    return body as Record<string, unknown>;
  } catch (reason) {
    if (reason instanceof SyntaxError) return null;
    throw reason;
  }
}

export function containsClientCreatedBy(body: Record<string, unknown>) {
  return Object.hasOwn(body, "createdBy") || Object.hasOwn(body, "created_by");
}
