import { ApiClient } from "@/lib/api/client";
import type { PermissionMatrixResponse, PermissionUpdateResponse, RoleAccess, UserRoleId } from "@/lib/types/access";

const client = new ApiClient();

export const permissionsApi = {
  list() {
    return client.get<PermissionMatrixResponse>("/admin/permissions");
  },
  update(roleId: UserRoleId, access: RoleAccess) {
    return client.put<PermissionUpdateResponse>(`/admin/permissions/${roleId}`, { access });
  },
  reset(roleId: UserRoleId) {
    return client.delete<PermissionUpdateResponse>(`/admin/permissions/${roleId}`);
  }
};
