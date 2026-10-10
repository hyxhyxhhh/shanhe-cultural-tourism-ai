"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { ArrowRight, BriefcaseBusiness, LockKeyhole, LogOut, Mountain, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { cockpitApi } from "@/lib/api/cockpits";
import { canUseCockpitWithAccess, canUseItemWithAccess } from "@/lib/platform/access";
import { useRoleAccess } from "@/lib/platform/permissions";
import { logoutDemoSession, useClientReady, useDemoSession } from "@/lib/platform/session";
import type { CockpitSummary } from "@/lib/types/access";
import styles from "./cockpit-selector.module.css";

type DeckStyle = CSSProperties & { "--deck-index": number };

export function CockpitSelector() {
  const router = useRouter();
  const clientReady = useClientReady();
  const session = useDemoSession();
  const [baseCockpits, setBaseCockpits] = useState<CockpitSummary[]>([]);
  const [activeId, setActiveId] = useState("");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const access = useRoleAccess(session?.user.roleId);

  const cockpits = useMemo(() => baseCockpits.map((cockpit) => ({
    ...cockpit,
    available: access ? canUseCockpitWithAccess(access, cockpit.id) : false,
    items: cockpit.items.map((item) => ({
      ...item,
      available: access ? canUseItemWithAccess(access, item) : false
    }))
  })), [access, baseCockpits]);

  useEffect(() => {
    if (!clientReady) return;
    if (!session) {
      router.replace("/login");
      return;
    }

    let cancelled = false;
    cockpitApi.list(session.user.roleId)
      .then((response) => {
        if (cancelled) return;
        setBaseCockpits(response.items);
        const initial = response.items.find((cockpit) => access?.cockpitIds.includes(cockpit.id)) ?? response.items[0];
        setActiveId(initial?.id ?? "");
      })
      .catch(() => { if (!cancelled) setError("驾驶舱数据加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [access, clientReady, router, session]);

  const activeCockpit = cockpits.find((cockpit) => cockpit.id === activeId) ?? cockpits[0];
  const visibleFeatures = activeCockpit?.items.filter((item) => item.kind === "feature") ?? [];

  function enterCockpit(cockpit: CockpitSummary) {
    if (!cockpit.available) {
      toast.error(`${session?.user.roleLabel ?? "当前身份"}暂无该驾驶舱权限`);
      return;
    }
    router.push(cockpit.href);
  }

  async function logout() {
    await logoutDemoSession();
    router.push("/login");
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#0b211c] text-white">
      <header className="flex h-[78px] items-center justify-between border-b border-white/10 px-5 sm:px-9 lg:px-12">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center border border-[#d2b26a]/55 text-[#dfc27e]"><Mountain size={21} strokeWidth={1.5} /></span>
          <span>
            <span className="block text-sm font-semibold">山河文旅产业决策平台</span>
            <span className="mt-0.5 hidden text-[9px] tracking-[0.2em] text-white/42 sm:block">SHANHE TOURISM DECISION PLATFORM</span>
          </span>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          {session?.user.roleId === "platform-admin" ? (
            <button onClick={() => router.push("/admin/permissions")} className="inline-flex h-9 items-center gap-2 rounded-[6px] border border-[#d2b26a]/35 px-3 text-[11px] text-[#dfc27e] transition hover:border-[#d2b26a]/70 hover:bg-white/[0.04]">
              <ShieldCheck size={15} /> <span className="hidden sm:inline">用户权限管理</span>
            </button>
          ) : null}
          <div className="hidden text-right sm:block">
            <div className="text-[11px] text-white/82">{session?.user.roleLabel ?? "正在读取身份"}</div>
            <div className="mt-0.5 text-[9px] text-white/42">{session?.user.account ?? ""}</div>
          </div>
          <button onClick={logout} className="grid h-9 w-9 place-items-center rounded-[6px] border border-white/15 text-white/65 transition hover:border-[#c5a76b]/60 hover:text-[#e0c27d]" aria-label="退出登录"><LogOut size={16} /></button>
        </div>
      </header>

      <section className="mx-auto max-w-[1800px] px-3 pb-10 pt-6 sm:px-6 lg:px-8">
        <div className="text-center">
          <p className="text-[10px] uppercase tracking-[0.32em] text-[#c7a966]">Select Your Cockpit</p>
          <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">选择驾驶舱</h1>
          <p className="mt-2 text-xs text-white/48">悬停查看功能，带锁驾驶舱当前身份不可进入</p>
        </div>

        {loading ? <div className="grid h-[520px] place-items-center text-sm text-white/50">正在加载驾驶舱...</div> : null}
        {error ? <div className="grid h-[520px] place-items-center text-sm text-[#e3a69c]">{error}</div> : null}

        {!loading && !error ? (
          <div className={styles.deckViewport} onMouseLeave={() => setHoveredId(null)}>
            <div className={styles.deck}>
              {cockpits.map((cockpit, index) => {
                const active = hoveredId === cockpit.id;
                const inactive = Boolean(hoveredId && hoveredId !== cockpit.id);
                const locked = !cockpit.available;
                return (
                  <button
                    key={cockpit.id}
                    type="button"
                    className={`${styles.deckCard} ${active ? styles.active : ""} ${inactive ? styles.inactive : ""} ${locked ? styles.locked : ""}`}
                    style={{ "--deck-index": index } as DeckStyle}
                    onMouseEnter={() => { setActiveId(cockpit.id); setHoveredId(cockpit.id); }}
                    onFocus={() => { setActiveId(cockpit.id); setHoveredId(cockpit.id); }}
                    onBlur={() => setHoveredId(null)}
                    onClick={() => enterCockpit(cockpit)}
                    aria-label={locked ? `${cockpit.title}，当前身份无权限` : `进入${cockpit.title}`}
                  >
                    <Image src={cockpit.imageSrc} alt="" fill sizes="(max-width: 720px) 72vw, 310px" className="object-cover" priority={index < 3} />
                    <span className={styles.cardShade} />
                    {locked ? <span className={styles.lockBadge}><LockKeyhole size={15} /> 暂无权限</span> : null}
                    <span className={styles.cardCopy}>
                      <span className="text-[9px] uppercase tracking-[0.19em] text-[#ddc17c]">{cockpit.eyebrow}</span>
                      <strong className="mt-2 block text-xl font-semibold">{cockpit.title}</strong>
                      <span className="mt-2 block text-[11px] leading-5 text-white/68">{cockpit.description}</span>
                      <span className="mt-5 inline-flex items-center gap-1.5 text-[10px] font-medium text-[#e1c681]">
                        {locked ? "查看权限" : "进入驾驶舱"} <ArrowRight size={13} />
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {activeCockpit ? (
          <section className="mx-auto max-w-[1580px] border-t border-white/10 pt-5">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <p className="text-[10px] tracking-[0.2em] text-[#c8aa68]">{activeCockpit.title}</p>
                <h2 className="mt-1 text-lg font-medium">功能预览</h2>
              </div>
              <span className="text-[10px] text-white/40">工作流进入驾驶舱后查看</span>
            </div>

            <div className="grid grid-cols-1 gap-3 pb-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {visibleFeatures.map((item) => {
                const available = Boolean(activeCockpit.available && item.available !== false);
                return (
                  <article key={item.id} className={`min-h-[108px] rounded-[10px] border p-4 transition ${available ? "border-white/12 bg-white/[0.045] hover:border-[#c5a76b]/45 hover:bg-white/[0.07]" : "border-white/[0.07] bg-black/15 text-white/45"}`}>
                    <div className="flex items-center justify-between gap-2 text-[10px]">
                      <span className="flex items-center gap-2 text-[#9cbd94]"><BriefcaseBusiness size={14} />功能</span>
                      {!available ? <LockKeyhole size={13} /> : null}
                    </div>
                    <h3 className="mt-3 text-sm font-medium">{item.title}</h3>
                    <p className="mt-1.5 text-[10px] leading-4 text-white/47">{item.note}</p>
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
