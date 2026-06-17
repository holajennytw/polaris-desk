"use client";
// ============================================================
// app/providers.tsx — 全域 client provider
//   next-themes：對應原型 app.jsx 的 <html data-theme> + localStorage('polaris-theme')
//   • attribute="data-theme" → 寫到 <html data-theme="light|dark">，與 polaris.css 完全一致
//   • defaultTheme="light"   → 原型預設亮色（暖紙）
//   • storageKey 沿用原型的 'polaris-theme'，舊使用者偏好可無痛接續
//   • enableSystem=false     → 原型不跟系統色，只在亮/暗間切
// ============================================================
import { ThemeProvider } from "next-themes";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="light"
      enableSystem={false}
      storageKey="polaris-theme"
      disableTransitionOnChange
    >
      {children}
    </ThemeProvider>
  );
}
