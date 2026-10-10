import { cookies } from "next/headers";
import {
  authenticatedFastApiFetch,
  forwardFastApiResponse,
  SESSION_COOKIE_NAME
} from "@/lib/server/fastapi";

export async function POST() {
  const upstream = await authenticatedFastApiFetch("/api/auth/logout", { method: "POST" });
  (await cookies()).set(SESSION_COOKIE_NAME, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0
  });

  if (!upstream) return new Response(null, { status: 204 });
  return forwardFastApiResponse(upstream);
}
