"use client";
import { Icon } from "@/components/ui/Icon";

export type ViewMode = "table" | "chart";

interface ViewModeToggleProps {
  mode: ViewMode;
  onToggle: (mode: ViewMode) => void;
  disabled?: boolean;
}

export function ViewModeToggle({ mode, onToggle, disabled }: ViewModeToggleProps) {
  return (
    <div className="vm-toggle">
      <button
        className={"vm-btn" + (mode === "table" ? " active" : "")}
        onClick={() => onToggle("table")}
        title="表格檢視"
        aria-pressed={mode === "table"}
      >
        <Icon name="tableView" size={13}/>
        <span>表格</span>
      </button>
      <button
        className={"vm-btn" + (mode === "chart" ? " active" : "")}
        onClick={() => onToggle("chart")}
        disabled={disabled}
        title={disabled ? "資料不足，無法繪圖" : "圖表檢視"}
        aria-pressed={mode === "chart"}
      >
        <Icon name="barChart" size={13}/>
        <span>圖表</span>
      </button>
    </div>
  );
}
