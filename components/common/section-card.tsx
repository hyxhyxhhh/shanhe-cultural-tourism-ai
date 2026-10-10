import { ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { PageSection } from "@/lib/types/platform";

export function SectionCard({ section }: { section: PageSection }) {
  return <Card className="overflow-hidden"><CardHeader className="py-4"><div><h3 className="text-sm font-semibold">{section.title}</h3>{section.subtitle && <p className="mt-1 text-[10px] text-moss">{section.subtitle}</p>}</div>{section.action && <button className="flex items-center gap-1 text-[10px] font-medium text-pine hover:text-forest">{section.action}<ArrowUpRight size={12}/></button>}</CardHeader><CardContent className="grid gap-x-4 gap-y-1 p-3 sm:grid-cols-2 lg:grid-cols-3">{section.items.map((item, index)=><div key={`${item.label}-${index}`} className="group flex min-h-[62px] items-center gap-3 rounded-lg px-3 py-2.5 transition hover:bg-mist"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-mist text-[10px] font-semibold text-pine">{item.icon ?? String(index+1).padStart(2,"0")}</div><div className="min-w-0 flex-1"><div className="truncate text-xs font-medium">{item.label}</div>{item.value && <div className="mt-1 truncate text-[10px] text-moss">{item.value}</div>}</div>{item.status && <span className="shrink-0 text-[10px] font-medium text-[#607b70]">{item.status}</span>}</div>)}</CardContent></Card>;
}
