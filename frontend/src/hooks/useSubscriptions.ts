"use client";
import useSWR from "swr";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";

export function useSubscriptions() {
  const { data: session } = useSession();
  // 未登入不打 API（端點需 Bearer token）
  const key = session ? "subscriptions" : null;
  return useSWR(key, () => api.getSubscriptions(), { revalidateOnFocus: false });
}
