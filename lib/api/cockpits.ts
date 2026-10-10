import { ApiClient } from "@/lib/api/client";
import type { CockpitListResponse, UserRoleId } from "@/lib/types/access";

const client = new ApiClient();

export const cockpitApi = {
  list(roleId: UserRoleId) {
    return client.get<CockpitListResponse>(`/cockpits?roleId=${encodeURIComponent(roleId)}`);
  }
};
