import { ROLE_OPTIONS } from "@/lib/platform/access";
import { authenticatedFastApiFetch, authenticationRequired, forwardFastApiResponse } from "@/lib/server/fastapi";
import type { SessionUser } from "@/lib/types/access";

interface FastApiUser {
  userId?: string;
  account?: string;
  displayName?: string;
  roleId?: string;
  roleLabel?: string;
}

export async function GET() {
  const upstream = await authenticatedFastApiFetch("/api/auth/me");
  if (!upstream) return authenticationRequired();
  if (!upstream.ok) return forwardFastApiResponse(upstream);

  let payload: FastApiUser | { user?: FastApiUser };
  try {
    payload = (await upstream.json()) as FastApiUser | { user?: FastApiUser };
  } catch {
    return Response.json({ message: "Authentication service returned an invalid response" }, { status: 502 });
  }

  const user = (payload as { user?: FastApiUser }).user ?? (payload as FastApiUser);
  const role = ROLE_OPTIONS.find((item) => item.id === user?.roleId);
  if (!user?.userId || !user.account || !user.displayName || !role) {
    return Response.json({ message: "Authentication service returned an invalid response" }, { status: 502 });
  }

  const safeUser: SessionUser = {
    userId: user.userId,
    account: user.account,
    displayName: user.displayName,
    roleId: role.id,
    roleLabel: user.roleLabel || role.label
  };
  return Response.json({ user: safeUser });
}
