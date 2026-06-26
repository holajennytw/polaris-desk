"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export function usePeriods(): string[] {
  const { data } = useSWR("periods", () => api.periods(), {
    revalidateOnFocus: false,
  });
  return data ?? [];
}
