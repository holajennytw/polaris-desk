"use client";
import { Icon } from "@/components/ui/Icon";
import type { IconName } from "@/components/ui/Icon";
import type { AlertVM } from "@/types/viewmodel";

interface AlertItemProps {
  alert: AlertVM;
  selected?: boolean;
  read?: boolean;
  onClick?: () => void;
  onDoubleClick?: () => void;
}

const LEVEL_ICON: Record<string, IconName> = {
  high: "alert",
  mid: "alert",
  info: "bolt",
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
      <div className={`alert-ico ${alert.level}`}>
        <Icon name={LEVEL_ICON[alert.level] ?? "alert"} size={17} />
      </div>
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
