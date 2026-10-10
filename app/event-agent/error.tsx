"use client";

import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="rounded-lg border border-[#e5c9c3] bg-white px-6 py-10 text-center">
      <h1 className="text-base font-semibold text-ink">活动任务暂时无法打开</h1>
      <p className="mt-2 text-xs text-moss">请检查网络或服务状态后重试。</p>
      <Button className="mt-5" onClick={retry}>
        <RotateCcw size={14} />
        重新加载
      </Button>
    </div>
  );
}
