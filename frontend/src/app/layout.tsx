import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Cortex · 你的 AI 外脑", description: "连接你的知识、记忆与行动的本地 AI 工作台" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
