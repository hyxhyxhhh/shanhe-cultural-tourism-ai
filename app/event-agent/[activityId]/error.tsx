"use client";

import Link from "next/link";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="rounded-lg border border-[#e5c9c3] bg-white px-6 py-10 text-center">
      <h1 className="text-base font-semibold text-ink">活动工作台暂时无法打开</h1>
      <p className="mt-2 text-xs text-moss">请重试，或返回活动列表选择其他任务。</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Link href="/event-agent" className="quiet-button inline-flex items-center gap-2">
          <ArrowLeft size={14} />
          返回活动列表
        </Link>
        <Button onClick={retry}>
          <RotateCcw size={14} />
          重新加载
        </Button>
      </div>
    </div>
  );
}
