import { ApiClient } from "@/lib/api/client";
import type { AuthPlaceholderResponse, LoginRequest, LoginResponse } from "@/lib/types/access";

const client = new ApiClient();

export const authApi = {
  login(request: LoginRequest) {
    return client.post<LoginResponse>("/auth/login", request);
  },
  me() {
    return client.get<LoginResponse>("/auth/me");
  },
  logout() {
    return client.post<void>("/auth/logout");
  },
  register(request: unknown) {
    return client.post<AuthPlaceholderResponse>("/auth/register", request);
  },
  wechatLogin(request: unknown) {
    return client.post<AuthPlaceholderResponse>("/auth/wechat", request);
  },
  phoneLogin(request: unknown) {
    return client.post<AuthPlaceholderResponse>("/auth/phone", request);
  },
  wechatQrLogin(request: unknown) {
    return client.post<AuthPlaceholderResponse>("/auth/wechat/qr", request);
  }
};
