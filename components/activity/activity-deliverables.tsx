"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileSpreadsheet, FileText, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { readableError } from "@/components/activity/activity-ui";
import { deliverablesApi } from "@/lib/api/deliverables";
import type { Deliverable } from "@/lib/types/activity-agent";

const FILE_LABELS: Record<Deliverable["filename"], string> = {
  "event-plan.docx": "完整活动策划 Word",
  "budget.xlsx": "预算 Excel",
  "execution-tasks.xlsx": "执行任务表 Excel"
};

function FileIcon({ filename }: { filename: Deliverable["filename"] }) {
  return filename.endsWith(".docx") ? <FileText size={16} /> : <FileSpreadsheet size={16} />;
}

export function ActivityDeliverables({
  activityId,
  refreshToken
}: {
  activityId: string;
  refreshToken: number;
}) {
  const [items, setItems] = useState<Deliverable[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await deliverablesApi.list(activityId));
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setLoading(false);
    }
  }, [activityId]);

  useEffect(() => {
    let active = true;
    deliverablesApi.list(activityId).then((next) => {
      if (active) setItems(next);
    }).catch((reason: unknown) => {
      if (active) toast.error(readableError(reason));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [activityId, refreshToken]);

  async function download(item: Deliverable) {
    setDownloadingId(item.id);
    try {
      const blob = await deliverablesApi.download(activityId, item.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = item.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (reason) {
      toast.error(readableError(reason));
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <section className="border-t border-line">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-ink">成果文件</h3>
          <p className="mt-1 text-[10px] text-moss">每次生成完整活动策划 Word、预算 Excel 和执行任务表 Excel，并保留历史版本。</p>
          <p className="mt-1 text-[10px] text-moss">共 {items.length} 个历史文件</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading} title="刷新成果文件">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            刷新
          </Button>
        </div>
      </div>

      {loading && !items.length ? (
        <div className="border-t border-line px-5 py-10 text-center text-xs text-moss">正在加载成果文件…</div>
      ) : items.length ? (
        <div className="divide-y divide-line border-t border-line">
          {items.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-mist text-pine">
                  <FileIcon filename={item.filename} />
                </span>
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium text-ink">{FILE_LABELS[item.filename]}</div>
                  <div className="mt-1 text-[10px] text-moss">版本 {item.version} · {new Date(item.createdAt).toLocaleString("zh-CN")}</div>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => void download(item)} disabled={downloadingId !== null} title={`下载 ${FILE_LABELS[item.filename]}`}>
                {downloadingId === item.id ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                下载
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="border-t border-line px-5 py-10 text-center text-xs text-moss">暂无成果文件</div>
      )}
    </section>
  );
}
