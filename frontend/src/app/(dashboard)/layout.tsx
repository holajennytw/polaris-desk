"use client";
import { AppShell } from "@/components/layout/AppShell";
import { useUnread } from "@/hooks/useUnread";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const unread = useUnread();
  return <AppShell unread={unread}>{children}</AppShell>;
}
