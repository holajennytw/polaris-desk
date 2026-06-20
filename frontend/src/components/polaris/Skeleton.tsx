// 通用 shimmer skeleton
interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = "", style }: SkeletonProps) {
  return <div className={"sk " + className} style={style} />;
}

export function KpiSkeleton() {
  return (
    <div className="kpi-grid">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="kpi" style={{ padding: 16 }}>
          <Skeleton style={{ height: 14, width: "60%", marginBottom: 8 }} />
          <Skeleton style={{ height: 28, width: "80%", marginBottom: 8 }} />
          <Skeleton style={{ height: 14, width: "40%" }} />
        </div>
      ))}
    </div>
  );
}

export function PanelSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ padding: "16px 0" }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} style={{ height: 18, marginBottom: 10, width: `${60 + (i % 3) * 15}%` }} />
      ))}
    </div>
  );
}
