// /api/research — 取代 next.config rewrite，自控上游 timeout（見 lib/upstreamProxy）。
import type { NextRequest } from "next/server";
import { proxyPost } from "@/lib/upstreamProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

export function POST(req: NextRequest) {
  return proxyPost(req, "/research");
}
