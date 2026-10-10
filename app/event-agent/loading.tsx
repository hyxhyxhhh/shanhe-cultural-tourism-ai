export default function Loading() {
  return (
    <div className="space-y-5" aria-label="正在加载活动任务">
      <div className="flex items-end justify-between gap-4">
        <div className="space-y-2">
          <div className="loading-shimmer h-5 w-36 rounded" />
          <div className="loading-shimmer h-3 w-72 max-w-full rounded" />
        </div>
        <div className="loading-shimmer h-9 w-28 rounded-md" />
      </div>
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <div className="loading-shimmer h-11 border-b border-line" />
        {[1, 2, 3].map((item) => (
          <div key={item} className="grid gap-3 border-b border-line px-5 py-5 sm:grid-cols-[1fr_120px_130px]">
            <div className="loading-shimmer h-10 rounded" />
            <div className="loading-shimmer h-8 rounded" />
            <div className="loading-shimmer h-8 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
