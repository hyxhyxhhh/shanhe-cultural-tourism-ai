import { proxyAuthenticated } from "@/app/api/activities/_lib/step-route";

export async function GET() {
  return proxyAuthenticated("/api/models");
}
