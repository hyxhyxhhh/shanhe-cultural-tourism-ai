"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Aperture, Archive, BarChart3, Boxes, BriefcaseBusiness, Building2,
  CheckSquare2, ChevronLeft, ChevronRight, CircleDollarSign, Database, FileCheck2,
  Gauge, Gem, Landmark, LayoutDashboard, Megaphone, Network, Palette, Play,
  LockKeyhole, ShieldCheck, Sparkles, Target, Workflow
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useRoleAccess } from "@/lib/platform/permissions";
import { useClientReady, useDemoSession } from "@/lib/platform/session";
import { useUIStore } from "@/stores/ui-store";
import type { CapabilityId, CockpitId } from "@/lib/types/access";
import type { LucideIcon } from "lucide-react";

type NavItem = { href: string; label: string; icon: LucideIcon; badge?: string; capabilityId?: CapabilityId; cockpitId?: CockpitId; adminOnly?: boolean };
type NavGroup = { title: string; items: NavItem[]; adminOnly?: boolean };

const navGroups: NavGroup[] = [
  { title: "客户演示", adminOnly: true, items: [
    { href: "/group-demo", label: "文旅集团演示入口", icon: Play },
    { href: "/clients", label: "客户Agent套件", icon: Boxes }
  ]},
  { title: "统一决策门户", items: [
    { href: "/dashboard", label: "管理层驾驶舱", icon: LayoutDashboard, cockpitId: "management" },
    { href: "/ai", label: "AI首席顾问", icon: Sparkles, cockpitId: "ai-advisor" },
    { href: "/automation", label: "自动执行中心", icon: Workflow },
    { href: "/decision-center", label: "决策任务中心", icon: Target, cockpitId: "decision-center" }
  ]},
  { title: "专业Agent", items: [
    { href: "/event-agent", label: "活动策划Agent", icon: Sparkles, capabilityId: "event-agent" },
    { href: "/operations", label: "运营招商Agent", icon: BriefcaseBusiness, capabilityId: "operations" },
    { href: "/strategy", label: "战略策划Agent", icon: Aperture, capabilityId: "strategy" },
    { href: "/assets", label: "资产盘活Agent", icon: Gem, capabilityId: "assets" },
    { href: "/marketing", label: "营销增长Agent", icon: Megaphone, capabilityId: "marketing" },
    { href: "/implementation", label: "实施PMO Agent", icon: CheckSquare2, badge: "12", capabilityId: "implementation" },
    { href: "/capital", label: "资本化前置Agent", icon: CircleDollarSign, capabilityId: "capital" }
  ]},
  { title: "专业能力域", items: [
    { href: "/design", label: "专业设计", icon: Palette, capabilityId: "design" },
    { href: "/project-control", label: "项目管控", icon: Building2, capabilityId: "project-control" },
    { href: "/creative", label: "文创工业设计", icon: Archive, capabilityId: "creative" }
  ]},
  { title: "平台核心", items: [
    { href: "/data-hub", label: "数据产品中台", icon: Database },
    { href: "/metrics", label: "指标语义中心", icon: BarChart3 },
    { href: "/digital", label: "数字治理", icon: Network, capabilityId: "digital" },
    { href: "/deliverables", label: "证据链与成果", icon: FileCheck2 }
  ]},
  { title: "治理与协同", items: [
    { href: "/institutions", label: "持牌机构协同", icon: Landmark, cockpitId: "collaboration-room" },
    { href: "/governance", label: "合规与权限", icon: ShieldCheck, adminOnly: true },
    { href: "/architecture", label: "目标架构", icon: Gauge }
  ]}
];

export function Sidebar() {
  const pathname = usePathname();
  const clientReady = useClientReady();
  const session = useDemoSession();
  const activeSession = clientReady ? session : null;
  const access = useRoleAccess(activeSession?.user.roleId);
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  return (
    <aside className={cn("fixed inset-y-0 left-0 z-40 flex flex-col bg-forest text-white transition-[width] duration-200", sidebarCollapsed ? "w-[66px]" : "w-[240px]", "max-md:w-[66px]")}>
      <div className={cn("flex h-[82px] items-center max-md:justify-center max-md:px-0", sidebarCollapsed ? "justify-center px-0" : "gap-3 px-6")}>
        <div className="grid h-11 w-11 shrink-0 rotate-45 place-items-center rounded-full border border-[#9c9369] text-[10px] text-gold"><span className="-rotate-45 font-bold">山河</span></div>
        <div className={cn("whitespace-nowrap max-md:hidden", sidebarCollapsed && "hidden")}><div className="text-xl font-semibold tracking-wide">山河文旅</div><div className="mt-1 text-[10px] tracking-[.18em] text-[#a8bbb4]">产业决策智库</div></div>
      </div>
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-3">
        {navGroups.filter((group) => !group.adminOnly || activeSession?.user.roleId === "platform-admin").map((group) => <nav key={group.title} className="mb-4">
          <div className={cn("px-3 pb-1.5 text-[10px] tracking-[.18em] text-[#769187] max-md:invisible", sidebarCollapsed && "invisible")}>{group.title}</div>
          <div className="space-y-1">{group.items.map(({ href, label, icon: Icon, badge, capabilityId, cockpitId, adminOnly }) => {
            const active = pathname.startsWith(href);
            const available = !access || (
              (!capabilityId || access.capabilityIds.includes(capabilityId)) &&
              (!cockpitId || access.cockpitIds.includes(cockpitId)) &&
              (!adminOnly || activeSession?.user.roleId === "platform-admin")
            );
            const content = <><Icon size={15} strokeWidth={1.6} className="shrink-0 text-[#a5c0b7] group-hover:text-white" /><span className={cn("whitespace-nowrap max-md:hidden", sidebarCollapsed && "hidden")}>{label}</span>{!available ? <LockKeyhole size={11} className={cn("ml-auto text-[#71877f] max-md:hidden", sidebarCollapsed && "hidden")} /> : badge ? <span className={cn("ml-auto rounded-full bg-[#52786d] px-1.5 text-[9px] max-md:hidden", sidebarCollapsed && "hidden")}>{badge}</span> : null}</>;
            const className = cn("group relative flex h-9 items-center gap-3 rounded-md px-3 text-[12px] transition", available ? "text-[#dce7e3] hover:bg-[#284d43] hover:text-white" : "cursor-not-allowed text-[#6f8780]", active && available && "bg-[#2c584c] text-white before:absolute before:inset-y-1 before:left-0 before:w-[3px] before:rounded-full before:bg-gold", "max-md:justify-center max-md:px-0", sidebarCollapsed && "justify-center px-0");
            if (!available) return <span key={href} title={`${label}（当前身份无权限）`} className={className}>{content}</span>;
            return <Link key={href} href={href} title={label} className={className}>
              {content}
            </Link>;
          })}</div>
        </nav>)}
      </div>
      <div className={cn("border-t border-white/10 py-3 max-md:hidden", sidebarCollapsed ? "px-0" : "px-4")}>
        <div className={cn("mb-3 rounded-md bg-white/5 p-2.5", sidebarCollapsed && "hidden")}><div className="flex items-center gap-2 text-[10px] text-[#c7d7d2]"><span className="h-1.5 w-1.5 rounded-full bg-[#75bc99]" />客户空间数据正常</div><div className="mt-1 text-[9px] text-[#769187]">权限隔离 · 全程审计</div></div>
        <div className={cn("flex items-center gap-2", sidebarCollapsed && "justify-center")}><div className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gold text-xs font-semibold text-white", sidebarCollapsed && "hidden")}>{activeSession?.user.roleLabel.slice(0, 1) ?? "山"}</div><div className={cn("min-w-0", sidebarCollapsed && "hidden")}><div className="truncate text-xs">{activeSession?.user.displayName ?? "演示用户"}</div><div className="truncate text-[9px] text-[#88a49a]">{activeSession?.user.roleLabel ?? "演示空间"}</div></div><button onClick={toggleSidebar} className={cn("rounded p-1 text-[#9eb4ad] hover:bg-white/10", sidebarCollapsed ? "mx-auto" : "ml-auto")} aria-label={sidebarCollapsed ? "展开侧栏" : "折叠侧栏"}>{sidebarCollapsed ? <ChevronRight size={14}/> : <ChevronLeft size={14}/>}</button></div>
      </div>
    </aside>
  );
}
