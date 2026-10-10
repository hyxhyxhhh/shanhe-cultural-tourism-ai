import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="rounded-lg border border-line bg-white px-6 py-10 text-center">
      <h1 className="text-base font-semibold text-ink">未找到活动任务</h1>
      <p className="mt-2 text-xs text-moss">活动可能已归档、删除，或当前账号无权访问。</p>
      <Link href="/event-agent" className="primary-button mt-5 inline-flex items-center gap-2">
        <ArrowLeft size={14} />
        返回活动列表
      </Link>
    </div>
  );
}
