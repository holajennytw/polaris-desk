"use client";
import { Icon } from "@/components/ui/Icon";
import type { KpiVM } from "@/types/viewmodel";

interface KpiCardProps {
  k: KpiVM;
  onCite?: (cite: string) => void;
}

export function KpiCard({ k, onCite }: KpiCardProps) {
  return (
    <button
      className="magic-card kpi"
      onClick={() => onCite?.(k.cite)}
    >
      <div className="kpi-label">{k.label}</div>
      <div className="kpi-value font-display">
        {k.value}
        <span className="kpi-unit">{k.unit}</span>
      </div>
      <div className={"kpi-delta " + k.trend}>
        <Icon name={k.trend === "up" ? "arrowUp" : "arrowDown"} size={13} />
        {k.delta}
      </div>
    </button>
  );
}
