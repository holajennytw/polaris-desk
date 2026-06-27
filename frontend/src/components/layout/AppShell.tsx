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
import { useSession } from "next-auth/react";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Toaster } from "@/components/ui/sonner";
import { OnboardingModal } from "@/components/polaris/OnboardingModal";
import { useThemeToggle } from "@/hooks/useThemeToggle";

type NavItem = { href: string; label: string; icon: IconName; badge?: boolean };

const NAV_PRIMARY: NavItem[] = [
  { href: "/", label: "首頁", icon: "home" },
  { href: "/research", label: "研究助理", icon: "brain" },
  { href: "/peer", label: "同業比較", icon: "scale" },
  { href: "/news", label: "新聞", icon: "news" },
];
const NAV_SECONDARY: NavItem[] = [
  { href: "/history", label: "對話紀錄", icon: "clock" },
  { href: "/notifications", label: "通知", icon: "bell", badge: true },
  { href: "/help", label: "說明中心", icon: "help" },
];
const MOB_NAV: NavItem[] = [
  { href: "/", label: "首頁", icon: "home" },
  { href: "/research", label: "研究", icon: "brain" },
  { href: "/peer", label: "同業", icon: "scale" },
  { href: "/notifications", label: "通知", icon: "bell", badge: true },
];

const MOB_MORE: NavItem[] = [
  { href: "/news", label: "新聞", icon: "news" },
  { href: "/history", label: "對話紀錄", icon: "clock" },
  { href: "/settings", label: "設定", icon: "settings" },
];

const CRUMB: Record<string, string> = {
  "/research": "研究助理",
  "/peer": "同業比較",
  "/news": "新聞",
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
  const { data: session } = useSession();
  const userName = session?.user?.name ?? "訪客";
  const userImage = session?.user?.image;
  const initials = userName.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase() || "?";

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

  // ── 主題切換（View Transition + 星星粒子，抽至 useThemeToggle）──
  const { isDark, toggleTheme, btnRef: themeButtonRef } = useThemeToggle();

  // ── 更多 sheet ──
  const [moreOpen, setMoreOpen] = useState(false);
  useEffect(() => { setMoreOpen(false); }, [pathname]);
  const moreActive = MOB_MORE.some(it => isActive(pathname, it.href));

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
            <Icon name="star" size={22} fill="currentColor" sw={0} />
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
            {userImage
              ? <img src={userImage} alt={userName} style={{ width: 32, height: 32, borderRadius: "50%" }} />
              : <div className="avatar">{initials}</div>
            }
            <div className="uc-info">
              <div className="user-name">{userName}</div>
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
          aria-label={collapsed ? "展開側邊欄" : "收合側邊欄"}
        >
          <Icon name="panelLeft" size={18} />
        </button>
        <div className="crumb">
          <span className="crumb-brand">Polaris</span>
          <Icon name="chevR" size={13} className="crumb-brand" />
          <b>{CRUMB[pathname] ?? ""}</b>
        </div>
        <div className="topbar-right">
          <button ref={themeButtonRef} className="icon-btn" onClick={toggleTheme} title="切換主題" aria-label={isDark ? "切換為淺色模式" : "切換為深色模式"}>
            <Icon name={isDark ? "sun" : "moon"} size={18} />
          </button>
        </div>
      </header>

      {/* ── 主區：捲動 + 內距由 .page 控制 ── */}
      <main className="main">{children}</main>

      <Toaster position="bottom-right" duration={2500} />
      <OnboardingModal />

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
        <button
          className={"mobnav-item" + (moreActive || moreOpen ? " active" : "")}
          onClick={() => setMoreOpen(o => !o)}
        >
          <span className="mobnav-ico"><Icon name="layers" size={20} /></span>
          <span>更多</span>
        </button>
      </nav>
      <div className={"mob-more-overlay" + (moreOpen ? " open" : "")} onClick={() => setMoreOpen(false)} />
      <div className={"mob-more-sheet" + (moreOpen ? " open" : "")}>
        <div className="mob-more-handle" />
        <div className="mob-more-grid">
          {MOB_MORE.map(it => (
            <Link
              key={it.href}
              href={it.href}
              className={"mob-more-item" + (isActive(pathname, it.href) ? " active" : "")}
              onClick={() => setMoreOpen(false)}
            >
              <Icon name={it.icon} size={22} />
              <span>{it.label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
