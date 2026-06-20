// lib/config.ts — 全域環境設定
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
