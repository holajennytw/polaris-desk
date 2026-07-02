import type { NextConfig } from "next";

// polaris-api（後端 Cloud Run）base URL。
// rewrites() 在 server 啟動時（runtime）求值，因此可用 BACKEND_API_URL runtime env
// 逐次部署覆寫——不像 NEXT_PUBLIC_* 是 build-time baked-in。預設指向已知後端，
// 讓 frontend 不必重 build 也能切後端。
const BACKEND_API_URL =
  process.env.BACKEND_API_URL ??
  "https://polaris-api-14326813937.asia-east1.run.app";

// 安全性標頭：CSP 作為 XSS 的瀏覽器層防線（後備），並鎖定 clickjacking /
// MIME sniffing / base-uri 竄改。script/style 仍需 'unsafe-inline'（Next.js 水合
// 內嵌腳本 + 大量 inline style），但 object-src/base-uri/frame-ancestors 已收緊。
const SECURITY_HEADERS = [
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: blob:",
      "connect-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'",
      "upgrade-insecure-requests",
    ].join("; "),
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  // 前端以同 origin 的 /api/* 呼叫，由本 rewrite proxy 到後端：
  //   /api/companies              -> {BACKEND}/companies
  //   /api/financials?ticker=2330 -> {BACKEND}/financials?ticker=2330（query 自動帶過去）
  //   /api/peer-compare           -> {BACKEND}/peer-compare
  //   /api/research               -> {BACKEND}/research
  //
  // negative lookahead 排除 /api/auth*：那是 NextAuth 的 filesystem route
  // (src/app/api/auth/[...nextauth]/route.ts)，必須留在前端 origin、不可 proxy 到後端。
  async rewrites() {
    return [
      {
        source: "/api/:path((?!auth).*)",
        destination: `${BACKEND_API_URL}/:path`,
      },
    ];
  },
};

export default nextConfig;
