// lib/upstreamProxy.ts — 慢路徑（/research /ask：LLM 生成實測 20–40s）的後端代理。
//
// 為何不沿用 next.config.ts 的 rewrites()：rewrite 代理層約在 30s 砍上游連線，
// cold-start 的慢生成（實測 34s）會被截斷成 500 → 前端顯示「研究請求失敗」，
// 即使後端其實成功（見 2026-06-27 prod log：web /api/research 500@30.0s、
// 同時 backend /research 200@34.3s）。改用 App Router route handler（優先於
// rewrite），由本層自控上游 timeout。
import { NextResponse, type NextRequest } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ??
  "https://polaris-api-14326813937.asia-east1.run.app";

// 後端慢生成上限實測 ~34s；給 115s 餘裕（涵蓋 cold start + Vertex 尖峰），
// 仍 < Cloud Run 300s request timeout。
const UPSTREAM_TIMEOUT_MS = 115_000;

/** 把 POST 轉給後端 `path`，保留 Authorization 與 X-Forwarded-For。上游逾時/失聯回 504。 */
export async function proxyPost(req: NextRequest, path: string): Promise<NextResponse> {
  const body = await req.text();
  const headers: Record<string, string> = { "content-type": "application/json" };
  // 帶過登入身分（後端據此解析 viewer ACL）。
  const auth = req.headers.get("authorization");
  if (auth) headers["authorization"] = auth;
  // 帶過原始 client IP（web 的 GFE 已填）→ 後端限流仍能 per-user 計數，
  // 不會全部使用者共用 web egress 同一桶。
  const xff = req.headers.get("x-forwarded-for");
  if (xff) headers["x-forwarded-for"] = xff;

  try {
    const res = await fetch(`${BACKEND_API_URL}${path}`, {
      method: "POST",
      headers,
      body,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    return new NextResponse(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "後端回應逾時或無法連線，請稍後再試。" },
      { status: 504 },
    );
  }
}
