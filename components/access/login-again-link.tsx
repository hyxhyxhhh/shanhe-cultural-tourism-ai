"use client";

import Link from "next/link";
import { LogIn } from "lucide-react";
import { cn } from "@/lib/utils";
import { eventAgentLoginHref } from "@/lib/platform/login-return";
import { clearDemoSession } from "@/lib/platform/session";

export function LoginAgainLink({ className }: { className?: string }) {
  return (
    <Link
      href={eventAgentLoginHref()}
      onClick={clearDemoSession}
      className={cn(
        "inline-flex h-8 shrink-0 items-center justify-center gap-2 rounded-md bg-forest px-3 text-xs font-medium text-white transition hover:bg-pine focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss active:scale-[.98]",
        className
      )}
    >
      <LogIn size={13} aria-hidden="true" />
      重新登录
    </Link>
  );
}
