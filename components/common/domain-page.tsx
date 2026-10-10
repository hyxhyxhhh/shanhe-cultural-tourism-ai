import { PageHeading } from "@/components/common/page-heading";
import { SectionCard } from "@/components/common/section-card";
import { Card, CardContent } from "@/components/ui/card";
import type { DomainPageData } from "@/lib/types/platform";

export function DomainPage({ data }: { data: DomainPageData }) {
  return <div><PageHeading title={data.title} description={data.description}/><section className="relative mb-5 overflow-hidden rounded-[10px] bg-[#2d4651] px-6 py-7 text-white shadow-card sm:px-8"><div className="absolute right-8 top-3 select-none text-[72px] font-semibold tracking-[.15em] text-white/[.035]">SHANHE</div><div className="eyebrow text-[#d6bb84]">{data.eyebrow ?? "DECISION OPERATING SYSTEM"}</div><h2 className="relative mt-3 max-w-3xl text-xl font-semibold leading-snug sm:text-2xl">{data.heroTitle}</h2><p className="relative mt-2 max-w-2xl text-[11px] leading-5 text-white/70">{data.heroDescription}</p></section>{data.stats && <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">{data.stats.map((stat)=><Card key={stat.label}><CardContent className="p-4"><div className="text-[10px] text-moss">{stat.label}</div><div className="mt-2 text-2xl font-semibold tracking-[-.04em]">{stat.value}</div>{stat.note && <div className="mt-1 text-[10px] text-moss">{stat.note}</div>}</CardContent></Card>)}</div>}<div className="space-y-4">{data.sections.map((section)=><SectionCard key={section.title} section={section}/>)}</div></div>;
}
