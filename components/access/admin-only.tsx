"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { LockKeyhole } from "lucide-react";
import { useClientReady, useDemoSession } from "@/lib/platform/session";

export function AdminOnly({ children }: { children: ReactNode }) {
  const router = useRouter();
  const clientReady = useClientReady();
  const session = useDemoSession();
  const allowed = session?.user.roleId === "platform-admin";

  useEffect(() => {
    if (clientReady && !allowed) router.replace(session ? "/cockpits" : "/login");
  }, [allowed, clientReady, router, session]);

  if (!clientReady || !allowed) {
    return <main className="grid min-h-screen place-items-center bg-[#f3f5f1] text-[#587068]"><div className="text-center"><LockKeyhole className="mx-auto" size={22} /><p className="mt-3 text-xs">正在返回可用页面...</p></div></main>;
  }

  return children;
}
