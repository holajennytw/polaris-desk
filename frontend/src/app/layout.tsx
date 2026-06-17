// ============================================================
// app/layout.tsx — Root Layout
//   • 載入 globals.css（內含 Tailwind v4 + 原型設計系統 + bridge）
//   • 掛 next/font 變數到 <html>
//   • 以 <link> 載入 Noto Sans TC（CJK）
//   • 亮/暗交 <Providers>（next-themes）控：data-theme 由 provider 寫，預設 light
//     —— 不再寫死 data-theme；<html> 加 suppressHydrationWarning（next-themes 必需）
// ============================================================
import "./globals.css";
import type { Metadata } from "next";
import { fontVars } from "./fonts";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Polaris Desk",
  description: "Research terminal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant" className={fontVars} suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        {/* CJK：Noto Sans TC 當 --sans/--display 的中文 fallback */}
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
