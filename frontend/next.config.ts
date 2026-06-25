import type { NextConfig } from "next";

// polaris-api（後端 Cloud Run）base URL。
// rewrites() 在 server 啟動時（runtime）求值，因此可用 BACKEND_API_URL runtime env
// 逐次部署覆寫——不像 NEXT_PUBLIC_* 是 build-time baked-in。預設指向已知後端，
// 讓 frontend 不必重 build 也能切後端。
const BACKEND_API_URL =
  process.env.BACKEND_API_URL ??
  "https://polaris-api-14326813937.asia-east1.run.app";

const nextConfig: NextConfig = {
  output: "standalone",
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
