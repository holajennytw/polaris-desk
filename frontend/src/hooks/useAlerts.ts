"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export function useAlerts() {
  return useSWR("alerts", () => api.alerts(), { refreshInterval: 30000 });
}
