"use client";
import { Component, type ReactNode } from "react";
import { logError } from "@/lib/logger";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : "未知錯誤";
    return { hasError: true, message };
  }

  componentDidCatch(error: unknown): void {
    logError("ErrorBoundary", error);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;
    return (
      <div className="chart-empty" style={{ padding: "48px 24px" }}>
        <span style={{ fontSize: "1.5rem", marginBottom: 12 }}>⚠</span>
        <span>頁面發生錯誤，請重新整理</span>
        <span
          className="font-mono"
          style={{ fontSize: "0.72rem", color: "rgb(var(--muted))", marginTop: 4 }}
        >
          {this.state.message}
        </span>
        <button
          className="btn ghost"
          style={{ marginTop: 16 }}
          onClick={() => this.setState({ hasError: false, message: "" })}
        >
          重試
        </button>
      </div>
    );
  }
}
