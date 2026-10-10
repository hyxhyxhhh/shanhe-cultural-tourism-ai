export type UserRoleId =
  | "government"
  | "group-executive"
  | "scenic-operator"
  | "creative-design"
  | "project-team"
  | "licensed-institution"
  | "expert-advisor"
  | "management"
  | "platform-admin";

export type CockpitId =
  | "management"
  | "ai-advisor"
  | "decision-center"
  | "task-center"
  | "collaboration-room";

export type CapabilityId =
  | "strategy"
  | "assets"
  | "operations"
  | "event-agent"
  | "marketing"
  | "design"
  | "project-control"
  | "creative"
  | "digital"
  | "implementation"
  | "capital";

export type WorkflowId =
  | "project-lifecycle"
  | "project-decision"
  | "investment-construction"
  | "financial-risk"
  | "operating-growth";

export interface RoleOption {
  id: UserRoleId;
  label: string;
  spaceLabel: string;
}

export interface RoleAccess {
  cockpitIds: CockpitId[];
  capabilityIds: CapabilityId[];
  workflowIds: WorkflowId[];
}

export type PermissionMatrix = Record<UserRoleId, RoleAccess>;

export interface PermissionMatrixResponse {
  items: PermissionMatrix;
}

export interface PermissionUpdateResponse {
  roleId: UserRoleId;
  access: RoleAccess;
  persisted: boolean;
  message: string;
}

export interface LoginRequest {
  roleId: UserRoleId;
  account: string;
  password: string;
}

export interface SessionUser {
  userId: string;
  account: string;
  displayName: string;
  roleId: UserRoleId;
  roleLabel: string;
}

export interface LoginResponse {
  user: SessionUser;
}

export interface AuthPlaceholderResponse {
  code: "NOT_IMPLEMENTED";
  message: string;
}

export type CockpitItemKind = "feature" | "workflow";

export interface CockpitPreviewItem {
  id: string;
  kind: CockpitItemKind;
  title: string;
  note: string;
  href?: string;
  permissionId?: CapabilityId | WorkflowId;
  available?: boolean;
}

export interface CockpitSummary {
  id: CockpitId;
  title: string;
  eyebrow: string;
  description: string;
  imageSrc: string;
  href: string;
  available?: boolean;
  items: CockpitPreviewItem[];
}

export interface CockpitListResponse {
  items: CockpitSummary[];
}
