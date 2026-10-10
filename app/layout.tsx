import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "山河文旅产业决策平台",
  description: "数据驱动的文旅产业决策操作系统"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><Providers><AppShell>{children}</AppShell></Providers></body>
    </html>
  );
}
