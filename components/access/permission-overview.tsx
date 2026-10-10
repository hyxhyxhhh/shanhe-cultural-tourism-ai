"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  Check,
  LockKeyhole,
  Mountain,
  Pencil,
  RotateCcw,
  Save,
  ShieldCheck,
  Square,
  X
} from "lucide-react";
import { toast } from "sonner";
import { permissionsApi } from "@/lib/api/permissions";
import { COCKPITS, ROLE_OPTIONS } from "@/lib/platform/access";
import { saveRoleAccess, usePermissionMatrix } from "@/lib/platform/permissions";
import { useClientReady, useDemoSession } from "@/lib/platform/session";
import type { CapabilityId, CockpitId, RoleAccess, UserRoleId, WorkflowId } from "@/lib/types/access";

const CAPABILITIES: Array<{ id: CapabilityId; label: string }> = [
  { id: "strategy", label: "战略策划" },
  { id: "assets", label: "资产盘活" },
  { id: "operations", label: "运营招商" },
  { id: "event-agent", label: "活动策划" },
  { id: "marketing", label: "营销策划" },
  { id: "design", label: "专项设计" },
  { id: "project-control", label: "项目管控" },
  { id: "creative", label: "文创产品设计" },
  { id: "digital", label: "数字系统" },
  { id: "implementation", label: "实施 PMO" },
  { id: "capital", label: "资本化前置" }
];

const WORKFLOWS: Array<{ id: WorkflowId; label: string }> = [
  { id: "project-lifecycle", label: "项目全生命周期" },
  { id: "project-decision", label: "项目决策" },
  { id: "investment-construction", label: "投资建设" },
  { id: "financial-risk", label: "金融风控" },
  { id: "operating-growth", label: "经营增长" }
];

function cloneAccess(access: RoleAccess): RoleAccess {
  return {
    cockpitIds: [...access.cockpitIds],
    capabilityIds: [...access.capabilityIds],
    workflowIds: [...access.workflowIds]
  };
}

export function PermissionOverview() {
  const router = useRouter();
  const clientReady = useClientReady();
  const session = useDemoSession();
  const permissionMatrix = usePermissionMatrix();
  const [selectedRoleId, setSelectedRoleId] = useState<UserRoleId>("government");
  const [draftAccess, setDraftAccess] = useState<RoleAccess | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (clientReady && !session) router.replace("/login");
  }, [clientReady, router, session]);

  if (!clientReady || !session) {
    return <main className="grid min-h-screen place-items-center bg-[#0b211c] text-sm text-white/55">正在读取管理员身份...</main>;
  }

  if (session.user.roleId !== "platform-admin") {
    return (
      <main className="grid min-h-screen place-items-center bg-[#0b211c] px-5 text-center text-white">
        <div><LockKeyhole className="mx-auto text-[#d8bb78]" size={28} /><h1 className="mt-5 text-xl font-semibold">仅平台管理员可管理用户权限</h1><button onClick={() => router.replace("/cockpits")} className="mt-6 rounded-[7px] bg-[#c2a35e] px-5 py-3 text-xs font-semibold text-[#10271f]">返回驾驶舱选择</button></div>
      </main>
    );
  }

  const selectedRole = ROLE_OPTIONS.find((role) => role.id === selectedRoleId) ?? ROLE_OPTIONS[0];
  const savedAccess = permissionMatrix[selectedRole.id];
  const access = draftAccess ?? savedAccess;
  const isEditing = draftAccess !== null;
  const isPlatformAdmin = selectedRole.id === "platform-admin";

  function selectRole(roleId: UserRoleId) {
    setDraftAccess(null);
    setSelectedRoleId(roleId);
  }

  function startEditing() {
    if (isPlatformAdmin) return;
    setDraftAccess(cloneAccess(savedAccess));
  }

  function updateAccess<K extends keyof RoleAccess>(key: K, values: RoleAccess[K]) {
    setDraftAccess((current) => current ? { ...current, [key]: values } : current);
  }

  function toggleCockpit(id: CockpitId) {
    if (!draftAccess) return;
    updateAccess("cockpitIds", draftAccess.cockpitIds.includes(id)
      ? draftAccess.cockpitIds.filter((item) => item !== id)
      : [...draftAccess.cockpitIds, id]);
  }

  function toggleCapability(id: CapabilityId) {
    if (!draftAccess) return;
    updateAccess("capabilityIds", draftAccess.capabilityIds.includes(id)
      ? draftAccess.capabilityIds.filter((item) => item !== id)
      : [...draftAccess.capabilityIds, id]);
  }

  function toggleWorkflow(id: WorkflowId) {
    if (!draftAccess) return;
    updateAccess("workflowIds", draftAccess.workflowIds.includes(id)
      ? draftAccess.workflowIds.filter((item) => item !== id)
      : [...draftAccess.workflowIds, id]);
  }

  async function saveChanges() {
    if (!draftAccess || isPlatformAdmin) return;
    setSaving(true);
    try {
      const response = await permissionsApi.update(selectedRole.id, draftAccess);
      saveRoleAccess(selectedRole.id, response.access);
      setDraftAccess(null);
      toast.success(`${selectedRole.label}的权限已更新`, { description: "当前浏览器已立即生效，后端持久化接口已预留。" });
    } catch {
      toast.error("权限保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  async function restoreDefaults() {
    if (isPlatformAdmin) return;
    setSaving(true);
    try {
      const response = await permissionsApi.reset(selectedRole.id);
      saveRoleAccess(selectedRole.id, response.access);
      setDraftAccess(null);
      toast.success(`${selectedRole.label}已恢复默认权限`);
    } catch {
      toast.error("恢复默认权限失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#edf1ec] text-[#162724]">
      <header className="flex h-[72px] items-center justify-between border-b border-[#d7ded9] bg-[#102b24] px-4 text-white sm:px-8 lg:px-12">
        <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center border border-[#d2b26a]/55 text-[#dfc27e]"><Mountain size={19} /></span><div><div className="text-xs font-semibold">山河文旅产业决策平台</div><div className="mt-1 text-[9px] text-white/40">后台管理空间</div></div></div>
        <span className="inline-flex items-center gap-2 rounded-[6px] border border-[#d2b26a]/30 px-3 py-2 text-[10px] text-[#dfc27e]"><ShieldCheck size={14} />平台管理员</span>
      </header>

      <section className="mx-auto max-w-[1660px] px-4 py-7 sm:px-8 lg:px-12">
        <button onClick={() => router.push("/cockpits")} className="inline-flex items-center gap-2 text-[11px] text-[#5f746d] hover:text-[#173d33]"><ArrowLeft size={14} />返回驾驶舱选择</button>
        <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-[10px] uppercase tracking-[0.22em] text-[#8f7747]">Permission Management</p><h1 className="mt-2 text-3xl font-semibold">用户权限管理</h1><p className="mt-2 text-xs text-[#60736d]">配置九个身份可进入的驾驶舱，以及可使用的功能和工作流。</p></div>
          <span className="rounded-[6px] border border-[#c9b37d] bg-[#f7f0dd] px-3 py-2 text-[10px] text-[#80682f]">前端可修改 · 接口已预留 · 当前浏览器立即生效</span>
        </div>

        <div className="mt-7 grid gap-5 lg:grid-cols-[290px_minmax(0,1fr)]">
          <aside className="rounded-[8px] border border-[#d6ddd8] bg-white p-2 shadow-sm">
            <div className="px-3 pb-2 pt-3 text-[10px] font-medium text-[#73847e]">选择身份（9）</div>
            <div className="space-y-1">
              {ROLE_OPTIONS.map((role) => (
                <button key={role.id} onClick={() => selectRole(role.id)} disabled={saving} className={`w-full rounded-[6px] px-3 py-3 text-left transition disabled:cursor-wait ${selectedRoleId === role.id ? "bg-[#173d33] text-white" : "text-[#29433c] hover:bg-[#edf3ef]"}`}>
                  <span className="block text-xs font-medium">{role.label}</span>
                  <span className={`mt-1 block text-[9px] ${selectedRoleId === role.id ? "text-white/55" : "text-[#82908b]"}`}>{role.spaceLabel}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="overflow-hidden rounded-[8px] border border-[#d6ddd8] bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#e0e5e1] bg-[#f8faf7] px-5 py-4">
              <div><h2 className="text-base font-semibold">{selectedRole.label}</h2><p className="mt-1 text-[10px] text-[#71827c]">{isPlatformAdmin ? "平台管理员固定拥有全部权限，不允许修改" : selectedRole.spaceLabel}</p></div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <div className="mr-1 flex gap-2 text-[10px]"><span className="rounded-full bg-[#e2eee8] px-3 py-1.5 text-[#356458]">{access.cockpitIds.length} 个驾驶舱</span><span className="rounded-full bg-[#f3ecdc] px-3 py-1.5 text-[#80682f]">{access.capabilityIds.length} 项功能</span><span className="rounded-full bg-[#e9e8f2] px-3 py-1.5 text-[#5e587e]">{access.workflowIds.length} 条工作流</span></div>
                {isEditing ? (
                  <>
                    <button onClick={() => setDraftAccess(null)} disabled={saving} className="inline-flex h-9 items-center gap-2 rounded-[6px] border border-[#ccd5d0] bg-white px-3 text-[10px] text-[#536961] hover:bg-[#f1f5f2] disabled:opacity-50"><X size={13} />取消</button>
                    <button onClick={saveChanges} disabled={saving} className="inline-flex h-9 items-center gap-2 rounded-[6px] bg-[#173d33] px-4 text-[10px] font-medium text-white hover:bg-[#245346] disabled:opacity-50"><Save size={13} />{saving ? "保存中..." : "保存修改"}</button>
                  </>
                ) : (
                  <>
                    <button onClick={restoreDefaults} disabled={saving || isPlatformAdmin} title={isPlatformAdmin ? "平台管理员权限不可重置" : "恢复代码中的默认权限"} className="inline-flex h-9 items-center gap-2 rounded-[6px] border border-[#ccd5d0] bg-white px-3 text-[10px] text-[#536961] hover:bg-[#f1f5f2] disabled:cursor-not-allowed disabled:opacity-45"><RotateCcw size={13} />恢复默认</button>
                    <button onClick={startEditing} disabled={saving || isPlatformAdmin} title={isPlatformAdmin ? "平台管理员固定拥有全部权限" : "修改当前身份权限"} className="inline-flex h-9 items-center gap-2 rounded-[6px] bg-[#173d33] px-4 text-[10px] font-medium text-white hover:bg-[#245346] disabled:cursor-not-allowed disabled:bg-[#879690]"><Pencil size={13} />编辑权限</button>
                  </>
                )}
              </div>
            </div>

            <PermissionSection title="驾驶舱" description="选择驾驶舱页面始终展示全部五项，未开放项显示锁。" editing={isEditing} onSelectAll={() => updateAccess("cockpitIds", COCKPITS.map((item) => item.id))} onClear={() => updateAccess("cockpitIds", [])}>
              {COCKPITS.map((cockpit) => <PermissionItem key={cockpit.id} label={cockpit.title} available={access.cockpitIds.includes(cockpit.id)} editing={isEditing} onClick={() => toggleCockpit(cockpit.id)} />)}
            </PermissionSection>
            <PermissionSection title="功能" description="进入驾驶舱后保持同一页面结构，未开放功能显示锁且不可点击。" editing={isEditing} onSelectAll={() => updateAccess("capabilityIds", CAPABILITIES.map((item) => item.id))} onClear={() => updateAccess("capabilityIds", [])}>
              {CAPABILITIES.map((item) => <PermissionItem key={item.id} label={item.label} available={access.capabilityIds.includes(item.id)} editing={isEditing} onClick={() => toggleCapability(item.id)} />)}
            </PermissionSection>
            <PermissionSection title="工作流" description="工作流只在驾驶舱内部展示，未开放项显示锁。" editing={isEditing} onSelectAll={() => updateAccess("workflowIds", WORKFLOWS.map((item) => item.id))} onClear={() => updateAccess("workflowIds", [])}>
              {WORKFLOWS.map((item) => <PermissionItem key={item.id} label={item.label} available={access.workflowIds.includes(item.id)} editing={isEditing} onClick={() => toggleWorkflow(item.id)} />)}
            </PermissionSection>
          </section>
        </div>
      </section>
    </main>
  );
}

function PermissionSection({ title, description, editing, onSelectAll, onClear, children }: { title: string; description: string; editing: boolean; onSelectAll: () => void; onClear: () => void; children: ReactNode }) {
  return (
    <section className="border-b border-[#e3e8e4] px-5 py-5 last:border-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="text-sm font-semibold">{title}</h3><p className="mt-1 text-[10px] text-[#7a8b85]">{description}</p></div>
        {editing ? <div className="flex gap-2"><button onClick={onSelectAll} className="rounded-[5px] border border-[#cbd8d1] px-2.5 py-1.5 text-[9px] text-[#356458] hover:bg-[#edf5f1]">全选</button><button onClick={onClear} className="rounded-[5px] border border-[#ded5ca] px-2.5 py-1.5 text-[9px] text-[#80682f] hover:bg-[#f7f2e8]">清空</button></div> : null}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{children}</div>
    </section>
  );
}

function PermissionItem({ label, available, editing, onClick }: { label: string; available: boolean; editing: boolean; onClick: () => void }) {
  const className = `flex min-h-11 w-full items-center gap-2 rounded-[6px] border px-3 text-left text-xs transition ${available ? "border-[#cfe0d7] bg-[#f0f6f2] text-[#315f52]" : "border-[#e3e6e4] bg-[#f7f8f7] text-[#99a39f]"} ${editing ? "cursor-pointer hover:border-[#8eb4a5] hover:shadow-sm" : "cursor-default"}`;
  const content = <>{available ? <Check size={14} /> : editing ? <Square size={13} /> : <LockKeyhole size={13} />}<span>{label}</span><span className="ml-auto text-[9px]">{available ? "已开放" : "未开放"}</span></>;
  return editing ? <button type="button" onClick={onClick} aria-pressed={available} className={className}>{content}</button> : <div className={className}>{content}</div>;
}
