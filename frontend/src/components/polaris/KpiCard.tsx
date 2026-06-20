"use client";
import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { SpotlightButton } from "@/components/ui/SpotlightCard";
import type { KpiVM } from "@/types/viewmodel";

function AnimatedNumber({ raw }: { raw: string }) {
  const num = parseFloat(raw);
  const isNum = !isNaN(num);
  const dec = isNum && raw.includes(".") ? raw.length - raw.indexOf(".") - 1 : 0;
  const [v, setV] = useState(0);

  useEffect(() => {
    if (!isNum) return;
    const start = performance.now();
    const dur = 900;
    const tick = (now: number) => {
      const t = Math.min((now - start) / dur, 1);
      setV((1 - Math.pow(1 - t, 3)) * num);
      if (t < 1) requestAnimationFrame(tick);
      else setV(num);
    };
    requestAnimationFrame(tick);
  }, [raw]);

  if (!isNum) return <>{raw}</>;
  return <>{v.toFixed(dec)}</>;
}

interface KpiCardProps {
  k: KpiVM;
  onCite?: (cite: string) => void;
}

export function KpiCard({ k, onCite }: KpiCardProps) {
  const hasValue = k.value !== "" && k.value != null;
  const hasDelta = k.delta !== "" && k.delta != null;
  return (
    <SpotlightButton className="magic-card kpi" onClick={() => onCite?.(k.cite)}>
      <div className="kpi-label">{k.label}</div>
      <div className="kpi-value font-display">
        {hasValue
          ? <><AnimatedNumber raw={String(k.value)} />{k.unit && <span className="kpi-unit">{k.unit}</span>}</>
          : <span className="kpi-unknown">不知道</span>
        }
      </div>
      {hasDelta && (
        <div className={"kpi-delta " + k.trend}>
          <Icon name={k.trend === "up" ? "arrowUp" : "arrowDown"} size={13} />
          {k.delta}
        </div>
      )}
    </SpotlightButton>
  );
}
