import { COCKPITS, getCockpitsForRole, ROLE_OPTIONS } from "@/lib/platform/access";
import type { UserRoleId } from "@/lib/types/access";

export async function GET(request: Request) {
  const roleId = new URL(request.url).searchParams.get("roleId") as UserRoleId | null;
  const validRole = ROLE_OPTIONS.some((role) => role.id === roleId);
  return Response.json({ items: validRole && roleId ? getCockpitsForRole(roleId) : COCKPITS });
}
