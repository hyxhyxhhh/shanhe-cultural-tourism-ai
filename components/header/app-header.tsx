"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Bell, ChevronDown, Command, LockKeyhole, Search, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useRoleAccess } from "@/lib/platform/permissions";
import { useClientReady, useDemoSession } from "@/lib/platform/session";
import type { CapabilityId } from "@/lib/types/access";
import { useUIStore } from "@/stores/ui-store";
import { getProject, projects } from "@/lib/api/projects";
import { cn } from "@/lib/utils";

const searchItems: Array<{ type: string; title: string; href: string; capabilityId?: CapabilityId }> = [
  { type: "Agent", title: "活动策划Agent", href: "/event-agent", capabilityId: "event-agent" },
  { type: "报告", title: "资本化前置诊断报告", href: "/deliverables", capabilityId: "capital" },
  { type: "资产", title: "一期资产归集及权属清单", href: "/assets", capabilityId: "assets" },
  { type: "任务", title: "酒店板块PMC百日计划", href: "/implementation", capabilityId: "implementation" }
];

export function AppHeader() {
  const router = useRouter();
  const clientReady = useClientReady();
  const session = useDemoSession();
  const activeSession = clientReady ? session : null;
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { notificationOpen, setNotificationOpen, sidebarCollapsed, currentProjectId, setCurrentProjectId } = useUIStore();
  const currentProject = getProject(currentProjectId);
  const access = useRoleAccess(activeSession?.user.roleId);
  const canAskAi = !access || access.cockpitIds.includes("ai-advisor");
  const filtered = searchItems.filter((item) => item.title.includes(query) && (!access || !item.capabilityId || access.capabilityIds.includes(item.capabilityId)));
  return <>
    <header className={cn("fixed right-0 top-0 z-30 flex h-[63px] items-center border-b border-line bg-white/95 px-7 backdrop-blur transition-[left] max-md:left-[66px] max-md:px-3", sidebarCollapsed ? "left-[66px]" : "left-[240px]")}>
      <DropdownMenu.Root><DropdownMenu.Trigger asChild><button className="flex min-w-[270px] items-center gap-3 text-left max-lg:min-w-0">
        <div className="min-w-0"><div className="truncate text-xs font-semibold">{currentProject.name}</div><div className="mt-1 truncate text-[9px] text-[#8b9a95] max-sm:hidden">{currentProject.owner} · {currentProject.status} · 点击切换</div></div><ChevronDown size={13} className="shrink-0 text-moss" />
      </button></DropdownMenu.Trigger><DropdownMenu.Portal><DropdownMenu.Content align="start" className="z-50 mt-2 w-72 rounded-lg border border-line bg-white p-2 shadow-xl">
        {projects.map((project)=><DropdownMenu.Item key={project.id} onSelect={()=>{setCurrentProjectId(project.id);toast.success(`已切换至：${project.name}`);}} className="cursor-pointer rounded-md px-3 py-2.5 text-xs outline-none hover:bg-mist"><div className="font-medium">{project.name}</div><div className="mt-1 text-[10px] text-moss">{project.id === currentProject.id ? "当前空间 · 数据正常" : `${project.status} · 可切换`}</div></DropdownMenu.Item>)}
      </DropdownMenu.Content></DropdownMenu.Portal></DropdownMenu.Root>
      <div className="ml-auto flex items-center gap-2">
        <button onClick={()=>setSearchOpen(true)} className="flex h-9 w-[245px] items-center gap-2 rounded-md border border-line bg-[#f7f8f6] px-3 text-[10px] text-[#83908c] hover:border-moss max-lg:w-10 max-lg:justify-center max-lg:px-0"><Search size={13}/><span className="max-lg:hidden">搜索资产、模型、报告或任务</span><span className="ml-auto flex items-center gap-0.5 rounded border border-line bg-white px-1 py-0.5 text-[9px] max-lg:hidden"><Command size={9}/>K</span></button>
        <button onClick={()=>setNotificationOpen(true)} aria-label="通知" className="relative grid h-9 w-9 place-items-center rounded-md border border-line bg-white text-ink hover:bg-mist"><Bell size={15}/><span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#9c5849] px-1 text-[8px] text-white">6</span></button>
        <button onClick={()=>canAskAi && router.push("/ai")} disabled={!canAskAi} className="flex h-9 items-center gap-2 rounded-md bg-forest px-4 text-[10px] font-medium text-white hover:bg-pine disabled:cursor-not-allowed disabled:bg-[#71827d] max-sm:w-9 max-sm:px-0 max-sm:justify-center">{canAskAi ? <Sparkles size={12}/> : <LockKeyhole size={12}/>}<span className="max-sm:hidden">{canAskAi ? "询问AI首席顾问" : "AI暂无权限"}</span></button>
      </div>
    </header>
    <Dialog open={searchOpen} onOpenChange={setSearchOpen}><DialogContent className="top-[34%] p-0 overflow-hidden"><div className="flex items-center gap-3 border-b border-line px-5 py-4"><Search size={18} className="text-moss"/><input value={query} onChange={(e)=>setQuery(e.target.value)} autoFocus placeholder="搜索资产、模型、报告或任务" className="w-full bg-transparent text-sm outline-none"/><span className="rounded border border-line px-1.5 py-0.5 text-[10px] text-moss">ESC</span></div><div className="max-h-80 p-2">{filtered.length ? filtered.map(item=><button key={item.title} onClick={()=>{router.push(item.href);setSearchOpen(false)}} className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-left hover:bg-mist"><span className="rounded bg-[#e5efeb] px-2 py-1 text-[9px] text-moss">{item.type}</span><span className="text-xs font-medium">{item.title}</span></button>) : <div className="py-12 text-center text-xs text-moss">没有找到匹配内容</div>}</div></DialogContent></Dialog>
    <div className={`fixed inset-y-0 right-0 z-50 w-[360px] border-l border-line bg-white p-5 shadow-2xl transition-transform max-sm:w-[calc(100%-40px)] ${notificationOpen ? "translate-x-0" : "translate-x-full"}`}><div className="flex items-center justify-between"><div><h2 className="text-base font-semibold">消息与待办</h2><p className="mt-1 text-[10px] text-moss">6 条未读提醒</p></div><button onClick={()=>setNotificationOpen(false)} className="quiet-button">关闭</button></div><div className="mt-6 space-y-2">{["活动投放预算等待审批","两项经营权授权待确认","酒店板块PMC诊断已完成","资产边界审议会明日召开"].map((text,i)=><button key={text} onClick={()=>toast.info("已打开提醒详情")} className="w-full rounded-lg border border-line p-4 text-left hover:bg-mist"><div className="flex gap-3"><span className={`mt-1 h-2 w-2 rounded-full ${i<2?"bg-[#a65e4d]":"bg-[#6c9d89]"}`}/><div><div className="text-xs font-medium">{text}</div><div className="mt-1 text-[10px] text-moss">{i+2} 小时前 · 渝西项目</div></div></div></button>)}</div></div>
  </>;
}
