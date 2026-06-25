// lib/config.ts — 全域環境設定
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
// 預設走同 origin 的 /api（由 next.config.ts 的 rewrite proxy 到 polaris-api）。
// 這樣 build-time 不需注入後端絕對網址；backend URL 改由 next.config 的
// BACKEND_API_URL runtime env 控制（見 next.config.ts）。
// 本機若要直連 localhost 後端，設 NEXT_PUBLIC_API_BASE=http://localhost:8000。
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
