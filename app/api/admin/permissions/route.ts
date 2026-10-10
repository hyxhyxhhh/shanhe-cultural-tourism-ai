import { ROLE_ACCESS } from "@/lib/platform/access";

export async function GET() {
  return Response.json({ items: ROLE_ACCESS });
}
