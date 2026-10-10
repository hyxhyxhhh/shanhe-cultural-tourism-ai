import Image from "next/image";
import { Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, CircleHelp, Minus, ShieldAlert } from "lucide-react";
import type { CSSProperties } from "react";
import type { CockpitDashboardData, DashboardProgress, DashboardRisk, DashboardTrend } from "@/mocks/cockpit-dashboard";

const panelClass = "rounded-[10px] border border-white/10 bg-[#102b24]/85";

function SectionTitle({ title, note }: { title: string; note?: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-white sm:text-base 2xl:text-lg"><span className="h-4 w-0.5 rounded-full bg-[#d2b26a]" />{title}</h3>
      {note ? <span className="text-[10px] text-white/45 2xl:text-xs">{note}</span> : null}
    </div>
  );
}

function ChartState({ loading }: { loading?: boolean }) {
  return <div className="grid min-h-[230px] place-items-center text-xs text-white/45" role="status">{loading ? "图表数据加载中…" : "暂无可展示的图表数据"}</div>;
}

function TrendChart({ trend, loading = false }: { trend: DashboardTrend; loading?: boolean }) {
  if (loading || trend.points.length === 0) return <ChartState loading={loading} />;

  const max = Math.max(1, ...trend.points.flatMap((point) => [point.primary, point.secondary]));
  const ceiling = Math.ceil(max / 2) * 2;
  const left = 48;
  const right = 575;
  const top = 24;
  const bottom = 188;
  const height = bottom - top;
  const step = (right - left) / trend.points.length;
  const centers = trend.points.map((_, index) => left + step * (index + 0.5));
  const line = trend.points.map((point, index) => `${centers[index]},${bottom - (point.secondary / ceiling) * height}`).join(" ");

  return (
    <>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[10px] text-white/58">
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm bg-[#5bb99d]" />{trend.primaryLabel}</span>
        <span className="inline-flex items-center gap-2"><i className="h-0.5 w-3 bg-[#d9b76d]" />{trend.secondaryLabel}</span>
        <span className="ml-auto">单位：{trend.unit} / 周</span>
      </div>
      <svg className="mt-2 h-[220px] w-full 2xl:h-[280px]" viewBox="0 0 620 230" role="img" aria-label={`${trend.title}：${trend.points.map((point) => `${point.label}${trend.primaryLabel}${point.primary}${trend.unit}、${trend.secondaryLabel}${point.secondary}${trend.unit}`).join("；")}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const y = bottom - fraction * height;
          return <g key={fraction}><line x1={left} y1={y} x2={right} y2={y} stroke="#ffffff" strokeOpacity="0.1" strokeDasharray="3 4" /><text x="35" y={y + 4} textAnchor="end" fill="#b4c5be" fontSize="10">{Math.round(fraction * ceiling)}</text></g>;
        })}
        {trend.points.map((point, index) => {
          const barHeight = (point.primary / ceiling) * height;
          return <g key={point.label}><rect x={centers[index] - 20} y={bottom - barHeight} width="40" height={barHeight} rx="3" fill="#5bb99d" fillOpacity="0.78" /><text x={centers[index]} y={bottom + 20} textAnchor="middle" fill="#b4c5be" fontSize="10">{point.label}</text></g>;
        })}
        <polyline points={line} fill="none" stroke="#d9b76d" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {trend.points.map((point, index) => <circle key={point.label} cx={centers[index]} cy={bottom - (point.secondary / ceiling) * height} r="4" fill="#e9d39a" stroke="#102b24" strokeWidth="2" />)}
      </svg>
    </>
  );
}

function DistributionChart({ title, segments, loading = false }: { title: string; segments: CockpitDashboardData["segments"]; loading?: boolean }) {
  const total = segments.reduce((sum, item) => sum + item.value, 0);
  if (loading || total === 0) return <ChartState loading={loading} />;

  const stops = segments.reduce<{ offset: number; values: string[] }>((result, segment) => {
    const nextOffset = result.offset + (segment.value / total) * 100;
    return {
      offset: nextOffset,
      values: [...result.values, `${segment.color} ${result.offset}% ${nextOffset}%`]
    };
  }, { offset: 0, values: [] }).values;
  const style: CSSProperties = { background: `conic-gradient(${stops.join(", ")})` };

  return (
    <div className="mt-4 flex flex-col items-center justify-center gap-6 py-3 sm:flex-row xl:min-h-[226px]">
      <div className="relative h-40 w-40 shrink-0 rounded-full 2xl:h-44 2xl:w-44" style={style} role="img" aria-label={`${title}：${segments.map((item) => `${item.label}${item.value}项`).join("；")}`}>
        <div className="absolute inset-[27px] grid place-content-center rounded-full bg-[#102b24] text-center">
          <strong className="text-2xl font-semibold text-white">{total}</strong>
          <span className="text-[10px] text-white/50">总计 · 项</span>
        </div>
      </div>
      <ul className="w-full min-w-0 space-y-3 text-[11px] sm:max-w-[190px] 2xl:max-w-[230px] 2xl:text-xs">
        {segments.map((segment) => <li key={segment.label} className="flex items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: segment.color }} /><span className="min-w-0 flex-1 truncate text-white/70">{segment.label}</span><strong className="text-white">{segment.value}</strong><span className="w-9 text-right text-white/45">{Math.round((segment.value / total) * 100)}%</span></li>)}
      </ul>
    </div>
  );
}

const progressTone: Record<DashboardProgress["status"], string> = {
  "进行中": "border-[#5bb99d]/35 bg-[#5bb99d]/10 text-[#91d5bc]",
  "待审核": "border-[#d9b76d]/35 bg-[#d9b76d]/10 text-[#e4ca89]",
  "有风险": "border-[#c98777]/35 bg-[#c98777]/10 text-[#e5a89b]",
  "已完成": "border-[#83a8a1]/35 bg-[#83a8a1]/10 text-[#b2d3cc]"
};

const riskTone: Record<DashboardRisk["severity"], string> = {
  "高": "border-[#c98777]/35 bg-[#c98777]/10 text-[#e5a89b]",
  "中": "border-[#d9b76d]/35 bg-[#d9b76d]/10 text-[#e4ca89]",
  "低": "border-[#83a8a1]/35 bg-[#83a8a1]/10 text-[#b2d3cc]"
};

export function CockpitDashboard({ data, loading = false }: { data: CockpitDashboardData; loading?: boolean }) {
  return (
    <section className="pb-12" aria-labelledby="cockpit-dashboard-title">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3"><h2 id="cockpit-dashboard-title" className="text-lg font-semibold text-white 2xl:text-2xl">驾驶舱概览</h2><span className="rounded-full border border-[#d2b26a]/35 bg-[#d2b26a]/10 px-2 py-0.5 text-[10px] text-[#e0c27d] 2xl:text-xs">演示数据</span></div>
        <p className="text-[10px] text-white/45 2xl:text-xs">{data.period} · 非真实业务结论</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:gap-4">
        {data.metrics.map((metric) => {
          const DirectionIcon = metric.direction === "up" ? ArrowUpRight : metric.direction === "down" ? ArrowDownRight : Minus;
          return <article key={metric.label} className={`${panelClass} min-h-[116px] p-4 2xl:min-h-[140px] 2xl:p-6`}>
            <div className="flex items-center gap-2 text-[11px] text-white/60 2xl:text-sm"><Activity size={14} className="text-[#d2b26a]" />{metric.label}</div>
            <div className="mt-2 flex items-end justify-between gap-2 2xl:mt-4"><div><strong className="text-3xl font-semibold leading-none text-white 2xl:text-4xl">{metric.value}</strong><span className="ml-1 text-[11px] text-white/55 2xl:text-sm">{metric.unit}</span></div><div className="flex items-center gap-1 text-[10px] text-white/55 2xl:text-xs"><span>{metric.comparison}</span><DirectionIcon size={13} className="text-[#8ac7ac]" /><span className="text-white/80">{metric.change}</span></div></div>
          </article>;
        })}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2 2xl:grid-cols-[1.45fr_0.9fr_1.1fr] 2xl:gap-4">
        <section className={`${panelClass} min-w-0 p-4 sm:p-5`}><SectionTitle title={data.trend.title} note="最近 4 周 · 演示趋势" /><TrendChart trend={data.trend} loading={loading} /></section>
        <section className={`${panelClass} min-w-0 p-4 sm:p-5`}><SectionTitle title={data.distributionTitle} note="按当前演示状态统计" /><DistributionChart title={data.distributionTitle} segments={data.segments} loading={loading} /></section>
        <section className={`${panelClass} min-w-0 p-4 sm:p-5 lg:col-span-2 2xl:col-span-1`}>
          <SectionTitle title="重点项目进度" note="计划时间为演示排期" />
          {data.progress.length ? (
            <ul className="mt-3 divide-y divide-white/10">
              {data.progress.map((item) => (
                <li key={item.name} className="flex gap-3 py-3 first:pt-0 last:pb-0 2xl:py-4">
                  <Image
                    src={item.imageSrc}
                    alt=""
                    width={112}
                    height={72}
                    sizes="112px"
                    className="h-[64px] w-[96px] shrink-0 rounded-[6px] border border-white/10 object-cover 2xl:h-[72px] 2xl:w-[112px]"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
                      <p className="min-w-0 text-xs font-medium text-white 2xl:text-sm">{item.name}</p>
                      <span className={`shrink-0 rounded-[5px] border px-2 py-0.5 text-[10px] ${progressTone[item.status]}`}>{item.status}</span>
                    </div>
                    <p className="mt-1 text-[10px] leading-4 text-white/48 2xl:text-xs">{item.stage} · 计划 {item.targetDate}</p>
                    <div className="mt-2 flex items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-[#68b99c]" style={{ width: `${Math.min(100, Math.max(0, item.percent))}%` }} /></div>
                      <span className="w-9 text-right text-[10px] text-white/70 2xl:text-xs">{item.percent}%</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="py-10 text-center text-xs text-white/45">暂无重点项目进度</p>}
        </section>
      </div>

      <div className="mt-3 2xl:mt-4">
        <section id="cockpit-risks" className={`${panelClass} min-w-0 p-4 sm:p-5`}>
          <SectionTitle title="风险提示" note={`${data.risks.length} 项需关注`} />
          {data.risks.length ? <ul className="mt-3 grid gap-3 md:grid-cols-2">{data.risks.map((risk) => <li key={risk.title} className="flex gap-3 rounded-[8px] border border-white/10 bg-white/[0.025] p-3 2xl:p-4"><ShieldAlert size={16} className="mt-0.5 shrink-0 text-[#d9b76d]" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-xs font-medium text-white 2xl:text-sm">{risk.title}</p><span className={`rounded-[5px] border px-1.5 py-0.5 text-[9px] ${riskTone[risk.severity]}`}>{risk.severity}风险</span></div><p className="mt-1 text-[10px] leading-4 text-white/50 2xl:text-xs 2xl:leading-5">影响：{risk.impact}</p><p className="mt-1 text-[10px] text-[#dec689] 2xl:text-xs">关注节点：{risk.dueDate}</p></div></li>)}</ul> : <div className="flex min-h-[160px] items-center justify-center gap-2 text-xs text-white/55"><CircleHelp size={15} />暂无风险提示</div>}
        </section>
      </div>
      <p className="mt-3 flex items-start gap-1.5 text-[10px] leading-5 text-white/35"><AlertTriangle size={12} className="mt-1 shrink-0" />当前指标、趋势、进度与风险为工作流演示快照；实际业务判断请以审核后的项目资料为准。<ArrowRight size={11} className="mt-1 shrink-0" /></p>
    </section>
  );
}
