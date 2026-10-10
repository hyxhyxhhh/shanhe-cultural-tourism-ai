export default function Loading() {
  return (
    <div className="space-y-4" aria-label="正在加载活动工作台">
      <div className="loading-shimmer h-20 rounded-lg border border-line" />
      <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)]">
        <div className="loading-shimmer h-[560px] rounded-lg border border-line" />
        <div className="loading-shimmer h-[560px] rounded-lg border border-line" />
      </div>
    </div>
  );
}
