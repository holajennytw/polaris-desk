// ============================================================
// components/ui/Icon.tsx — 原型 icons.jsx 的 TypeScript 移植
//   描邊線性圖示（Lucide 風）。用法：<Icon name="brain" size={18} />
//   名稱與原型一對一；若改用 lucide-react，名稱也幾乎可直接對映（見 SDD §3.6）。
// ============================================================
import * as React from "react";

export type IconName =
  | "home" | "brain" | "scale" | "news" | "database" | "clock" | "bell"
  | "help" | "search" | "star" | "bolt" | "spark" | "arrowUp" | "arrowDown"
  | "check" | "shield" | "file" | "x" | "chevR" | "target" | "layers"
  | "download" | "refresh" | "alert" | "quote" | "gear" | "logout" | "mail"
  | "user" | "panelLeft" | "sun" | "moon" | "arrowRight" | "send" | "chevD"
  | "paperclip" | "hourglass" | "bellOff" | "mic" | "settings";

const P: Record<IconName, React.ReactNode> = {
  home: <path d="M3 11l9-8 9 8M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />,
  brain: <g><path d="M9.5 3.5A2.5 2.5 0 0 0 7 6c-1.4.2-2.5 1.4-2.5 2.9 0 .6.2 1.2.5 1.6-.6.5-1 1.3-1 2.2 0 1.1.6 2 1.5 2.5 0 1.6 1.3 2.8 2.9 2.8.5.8 1.4 1.3 2.4 1.3" /><path d="M14.5 3.5A2.5 2.5 0 0 1 17 6c1.4.2 2.5 1.4 2.5 2.9 0 .6-.2 1.2-.5 1.6.6.5 1 1.3 1 2.2 0 1.1-.6 2-1.5 2.5 0 1.6-1.3 2.8-2.9 2.8-.5.8-1.4 1.3-2.4 1.3" /><path d="M12 4v16" /></g>,
  scale: <g><path d="M12 3v18M7 21h10M5 7l3-3 3 3M5 7l-2.5 5a2.5 2.5 0 0 0 5 0L5 7zM19 7l-3-3-3 3M19 7l-2.5 5a2.5 2.5 0 0 0 5 0L19 7zM4.5 4.5h15" /></g>,
  news: <g><path d="M4 5h13a1 1 0 0 1 1 1v12a1 1 0 0 0 1 1 1 1 0 0 0 1-1V8" /><path d="M4 5a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h15" /><path d="M7 9h7M7 12.5h7M7 16h4" /></g>,
  database: <g><ellipse cx="12" cy="5.5" rx="7" ry="2.8" /><path d="M5 5.5v13c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-13M5 12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8" /></g>,
  clock: <g><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></g>,
  bell: <path d="M18 9a6 6 0 1 0-12 0c0 6-2.5 7.5-2.5 7.5h17S18 15 18 9zM10.5 20a2 2 0 0 0 3 0" />,
  help: <g><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 0 1 4.5 1.4c0 1.6-2.5 2-2.5 3.6M12 17.5h.01" /></g>,
  search: <g><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></g>,
  star: <path d="M12 2.5l2.9 6.2 6.6.8-4.9 4.5 1.3 6.5L12 17.6 6.1 21l1.3-6.5L2.5 9.5l6.6-.8z" />,
  bolt: <path d="M13 2 4.5 13.5H11l-1 8.5L19.5 10H13z" />,
  spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />,
  arrowUp: <path d="M12 19V5M6 11l6-6 6 6" />,
  arrowDown: <path d="M12 5v14M6 13l6 6 6-6" />,
  check: <path d="M20 6 9 17l-5-5" />,
  shield: <g><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="m9 12 2 2 4-4" /></g>,
  file: <g><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 16.5h6" /></g>,
  x: <path d="M18 6 6 18M6 6l12 12" />,
  chevR: <path d="m9 6 6 6-6 6" />,
  target: <g><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r=".6" fill="currentColor" /></g>,
  layers: <path d="M12 3 3 8l9 5 9-5-9-5zM4 12.5 12 17l8-4.5M4 16.5 12 21l8-4.5" />,
  download: <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" />,
  refresh: <path d="M3.5 9a8.5 8.5 0 0 1 14.5-3l2 2M20.5 15A8.5 8.5 0 0 1 6 18l-2-2M19 4v4h-4M5 20v-4h4" />,
  alert: <path d="M12 3 2.5 19.5h19L12 3zM12 10v4M12 17.5h.01" />,
  quote: <path d="M7 7h4v6a4 4 0 0 1-4 4M13 7h4v6a4 4 0 0 1-4 4" />,
  gear: <g><circle cx="12" cy="12" r="3.2" /><path d="M19.4 13a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></g>,
  logout: <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />,
  mail: <g><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></g>,
  user: <g><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></g>,
  panelLeft: <g><rect x="3" y="4" width="18" height="16" rx="2.2" /><path d="M9 4v16" /></g>,
  sun: <g><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19" /></g>,
  moon: <path d="M20 13.5A8 8 0 1 1 10.5 4a6.2 6.2 0 0 0 9.5 9.5z" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  send: <g><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4z" /></g>,
  chevD: <path d="m6 9 6 6 6-6" />,
  paperclip: <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />,
  hourglass: <g><path d="M6 3h12M6 21h12M7 3c0 4 4 5.5 5 9 1-3.5 5-5 5-9M7 21c0-4 4-5.5 5-9 1 3.5 5 5 5 9" /></g>,
  bellOff: <g><path d="M9.5 4.2A6 6 0 0 1 18 9c0 2.3.4 4 .9 5.2M6 9c0 6-2.5 7.5-2.5 7.5h12.5M10.5 20a2 2 0 0 0 3 0" /><path d="M3 3l18 18" /></g>,
  mic: <g><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><path d="M12 19v3" /></g>,
  settings: <g><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></g>,
};

export interface IconProps {
  name: IconName;
  size?: number;
  fill?: string;
  /** stroke width — 原型參數名為 sw */
  sw?: number;
  style?: React.CSSProperties;
  className?: string;
}

export function Icon({ name, size = 18, fill = "none", sw = 1.9, style, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill}
      stroke="currentColor"
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
      aria-hidden="true"
    >
      {P[name] ?? null}
    </svg>
  );
}

export default Icon;
