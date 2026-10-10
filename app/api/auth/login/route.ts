import { cookies } from "next/headers";
import { ROLE_OPTIONS } from "@/lib/platform/access";
import { fastApiFetch, forwardFastApiResponse, readJsonObject, SESSION_COOKIE_NAME } from "@/lib/server/fastapi";
import type { SessionUser } from "@/lib/types/access";

interface FastApiLoginResponse {
  sessionToken?: string;
  expiresAt?: string;
  user?: {
    userId?: string;
    account?: string;
    displayName?: string;
    roleId?: string;
    roleLabel?: string;
  };
}

function publicUser(user: NonNullable<FastApiLoginResponse["user"]>): SessionUser | null {
  const role = ROLE_OPTIONS.find((item) => item.id === user.roleId);
  if (!role || !user.userId || !user.account || !user.displayName) return null;
  return {
    userId: user.userId,
    account: user.account,
    displayName: user.displayName,
    roleId: role.id,
    roleLabel: user.roleLabel || role.label
  };
}

export async function POST(request: Request) {
  const body = await readJsonObject(request);
  if (!body) return Response.json({ message: "Invalid JSON request body" }, { status: 400 });

  const upstream = await fastApiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account: body.account, password: body.password })
  });
  if (!upstream.ok) return forwardFastApiResponse(upstream);

  let result: FastApiLoginResponse;
  try {
    result = (await upstream.json()) as FastApiLoginResponse;
  } catch {
    return Response.json({ message: "Authentication service returned an invalid response" }, { status: 502 });
  }

  const token = result.sessionToken;
  const user = result.user ? publicUser(result.user) : null;
  const expires = result.expiresAt ? new Date(result.expiresAt) : null;
  if (!token || !user || !expires || Number.isNaN(expires.getTime())) {
    return Response.json({ message: "Authentication service returned an invalid response" }, { status: 502 });
  }

  (await cookies()).set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires
  });

  return Response.json({ user });
}
