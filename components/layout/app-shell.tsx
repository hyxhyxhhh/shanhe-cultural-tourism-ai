"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/navigation/sidebar";
import { AppHeader } from "@/components/header/app-header";
import { useUIStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const collapsed = useUIStore((state) => state.sidebarCollapsed);
  if (pathname === "/login" || pathname.startsWith("/cockpits") || pathname.startsWith("/admin")) return <>{children}</>;
  return <div className="min-h-screen"><Sidebar/><AppHeader/><main className={cn("min-h-screen pt-[63px] transition-[margin]", collapsed ? "ml-[66px]" : "ml-[240px]", "max-md:ml-[66px]")}><div className="mx-auto max-w-[1500px] px-8 py-8 max-lg:px-5 max-sm:px-3 max-sm:py-5">{children}</div></main></div>;
}
