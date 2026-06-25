"use client";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useUnread } from "@/hooks/useUnread";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const unread = useUnread();
  return (
    <ErrorBoundary>
      <AppShell unread={unread}>{children}</AppShell>
    </ErrorBoundary>
  );
}
