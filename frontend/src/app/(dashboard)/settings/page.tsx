"use client";
import { useTheme } from "next-themes";
import { signIn, signOut, useSession } from "next-auth/react";
import { Icon } from "@/components/ui/Icon";
import { USE_MOCK } from "@/lib/config";

function GoogleMark() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.56c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.56-2.76c-.98.66-2.23 1.06-3.72 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
    </svg>
  );
}

export default function SettingsPage() {
  const { resolvedTheme, setTheme } = useTheme();
  const { data: session } = useSession();
  const isDark = resolvedTheme === "dark";

  const name = session?.user?.name ?? "訪客";
  const email = session?.user?.email ?? "";
  const initials = name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="page-scroll">
      <div className="page settings-page">
        <div className="page-head">
          <div className="page-eyebrow">帳號 · /settings</div>
          <h1 className="page-title">帳號與設定</h1>
          <p className="page-desc">管理登入方式、外觀主題與資料來源偏好。</p>
        </div>
        <div className="set-body">
          <div className="set-account">
            {session?.user?.image
              ? <img src={session.user.image} alt={name} style={{width:44,height:44,borderRadius:"50%"}} />
              : <div className="avatar" style={{width:44,height:44,fontSize:20}}>{initials}</div>
            }
            <div style={{flex:1}}>
              <div className="user-name" style={{fontSize:19,color:"rgb(var(--foreground))"}}>{name}</div>
              {email && <div className="set-mail font-mono">{email}</div>}
            </div>
            <span className={`tag ${session ? "ok" : "muted"}`}>
              <span className="tdot"/>{session ? "已登入" : "未登入"}
            </span>
          </div>
          <div className="set-label">以郵箱第三方登入 / 綁定</div>
          <div className="set-sso">
            {session
              ? <button className="sso-btn" onClick={() => signOut()}><GoogleMark/><span>登出 Google 帳號</span></button>
              : <button className="sso-btn" onClick={() => signIn("google")}><GoogleMark/><span>使用 Google 帳號繼續</span></button>
            }
          </div>
          <div className="set-label" style={{marginTop:22}}>偏好設定</div>
          <div className="set-pref">
            <div className="pref-row">
              <div><div className="pref-t">外觀主題</div><div className="pref-d">淺色 / 深色終端</div></div>
              <button className="btn sm" onClick={()=>setTheme(isDark?"light":"dark")}><Icon name={isDark?"sun":"moon"} size={14}/>{isDark?"淺色":"深色"}</button>
            </div>
            <div className="pref-row">
              <div><div className="pref-t">資料來源</div><div className="pref-d">mock JSON ↔ 真實 API</div></div>
              <span className="tag muted font-mono">USE_MOCK={USE_MOCK?"true":"false"}</span>
            </div>
          </div>
          {session && <button className="set-logout" onClick={() => signOut()}><Icon name="logout" size={16}/>登出帳號</button>}
        </div>
      </div>
    </div>
  );
}