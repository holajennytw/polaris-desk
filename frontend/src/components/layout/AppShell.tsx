"use client";
// ============================================================
// components/layout/AppShell.tsx — 固定三區外框（rail / topbar / main）
//   忠實重建原型 app.jsx + shell.jsx 的「行為真相」：
//   • 路由      → next/navigation（usePathname + Link）取代原型 go()
//   • 主題切換  → next-themes（TopBar sun/moon），對應 data-theme + localStorage('polaris-theme')
//   • rail 收合 → useState + localStorage('polaris-rail')（'1'=收合），對應 .app.collapsed（232→68px）
//   • 未讀徽章  → unread prop（接 useUnread()：風險未讀 + 追蹤未讀，見 SDD §7.5）
//   • RWD      → class 全用 polaris.css；<1230px 自動 rail 隱藏 / mobnav 顯示（CSS 已寫）
//
//   用法：app/(dashboard)/layout.tsx → <AppShell unread={n}>{children}</AppShell>
//   注意：DocViewer（右側 slide-over）是跨頁 overlay，建議用 Context/parallel route 另置，不在此 shell。
// ============================================================
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Toaster } from "@/components/ui/sonner";

type NavItem = { href: string; label: string; icon: IconName; badge?: boolean };

const NAV_PRIMARY: NavItem[] = [
  { href: "/", label: "首頁", icon: "home" },
  { href: "/research", label: "研究助理", icon: "brain" },
  { href: "/peer", label: "同業比較", icon: "scale" },
  { href: "/news", label: "新聞", icon: "news" },
  { href: "/library", label: "資料庫", icon: "database" },
];
const NAV_SECONDARY: NavItem[] = [
  { href: "/history", label: "對話紀錄", icon: "clock" },
  { href: "/notifications", label: "通知", icon: "bell", badge: true },
  { href: "/help", label: "說明中心", icon: "help" },
];
const MOB_NAV: NavItem[] = [
  { href: "/", label: "首頁", icon: "home" },
  { href: "/peer", label: "同業", icon: "scale" },
  { href: "/research", label: "研究", icon: "brain" },
  { href: "/notifications", label: "通知", icon: "bell", badge: true },
  { href: "/settings", label: "設定", icon: "settings" },
];

const CRUMB: Record<string, string> = {
  "/research": "研究助理",
  "/peer": "同業比較",
  "/news": "新聞",
  "/library": "資料庫",
  "/notifications": "通知",
  "/history": "對話紀錄",
  "/help": "說明中心",
  "/settings": "帳號與設定",
};

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({
  children,
  unread = 0,
}: {
  children: React.ReactNode;
  /** 未讀徽章數：接 useUnread()（風險未讀 + 追蹤未讀）。0 不顯示。 */
  unread?: number;
}) {
  const pathname = usePathname() || "/";

  // ── rail 收合：localStorage('polaris-rail') 持久化（對應原型 app.jsx）──
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    setCollapsed(localStorage.getItem("polaris-rail") === "1");
  }, []);
  const toggleCollapse = () =>
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("polaris-rail", next ? "1" : "0");
      return next;
    });

  // ── 主題切換：next-themes（避免 hydration mismatch，mounted 後才顯示對的圖示）──
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";
  const toggleTheme = () => setTheme(isDark ? "light" : "dark");

  const renderNavItem = (it: NavItem) => {
    const active = isActive(pathname, it.href);
    const show = !!it.badge && unread > 0;
    return (
      <Link
        key={it.href}
        href={it.href}
        className={"nav-item" + (active ? " active" : "")}
        data-badge={show ? "1" : "0"}
      >
        <Icon name={it.icon} />
        <span>{it.label}</span>
        {show ? <span className="nav-badge">{unread > 99 ? "99+" : unread}</span> : null}
      </Link>
    );
  };

  return (
    <div className={"app" + (collapsed ? " collapsed" : "")}>
      {/* ── 左側墨色 rail ── */}
      <aside className="rail">
        <Link
          href="/"
          className="rail-brand"
          style={{ background: "none", border: "none", cursor: "pointer", width: "100%", textAlign: "left" }}
        >
          <div className="brand-star">
            <Icon name="star" size={17} fill="currentColor" sw={0} />
          </div>
          <div>
            <div className="brand-name">Polaris Desk</div>
            <div className="brand-sub">Equity Research</div>
          </div>
        </Link>
        <nav className="nav">
          {NAV_PRIMARY.map(renderNavItem)}
          {NAV_SECONDARY.map(renderNavItem)}
        </nav>
        <div className="side-foot">
          <Link
            href="/settings"
            className={"user-card" + (isActive(pathname, "/settings") ? " active" : "")}
          >
            <div className="avatar">JC</div>
            <div className="uc-info">
              <div className="user-name">Jing Chen</div>
              <div className="user-role">分析師 · R7</div>
            </div>
            <span className="uc-gear">
              <Icon name="settings" size={16} />
            </span>
          </Link>
        </div>
      </aside>

      {/* ── 頂部 TopBar ── */}
      <header className="topbar">
        <button
          className="icon-btn collapse-btn"
          onClick={toggleCollapse}
          title={collapsed ? "展開側邊欄" : "收合側邊欄"}
        >
          <Icon name="panelLeft" size={18} />
        </button>
        <div className="crumb">
          <span>Polaris</span>
          <Icon name="chevR" size={13} />
          <b>{CRUMB[pathname] ?? ""}</b>
        </div>
        <div className="topbar-right">
          <button className="icon-btn" onClick={toggleTheme} title="切換主題">
            <Icon name={isDark ? "sun" : "moon"} size={18} />
          </button>
        </div>
      </header>

      {/* ── 主區：捲動 + 內距由 .page 控制 ── */}
      <main className="main">{children}</main>

      <Toaster position="bottom-right" duration={2500} />

      {/* ── 手機底部導覽：<1230px 由 polaris.css 自動顯示（rail 同時隱藏）── */}
      <nav className="mobnav">
        {MOB_NAV.map((it) => {
          const active = isActive(pathname, it.href);
          const show = !!it.badge && unread > 0;
          return (
            <Link
              key={it.href}
              href={it.href}
              className={"mobnav-item" + (active ? " active" : "")}
            >
              <span className="mobnav-ico">
                <Icon name={it.icon} size={20} />
                {show ? <span className="mobnav-badge">{unread > 99 ? "99+" : unread}</span> : null}
              </span>
              <span>{it.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
