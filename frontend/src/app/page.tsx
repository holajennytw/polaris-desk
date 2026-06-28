"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { SpotlightCard } from "@/components/ui/SpotlightCard";
import { useThemeToggle } from "@/hooks/useThemeToggle";

function NumberTicker({ target, suffix = "", decimals = 0, delay = 0, formatter }: {
  target: number; suffix?: string; decimals?: number; delay?: number;
  formatter?: (v: number) => string;
}) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      obs.disconnect();
      const t0 = performance.now() + delay;
      const duration = 1400;
      const tick = (now: number) => {
        if (now < t0) { requestAnimationFrame(tick); return; }
        const t = Math.min((now - t0) / duration, 1);
        const ease = 1 - Math.pow(1 - t, 3);
        setVal(ease * target);
        if (t < 1) requestAnimationFrame(tick); else setVal(target);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [target, delay]);
  const display = formatter ? formatter(val) : decimals > 0 ? val.toFixed(decimals) : String(Math.round(val));
  return <div ref={ref} className="lp-stat-v font-display">{display}{suffix}</div>;
}

const LP_MOB_NAV = [
  { href: "/",              label: "首頁", icon: "home"  as const },
  { href: "/research",      label: "研究", icon: "brain" as const },
  { href: "/peer",          label: "同業", icon: "scale" as const },
  { href: "/notifications", label: "通知", icon: "bell"  as const },
];

const LP_MORE_NAV = [
  { href: "/news",     label: "新聞",   icon: "news"     as const },
  { href: "/library",  label: "資料庫", icon: "database" as const },
  { href: "/history",  label: "對話紀錄", icon: "clock"  as const },
  { href: "/settings", label: "設定",   icon: "settings" as const },
];

const FEATURES = [
  { icon: "brain" as const, t: "研究助理", d: "輸入問題，小助手逐步規劃、檢索、計算與檢查，全程可視。" },
  { icon: "quote" as const, t: "可溯源引用", d: "每個數字、每句摘要均引用，點擊標籤即可查看。" },
  { icon: "scale" as const, t: "同業比較", d: "跨公司財務對比逐欄交叉驗證，拆解解釋各項數據差異。" },
  { icon: "alert" as const, t: "訊息通知", d: "公司有重大消息發布，即時通知使用者知悉。" },
  { icon: "shield" as const, t: "事實摘要", d: "所有 AI 輸出皆經檢查，標示「事實摘要，非投資建議」。" },
  { icon: "bell" as const, t: "訂閱追蹤", d: "訂閱感興趣的公司或主題，即時獲取最新資訊。" },
];

export default function LandingPage() {
  const { isDark, toggleTheme, btnRef: themeButtonRef } = useThemeToggle();
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  useEffect(() => { setMoreOpen(false); }, [pathname]);
  const moreActive = LP_MORE_NAV.some(it => pathname.startsWith(it.href));

  return (
    <div className="landing">
      <nav className="lp-nav">
        <div className="lp-brand">
          <div className="brand-star">
            <Icon name="star" size={22} fill="currentColor" sw={0} />
          </div>
          <div>
            <div className="brand-name font-display">Polaris Desk</div>
            <div className="brand-sub" style={{ color: "rgb(var(--muted))" }}>
              Equity Research
            </div>
          </div>
        </div>
        <div className="lp-nav-links">
          <Link href="/research">研究助理</Link>
          <Link href="/peer">同業比較</Link>
          <Link href="/news">新聞</Link>
          <Link href="/help">說明</Link>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button ref={themeButtonRef} className="icon-btn" onClick={toggleTheme} title="切換主題">
            <Icon name={isDark ? "sun" : "moon"} size={18} />
          </button>
          <Link href="/research" className="btn primary">
            開始使用 <Icon name="arrowRight" size={15} />
          </Link>
        </div>
      </nav>

      <header className="lp-hero">
        <div>
          <span className="lp-eyebrow">
            <span className="tdot" style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
            可溯源的 AI 股票研究工作台
          </span>
          <h1 className="lp-h1">
            把財報問題<br />
            變成<span className="accent">可驗證的答案</span>
          </h1>
          <p className="lp-sub">
            Polaris Desk 結合 AI 推理、引用與查詢，讓分析師在數秒內得到有來源、可稽核的研究結論。
          </p>
          <div className="lp-cta">
            <Link href="/research" className="btn primary xl">
              開始使用 <Icon name="arrowRight" size={17} />
            </Link>
            <Link href="/peer" className="btn xl">
              看同業比較
            </Link>
          </div>
          <div className="lp-stats">
            <div>
              <NumberTicker target={100} suffix="%" delay={0}/>
              <div className="lp-stat-l">引用可溯源率</div>
            </div>
            <div>
              <NumberTicker target={1.07} suffix="s" decimals={2} delay={200}/>
              <div className="lp-stat-l">平均回應時間</div>
            </div>
            <div>
              <NumberTicker target={3481} delay={400} formatter={v => Math.round(v).toLocaleString("zh-TW")}/>
              <div className="lp-stat-l">索引文件 chunks</div>
            </div>
          </div>
        </div>

        <div className="lp-visual">
          <div className="lp-card">
            <div className="lp-card-bar">
              <i /><i /><i />
              <span>polaris-desk / research</span>
            </div>
            <div className="lp-card-body">
              <div className="lp-mini-kpis">
                <div className="lp-mini-kpi">
                  <div className="k">毛利率</div>
                  <div className="v font-display">57.8%</div>
                  <div className="d">QoQ +0.8pp</div>
                </div>
                <div className="lp-mini-kpi">
                  <div className="k">營益率</div>
                  <div className="v font-display">47.5%</div>
                  <div className="d">QoQ +0.4pp</div>
                </div>
                <div className="lp-mini-kpi">
                  <div className="k">EPS</div>
                  <div className="v font-display">12.54</div>
                  <div className="d">YoY +54%</div>
                </div>
              </div>
              <div className="lp-mini-row">
                CoWoS 產能 Q4 預估翻倍<span className="cchip">法說 p.7</span>
              </div>
              <div className="lp-mini-row">
                毛利率 57.8%，季增 0.8pp<span className="cchip">財報 p.11</span>
              </div>
              <div className="lp-mini-row" style={{ color: "rgb(var(--success))", background: "rgb(var(--success) / .08)" }}>
                <Icon name="check" size={14} /> 合規檢查通過
              </div>
            </div>
          </div>
          <div className="lp-float">
            <div className="lf-ico"><Icon name="brain" size={16} /></div>
            <div>
              <div className="lf-t">推理完成</div>
              <div className="lf-s">4 steps · traced</div>
            </div>
          </div>
        </div>
      </header>

      <section className="lp-features">
        <div className="lp-sec-head">
          <h2 className="lp-sec-title">為機構研究而生的工作台</h2>
        </div>
        <div className="lp-feat-grid">
          {FEATURES.map((f, i) => (
            <SpotlightCard className="magic-card lp-feat" key={i}>
              <div className="lp-feat-ico"><Icon name={f.icon} size={22} /></div>
              <div className="lp-feat-t">{f.t}</div>
              <div className="lp-feat-d">{f.d}</div>
            </SpotlightCard>
          ))}
        </div>
      </section>

      <nav className="mobnav">
        {LP_MOB_NAV.map(it => (
          <Link key={it.href} href={it.href} className={"mobnav-item" + (pathname === it.href ? " active" : "")}>
            <span className="mobnav-ico"><Icon name={it.icon} size={20} /></span>
            <span>{it.label}</span>
          </Link>
        ))}
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
          {LP_MORE_NAV.map(it => (
            <Link
              key={it.href}
              href={it.href}
              className={"mob-more-item" + (pathname.startsWith(it.href) ? " active" : "")}
              onClick={() => setMoreOpen(false)}
            >
              <Icon name={it.icon} size={22} />
              <span>{it.label}</span>
            </Link>
          ))}
        </div>
      </div>

      <footer className="lp-foot">
        <div className="lp-brand">
          <div className="brand-star">
            <Icon name="star" size={22} fill="currentColor" sw={0} />
          </div>
          <div className="lp-foot-note">Polaris Desk · 前端參考原型 · 資料為 mock</div>
        </div>
        <Link href="/research" className="btn primary">
          開始使用 <Icon name="arrowRight" size={15} />
        </Link>
      </footer>
    </div>
  );
}
