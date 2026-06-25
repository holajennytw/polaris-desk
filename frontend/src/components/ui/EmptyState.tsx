import { Icon, type IconName } from "@/components/ui/Icon";

interface EmptyStateProps {
  icon?: IconName;
  message: string;
  sub?: string;
  style?: React.CSSProperties;
}

export function EmptyState({ icon = "layers", message, sub, style }: EmptyStateProps) {
  return (
    <div className="chart-empty" style={style}>
      <Icon name={icon} size={20} style={{ color: "rgb(var(--muted))", marginBottom: 8 }} />
      <span>{message}</span>
      {sub && (
        <span className="font-mono" style={{ fontSize: "0.72rem", color: "rgb(var(--muted))" }}>
          {sub}
        </span>
      )}
    </div>
  );
}
