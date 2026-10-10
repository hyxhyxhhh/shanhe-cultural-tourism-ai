"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  ChevronDown,
  Eye,
  EyeOff,
  Landmark,
  LockKeyhole,
  Mountain,
  QrCode,
  Smartphone,
  UserPlus,
  UserRound,
  MessageCircle
} from "lucide-react";
import { authApi } from "@/lib/api/auth";
import { ROLE_OPTIONS } from "@/lib/platform/access";
import { saveDemoSession } from "@/lib/platform/session";
import type { UserRoleId } from "@/lib/types/access";

interface LoginScreenProps {
  backgroundVideo?: string;
  returnTo: string;
}

export function LoginScreen({ backgroundVideo, returnTo }: LoginScreenProps) {
  const router = useRouter();
  const [roleId, setRoleId] = useState<UserRoleId | "">("");
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [alternateSubmitting, setAlternateSubmitting] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function handleAlternateLogin(
    method: "register" | "wechat" | "phone" | "wechatQr",
    label: string
  ) {
    setError("");
    setAlternateSubmitting(method);

    const request = { roleId, account: account.trim(), password };

    try {
      if (method === "register") {
        await authApi.register(request);
      } else if (method === "wechat") {
        await authApi.wechatLogin(request);
      } else if (method === "phone") {
        await authApi.phoneLogin(request);
      } else {
        await authApi.wechatQrLogin(request);
      }
      setError(`${label}已完成`);
    } catch (alternateError) {
      const message = alternateError instanceof Error ? alternateError.message : "";
      setError(message.includes("501") ? `${label}接口暂未接入（501）` : `${label}失败，请稍后重试`);
    } finally {
      setAlternateSubmitting(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!roleId) {
      setError("请选择身份");
      return;
    }

    if (!account.trim()) {
      setError("请输入账号");
      return;
    }

    if (!password) {
      setError("请输入密码");
      return;
    }

    setSubmitting(true);

    try {
      const session = await authApi.login({ roleId, account, password });
      saveDemoSession(session);
      router.replace(returnTo);
    } catch {
      setError("账号或密码不正确，请重新输入");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[#102b24] text-white">
      {backgroundVideo ? (
        <video
          className="absolute inset-0 -z-20 h-full w-full object-cover"
          src={backgroundVideo}
          autoPlay
          muted
          loop
          playsInline
          aria-hidden="true"
        />
      ) : null}
      <div className="absolute inset-0 -z-10 bg-[#102b24]/65" />

      <header className="absolute inset-x-0 top-0 z-10 flex items-center px-[5vw] py-7">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center border border-[#d7b86e]/60 bg-[#102b24]/70 text-[#e1c681] backdrop-blur-sm">
            <Mountain size={22} strokeWidth={1.5} />
          </span>
          <span>
            <span className="block text-base font-semibold">山河文旅</span>
            <span className="mt-0.5 block text-[9px] tracking-[0.2em] text-white/60">SHANHE TOURISM</span>
          </span>
        </div>
      </header>

      <div className="mx-auto grid min-h-screen max-w-[1800px] items-center gap-12 px-[4vw] py-24 lg:grid-cols-[minmax(0,1fr)_minmax(460px,520px)] lg:gap-[7vw]">
        <section className="login-slide-from-left min-w-0 max-w-[760px] self-center lg:relative lg:-left-2 lg:-top-12">
          <div className="mb-5 flex items-center gap-3 text-[#e0c27d]">
            <span className="h-px w-10 bg-current" />
            <span className="text-[10px] uppercase tracking-[0.3em]">Tourism Decision Platform</span>
          </div>
          <h1 className="max-w-full break-words text-[27px] font-semibold leading-tight tracking-[0] sm:text-5xl lg:text-[58px]">
            山河文旅产业决策平台
          </h1>
          <p className="mt-6 text-lg text-white/78 sm:text-xl">数据驱动的文旅产业决策操作系统</p>
          <p className="mt-3 text-sm text-white/56">连接数据、决策、专业任务和经营结果</p>
          <div className="mt-10 flex items-center gap-7 text-[11px] text-white/45">
            <span className="inline-flex items-center gap-2"><Landmark size={14} />产业决策</span>
            <span className="inline-flex items-center gap-2"><Building2 size={14} />专业协同</span>
          </div>
        </section>

        <section className="login-slide-from-right min-w-0 w-full rounded-[14px] border border-white/25 bg-[#f5f6ef]/[0.92] p-8 text-[#18332c] shadow-[0_30px_90px_rgba(3,18,14,0.28)] backdrop-blur-xl sm:p-10">
          <div className="mb-8">
            <p className="text-[10px] uppercase tracking-[0.24em] text-[#7f704f]">Account Access</p>
            <h2 className="mt-3 text-3xl font-semibold">欢迎登录</h2>
            <p className="mt-2 text-xs text-[#61736d]">请选择身份并登录您的工作空间</p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-xs font-medium">当前选择的身份</span>
              <span className="relative block">
                <UserRound className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6d7e78]" size={17} />
                <select
                  value={roleId}
                  onChange={(event) => {
                    setRoleId(event.target.value as UserRoleId);
                    setError("");
                  }}
                  className="h-12 w-full appearance-none rounded-[6px] border border-[#cad3cc] bg-white/75 pl-11 pr-11 text-sm outline-none transition focus:border-[#a78b50] focus:ring-2 focus:ring-[#c7ab6c]/20"
                >
                  <option value="" disabled>请选择身份</option>
                  {ROLE_OPTIONS.map((role) => <option key={role.id} value={role.id}>{role.label}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[#6d7e78]" size={17} />
              </span>
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-medium">账号</span>
              <span className="relative block">
                <UserRound className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6d7e78]" size={17} />
                <input
                  value={account}
                  onChange={(event) => setAccount(event.target.value)}
                  className="h-12 w-full rounded-[6px] border border-[#cad3cc] bg-white/75 pl-11 pr-4 outline-none transition placeholder:text-[#97a39f] focus:border-[#a78b50] focus:ring-2 focus:ring-[#c7ab6c]/20"
                  placeholder="请输入账号"
                  autoComplete="username"
                />
              </span>
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-medium">密码</span>
              <span className="relative block">
                <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6d7e78]" size={17} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-12 w-full rounded-[6px] border border-[#cad3cc] bg-white/75 pl-11 pr-12 outline-none transition placeholder:text-[#97a39f] focus:border-[#a78b50] focus:ring-2 focus:ring-[#c7ab6c]/20"
                  placeholder="请输入密码"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute right-3 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center text-[#6d7e78] transition hover:text-[#18332c]"
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
            </label>

            {error ? <p role="alert" className="text-xs text-[#a84f44]">{error}</p> : null}

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 h-12 w-full bg-[#b99a58] text-sm font-semibold text-[#142c25] transition hover:bg-[#c9aa65] active:scale-[0.99] disabled:cursor-wait disabled:opacity-65"
            >
              {submitting ? "正在登录..." : "登录"}
            </button>

            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                type="button"
                onClick={() => handleAlternateLogin("register", "注册")}
                disabled={Boolean(alternateSubmitting)}
                className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-[6px] border border-[#c7d0ca] bg-white/55 px-1.5 text-[11px] text-[#35534a] transition hover:border-[#a78b50] hover:bg-white/80 disabled:cursor-wait disabled:opacity-60 sm:px-2 sm:text-xs"
              >
                <UserPlus className="shrink-0" size={15} aria-hidden="true" />
                <span>注册</span>
              </button>
              <button
                type="button"
                onClick={() => handleAlternateLogin("wechat", "微信登录")}
                disabled={Boolean(alternateSubmitting)}
                className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-[6px] border border-[#c7d0ca] bg-white/55 px-1.5 text-[11px] text-[#35534a] transition hover:border-[#a78b50] hover:bg-white/80 disabled:cursor-wait disabled:opacity-60 sm:px-2 sm:text-xs"
              >
                <MessageCircle className="shrink-0" size={15} aria-hidden="true" />
                <span>微信登录</span>
              </button>
              <button
                type="button"
                onClick={() => handleAlternateLogin("phone", "手机号登录")}
                disabled={Boolean(alternateSubmitting)}
                className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-[6px] border border-[#c7d0ca] bg-white/55 px-1.5 text-[11px] text-[#35534a] transition hover:border-[#a78b50] hover:bg-white/80 disabled:cursor-wait disabled:opacity-60 sm:px-2 sm:text-xs"
              >
                <Smartphone className="shrink-0" size={15} aria-hidden="true" />
                <span>手机号登录</span>
              </button>
              <button
                type="button"
                onClick={() => handleAlternateLogin("wechatQr", "微信扫码登录")}
                disabled={Boolean(alternateSubmitting)}
                className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-[6px] border border-[#c7d0ca] bg-white/55 px-1.5 text-[11px] text-[#35534a] transition hover:border-[#a78b50] hover:bg-white/80 disabled:cursor-wait disabled:opacity-60 sm:px-2 sm:text-xs"
              >
                <QrCode className="shrink-0" size={15} aria-hidden="true" />
                <span>微信扫码登录</span>
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
