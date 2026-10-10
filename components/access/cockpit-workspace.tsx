"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Bell, BriefcaseBusiness, GitBranch, LockKeyhole, LogOut, Mountain, Search, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";
import { CockpitDashboard } from "@/components/access/cockpit-dashboard";
import { canUseCockpitWithAccess, canUseItemWithAccess, getCockpit, getRole } from "@/lib/platform/access";
import { useRoleAccess } from "@/lib/platform/permissions";
import { logoutDemoSession, useClientReady, useDemoSession } from "@/lib/platform/session";
import type { CockpitId, CockpitItemKind } from "@/lib/types/access";
import { COCKPIT_DASHBOARDS } from "@/mocks/cockpit-dashboard";

export function CockpitWorkspace({ cockpitId }: { cockpitId: CockpitId }) {
  const router = useRouter();
  const clientReady = useClientReady();
  const cockpit = getCockpit(cockpitId);
  const session = useDemoSession();
  const access = useRoleAccess(session?.user.roleId);
  const [activeKind, setActiveKind] = useState<CockpitItemKind>("feature");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (clientReady && !session) router.replace("/login");
  }, [clientReady, router, session]);

  const role = session ? getRole(session.user.roleId) : null;
  const dashboard = COCKPIT_DASHBOARDS[cockpitId];
  const cockpitAvailable = Boolean(access && cockpit && canUseCockpitWithAccess(access, cockpit.id));
  const items = useMemo(() => cockpit?.items.filter((item) => item.kind === activeKind) ?? [], [activeKind, cockpit]);
  const visibleItems = cockpitId === "decision-center" && searchQuery.trim()
    ? items.filter((item) => `${item.title} ${item.note}`.includes(searchQuery.trim()))
    : items;
  const decisionNav = [
    { label: "首页", href: "/cockpits", available: true },
    { label: "数据洞察", href: "/dashboard", available: Boolean(access?.cockpitIds.includes("management")) },
    { label: "决策仓", href: "/cockpits/decision-center", available: Boolean(access?.cockpitIds.includes("decision-center")) },
    { label: "资源图谱", href: "/assets", available: Boolean(access?.capabilityIds.includes("assets")) },
    { label: "项目管理", href: "/project-control", available: Boolean(access?.capabilityIds.includes("project-control")) },
    { label: "监测预警", href: "/automation", available: Boolean(access?.cockpitIds.includes("management")) },
    { label: "知识中心", href: "/deliverables", available: Boolean(access?.cockpitIds.includes("decision-center")) }
  ].filter((item) => item.available);

  async function logout() {
    await logoutDemoSession();
    router.push("/login");
  }

  if (!clientReady || !cockpit || !session) {
    return <main className="grid min-h-screen place-items-center bg-[#0b211c] text-sm text-white/55" role="status">正在加载驾驶舱与图表数据...</main>;
  }

  if (!cockpitAvailable) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#0b211c] px-5 text-white">
        <section className="max-w-lg text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-[10px] border border-white/15 bg-white/[0.04] text-[#d8bb78]"><LockKeyhole size={24} /></span>
          <h1 className="mt-6 text-2xl font-semibold">当前身份无法进入{cockpit.title}</h1>
          <p className="mt-3 text-sm text-white/52">{session.user.roleLabel}暂未配置这个驾驶舱的使用权限。</p>
          <button onClick={() => router.replace("/cockpits")} className="mt-7 inline-flex h-10 items-center gap-2 rounded-[7px] bg-[#c2a35e] px-5 text-xs font-semibold text-[#10271f]"><ArrowLeft size={14} />返回驾驶舱选择</button>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0b211c] text-white">
      <header className="flex h-[64px] items-center justify-between gap-4 border-b border-white/10 px-4 sm:px-8 lg:px-12 2xl:h-[76px]">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center border border-[#d2b26a]/55 text-[#dfc27e] 2xl:h-11 2xl:w-11"><Mountain size={19} strokeWidth={1.5} /></span>
          <div>
            <div className="text-xs font-semibold 2xl:text-sm">山河文旅产业决策平台</div>
            <div className="mt-1 text-[9px] text-white/40 2xl:text-[10px]">{role?.spaceLabel}</div>
          </div>
        </div>
        {cockpitId === "decision-center" ? (
          <nav className="hidden min-w-0 items-center gap-4 xl:flex 2xl:gap-6" aria-label="决策仓导航">
            {decisionNav.map((item) => <button key={item.href} type="button" onClick={() => router.push(item.href)} className={`whitespace-nowrap border-b-2 py-5 text-[11px] transition 2xl:text-xs ${item.href === cockpit.href ? "border-[#d2b26a] text-white" : "border-transparent text-white/55 hover:text-white"}`}>{item.label}</button>)}
          </nav>
        ) : null}
        <div className="flex items-center gap-2">
          {cockpitId === "decision-center" ? (
            <>
              <label className="hidden h-9 w-[230px] items-center gap-2 rounded-[6px] border border-white/15 bg-white/[0.03] px-3 text-white/45 2xl:flex">
                <Search size={14} className="shrink-0" />
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} aria-label="搜索决策仓功能" placeholder="搜索议题、方案或工作流" className="w-full bg-transparent text-[11px] text-white outline-none placeholder:text-white/35" />
              </label>
              <button type="button" onClick={() => document.getElementById("cockpit-risks")?.scrollIntoView({ behavior: "smooth" })} className="hidden h-9 w-9 place-items-center rounded-[6px] border border-white/15 text-white/65 transition hover:text-[#e0c27d] 2xl:grid" aria-label="查看风险提示"><Bell size={15} /></button>
            </>
          ) : null}
          {session.user.roleId === "platform-admin" ? (
            <button onClick={() => router.push("/admin/permissions")} className="grid h-9 w-9 place-items-center rounded-[6px] border border-[#d2b26a]/35 text-[#dfc27e] sm:flex sm:w-auto sm:px-3" aria-label="用户权限管理"><ShieldCheck size={15} /><span className="ml-2 hidden text-[11px] sm:inline">权限管理</span></button>
          ) : null}
          <span className="inline-flex max-w-[150px] items-center gap-1.5 rounded-[6px] border border-[#d2b26a]/30 bg-[#d2b26a]/[0.06] px-2 py-2 text-[10px] text-[#e0c27d] sm:max-w-none sm:px-3" title={`当前身份：${role?.label ?? session.user.roleLabel}`}><UserRound size={13} className="shrink-0" /><span className="truncate">{role?.label ?? session.user.roleLabel}</span></span>
          <button onClick={logout} className="grid h-9 w-9 place-items-center rounded-[6px] border border-white/15 text-white/65" aria-label="退出登录"><LogOut size={15} /></button>
        </div>
      </header>

      <section className="w-full px-4 pb-8 pt-4 sm:px-6 lg:px-8 2xl:px-10 2xl:pt-5">
        <button onClick={() => router.push("/cockpits")} className="inline-flex items-center gap-2 text-[11px] text-white/55 transition hover:text-[#e0c27d] 2xl:text-xs"><ArrowLeft size={14} />返回驾驶舱选择</button>

        <section className="relative mt-3 min-h-[184px] overflow-hidden rounded-[10px] border border-white/10 bg-[#102b24] 2xl:min-h-[220px]">
          <Image src={cockpit.imageSrc} alt="" fill sizes="100vw" className="object-cover opacity-28" priority />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0d241e] via-[#0d241e]/90 to-[#0d241e]/35" />
          <div className="relative flex min-h-[184px] max-w-3xl flex-col justify-center px-5 py-5 sm:px-8 2xl:min-h-[220px] 2xl:max-w-4xl 2xl:px-10">
            <p className="text-[10px] tracking-[0.24em] text-[#d7ba75]">{cockpit.eyebrow}</p>
            <h1 className="mt-2 text-2xl font-semibold sm:text-3xl 2xl:text-4xl">{cockpit.title}</h1>
            <p className="mt-2 max-w-xl text-xs leading-5 text-white/65 sm:text-sm 2xl:max-w-3xl 2xl:text-base 2xl:leading-6">{cockpit.description}。按当前身份展示可用功能与工作流。</p>
            <div className="mt-3 flex flex-wrap gap-2 text-[10px]">
              <span className="rounded-[6px] border border-white/12 bg-white/[0.05] px-2.5 py-1.5">当前身份：{role?.label ?? session.user.roleLabel}</span>
              <span className="rounded-[6px] border border-[#b99a58]/30 bg-[#b99a58]/10 px-2.5 py-1.5 text-[#ddc17c]">演示数据</span>
            </div>
          </div>
        </section>

        <div className="mt-4 flex border-b border-white/10">
          {(["feature", "workflow"] as CockpitItemKind[]).map((kind) => (
            <button key={kind} onClick={() => setActiveKind(kind)} className={`relative min-w-24 px-4 py-2.5 text-xs transition 2xl:min-w-32 2xl:py-3 2xl:text-sm ${activeKind === kind ? "text-[#e1c681]" : "text-white/48 hover:text-white/75"}`}>
              {kind === "feature" ? "功能" : "工作流"}
              {activeKind === kind ? <span className="absolute inset-x-4 bottom-0 h-0.5 bg-[#c5a55e]" /> : null}
            </button>
          ))}
        </div>

        <section className="grid grid-cols-1 gap-2.5 py-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 2xl:gap-4 2xl:py-5">
          {visibleItems.map((item) => {
            const available = Boolean(access && canUseItemWithAccess(access, item));
            const Icon = item.kind === "feature" ? BriefcaseBusiness : GitBranch;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  if (!available) return;
                  if (item.href) router.push(item.href);
                  else toast.info(`${item.title}工作流演示入口已预留`);
                }}
                disabled={!available}
                className={`group min-h-[116px] rounded-[10px] border p-4 text-left transition 2xl:min-h-[140px] 2xl:p-5 ${available ? "border-white/12 bg-white/[0.045] hover:-translate-y-0.5 hover:border-[#c5a76b]/50 hover:bg-white/[0.075]" : "cursor-not-allowed border-white/[0.07] bg-black/15 text-white/38"}`}
              >
                <div className="flex items-center justify-between">
                  <span className={`grid h-9 w-9 place-items-center rounded-[7px] ${available ? "bg-[#d7b96f]/10 text-[#d7b96f]" : "bg-white/[0.04] text-white/35"}`}><Icon size={17} /></span>
                  {available ? <ArrowRight size={15} className="text-white/35 transition group-hover:translate-x-1 group-hover:text-[#d7b96f]" /> : <span className="inline-flex items-center gap-1.5 text-[10px]"><LockKeyhole size={13} />暂无权限</span>}
                </div>
                <h2 className="mt-3 text-xs font-medium 2xl:mt-4 2xl:text-sm">{item.title}</h2>
                <p className="mt-1 text-[10px] leading-4 text-white/45 2xl:text-[11px]">{item.note}</p>
              </button>
            );
          })}
          {visibleItems.length === 0 ? <p className="col-span-full py-8 text-center text-xs text-white/45">没有找到匹配的功能或工作流</p> : null}
        </section>
        <CockpitDashboard data={dashboard} />
      </section>
    </main>
  );
}
