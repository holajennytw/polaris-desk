"use client";
import { useNotifications } from "./useNotifications";

export function useUnread(): number {
  const { data } = useNotifications();
  return data?.unread ?? 0;
}
