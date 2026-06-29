"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { PeriodInfo } from "@/types/api";

export function usePeriods(): PeriodInfo[] {
  const { data } = useSWR("periods", () => api.periods(), {
    revalidateOnFocus: false,
  });
  return data ?? [];
}
