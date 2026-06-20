// ============================================================
// app/fonts.ts — next/font 載入拉丁字型，輸出 CSS 變數
// 對應 globals.css §5 的 --font-dm-sans / --font-syne / --font-jetbrains-mono
// 註：Noto Sans TC（CJK）不走 next/font（子集不穩、檔案大），改在 layout.tsx 以 <link> 載入。
// ============================================================
import { DM_Sans, Syne, JetBrains_Mono } from "next/font/google";

export const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const syne = Syne({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-syne",
  display: "swap",
});

export const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const fontVars = `${dmSans.variable} ${syne.variable} ${jetbrainsMono.variable}`;
