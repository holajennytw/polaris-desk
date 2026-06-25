// lib/config.ts — 全域環境設定
// 預設走同 origin 的 /api（由 next.config.ts 的 rewrite proxy 到 polaris-api）。
// 本機若要直連 localhost 後端，設 NEXT_PUBLIC_API_BASE=http://localhost:8000。
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
