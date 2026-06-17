"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export function useNotifications() {
  return useSWR("notifications", () => api.notifications(), { refreshInterval: 60000 });
}
