import { ROLE_ACCESS, ROLE_OPTIONS, WORKFLOW_IDS } from "@/lib/platform/access";
import type { CapabilityId, CockpitId, RoleAccess, UserRoleId } from "@/lib/types/access";

const cockpitIds: CockpitId[] = ["management", "ai-advisor", "decision-center", "task-center", "collaboration-room"];
const capabilityIds: CapabilityId[] = ["strategy", "assets", "operations", "event-agent", "marketing", "design", "project-control", "creative", "digital", "implementation", "capital"];

function isRoleId(value: string): value is UserRoleId {
  return ROLE_OPTIONS.some((role) => role.id === value);
}

function isAccess(value: unknown): value is RoleAccess {
  if (!value || typeof value !== "object") return false;
  const access = value as Partial<RoleAccess>;
  return Array.isArray(access.cockpitIds)
    && access.cockpitIds.every((id) => cockpitIds.includes(id))
    && Array.isArray(access.capabilityIds)
    && access.capabilityIds.every((id) => capabilityIds.includes(id))
    && Array.isArray(access.workflowIds)
    && access.workflowIds.every((id) => WORKFLOW_IDS.includes(id));
}

export async function PUT(request: Request, { params }: { params: Promise<{ roleId: string }> }) {
  const { roleId } = await params;
  if (!isRoleId(roleId)) return Response.json({ message: "身份不存在" }, { status: 404 });
  if (roleId === "platform-admin") return Response.json({ message: "平台管理员权限不可修改" }, { status: 400 });

  const body = (await request.json()) as { access?: unknown };
  if (!isAccess(body.access)) return Response.json({ message: "权限数据格式不正确" }, { status: 400 });

  return Response.json({
    roleId,
    access: body.access,
    persisted: false,
    message: "权限接口已接收，当前阶段由前端浏览器保存；后端接入后在此持久化。"
  });
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ roleId: string }> }) {
  const { roleId } = await params;
  if (!isRoleId(roleId)) return Response.json({ message: "身份不存在" }, { status: 404 });
  if (roleId === "platform-admin") return Response.json({ message: "平台管理员权限不可重置" }, { status: 400 });

  return Response.json({
    roleId,
    access: ROLE_ACCESS[roleId],
    persisted: false,
    message: "已恢复代码中的默认权限；后端接入后在此持久化。"
  });
}
