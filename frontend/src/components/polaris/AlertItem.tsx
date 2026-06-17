"use client";
import type { AlertVM } from "@/types/viewmodel";

interface AlertItemProps {
  alert: AlertVM;
  selected?: boolean;
  read?: boolean;
  onClick?: () => void;
  onDoubleClick?: () => void;
}

const LEVEL_LABEL: Record<string, string> = {
  high: "高", mid: "中", info: "低",
};

export function AlertItem({ alert, selected, read, onClick, onDoubleClick }: AlertItemProps) {
  return (
    <div
      className={
        "alert" +
        (selected ? " selected" : "") +
        (read ? " read" : "")
      }
      onClick={onClick}
      onDoubleClick={onDoubleClick}
    >
      <span className={"tag " + alert.level}>
        <span className="tdot" />
        {LEVEL_LABEL[alert.level] ?? alert.level}
      </span>
      <div className="alert-body">
        <div className="alert-title">{alert.title}</div>
        <div className="alert-sum">{alert.summary}</div>
        <div className="alert-meta font-mono">
          {alert.source} · {alert.time}
        </div>
      </div>
    </div>
  );
}
