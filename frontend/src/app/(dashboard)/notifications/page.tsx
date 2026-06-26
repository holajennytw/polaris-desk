"use client";
import { useState } from "react";
import { useSWRConfig } from "swr";
import { useSession } from "next-auth/react";
import { Icon } from "@/components/ui/Icon";
import { AlertItem } from "@/components/polaris/AlertItem";
import { useNotifications } from "@/hooks/useNotifications";
import { useAlerts } from "@/hooks/useAlerts";
import { useReadStore } from "@/hooks/useReadStore";
import { useCompanies } from "@/hooks/useCompanies";
import { useSubscriptions } from "@/hooks/useSubscriptions";
import { api } from "@/lib/api";
import { logError } from "@/lib/logger";

const TABS = ["feed","tracking","rules"] as const;
const TAB_LABELS: Record<string, string> = { feed:"訊息通知", tracking:"追蹤通知", rules:"訂閱設定" };

export default function NotificationsPage() {
  const { data: notifs } = useNotifications();
  const { data: alerts } = useAlerts();
  const rs = useReadStore();
  const allAlerts = alerts ?? [];
  const [tab, setTab] = useState<typeof TABS[number]>("feed");
  const { mutate } = useSWRConfig();
  const { data: session } = useSession();
  const companies = useCompanies();
  const { data: subs, isLoading: isSubsLoading } = useSubscriptions();
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const subscribedCompanies = companies.filter(c => (subs ?? []).includes(c.id));
  const filteredCompanies = companies.filter(c => {
    if ((subs ?? []).includes(c.id)) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return c.id.includes(q) || c.name.toLowerCase().includes(q);
  });

  const handleMarkNotifRead = async (id: string, alreadyRead: boolean) => {
    if (alreadyRead) return;
    await api.markNotificationRead(id);
    mutate("notifications");
  };

  const toggleSub = async (ticker: string) => {
    const current = subs ?? [];
    const next = current.includes(ticker)
      ? current.filter((t) => t !== ticker)
      : [...current, ticker];
    setSaveError(false);
    setIsSaving(true);
    try {
      await api.setSubscriptions(next);
      mutate("subscriptions");
    } catch (e) {
      logError("toggleSub", e);
      setSaveError(true);
    } finally {
      setIsSaving(false);
    }
  };

  const items = notifs?.items ?? [];
  const trackItems = items.filter(i=>i.type==="tracking");

  return (
    <div className="page-scroll">
      <div className="page narrow">
        <div className="page-head">
          <div className="page-eyebrow">通知 · notifications</div>
          <h1 className="page-title">通知中心</h1>
          <p className="page-desc">訊息通知、追蹤動態與訂閱設定。</p>
        </div>
        <div className="news-tabs">
          {TABS.map(t=>(
            <button key={t} className={"news-tab"+(t===tab?" active":"")} onClick={()=>setTab(t)}>{TAB_LABELS[t]}</button>
          ))}
        </div>
        {tab==="feed" && (
          <div className="panel" style={{marginTop:16}}>
            <div className="panel-head">
              <span className="panel-title"><Icon name="alert" size={15} style={{color:"rgb(var(--danger))",verticalAlign:"-2px",marginRight:6}}/>訊息通知</span>
              <span className="panel-meta">{allAlerts.length} 條</span>
            </div>
            <div className="alert-list">
              {allAlerts.map((a)=>(
                <AlertItem key={a.id} alert={a} read={rs.isRead(a.id)} onClick={()=>rs.markRead(a.id)}/>
              ))}
              {allAlerts.length===0 && (
                <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
                  <Icon name="shield" size={32} style={{marginBottom:10,opacity:0.3}}/>
                  <div style={{fontWeight:500,marginBottom:4}}>目前無風險警示</div>
                  <div style={{fontSize:13}}>執行研究或同業比較後，矛盾偵測與監控警示將顯示於此</div>
                </div>
              )}
            </div>
          </div>
        )}
        {tab==="tracking" && (
          <div className="panel" style={{marginTop:16}}>
            <div className="panel-head">
              <span className="panel-title"><Icon name="bell" size={15} style={{color:"rgb(var(--primary))",verticalAlign:"-2px",marginRight:6}}/>追蹤通知</span>
            </div>
            <div style={{padding:"12px 0"}}>
              {trackItems.length===0 ? (
                <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
                  <Icon name="bellOff" size={32} style={{marginBottom:10,opacity:0.3}}/>
                  <div style={{fontWeight:500,marginBottom:4}}>目前無追蹤通知</div>
                  <div style={{fontSize:13}}>在「訂閱設定」選擇追蹤公司後，最新動態將推送至此</div>
                </div>
              ) : trackItems.map(n=>(
                <div
                  key={n.id}
                  className={"alert"+(n.read?" read":"")}
                  style={{cursor: n.read ? "default" : "pointer"}}
                  onClick={() => handleMarkNotifRead(n.id, n.read)}
                >
                  <div className="alert-body">
                    <div className="alert-title">{n.title}</div>
                    <div className="alert-sum">{n.body}</div>
                    <div className="alert-meta font-mono">{n.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {tab==="rules" && (
          <div className="panel" style={{marginTop:16}}>
            <div className="panel-head">
              <span className="panel-title"><Icon name="target" size={15} style={{color:"rgb(var(--primary))",verticalAlign:"-2px",marginRight:6}}/>訂閱設定</span>
              {isSaving && <span className="panel-meta">儲存中…</span>}
              {saveError && <span className="panel-meta" style={{color:"rgb(var(--danger))"}}>儲存失敗，請稍後再試</span>}
            </div>
            {!session ? (
              <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
                <Icon name="user" size={32} style={{marginBottom:10,opacity:0.3}}/>
                <div style={{fontWeight:500,marginBottom:4}}>請先登入</div>
                <div style={{fontSize:13}}>登入後即可設定公司訂閱，接收法說會與財報更新通知</div>
              </div>
            ) : isSubsLoading ? (
              <div style={{padding:"24px 16px",color:"rgb(var(--muted))"}}>載入中…</div>
            ) : (
              <div style={{padding:"16px"}}>
                <p style={{fontSize:13,color:"rgb(var(--muted))",marginBottom:16}}>
                  搜尋公司後選取訂閱，接收法說會與財報更新通知。
                </p>
                {/* 搜尋框 + 下拉 */}
                <div style={{position:"relative",marginBottom:20}}>
                  <input
                    className="dock-input"
                    style={{width:"100%",boxSizing:"border-box"}}
                    value={searchQuery}
                    onChange={e => { setSearchQuery(e.target.value); setDropdownOpen(true); }}
                    onFocus={() => setDropdownOpen(true)}
                    onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
                    placeholder="輸入股票代號或公司名稱..."
                    disabled={isSaving}
                  />
                  {dropdownOpen && (
                    <div style={{
                      position:"absolute",top:"calc(100% + 4px)",left:0,right:0,
                      background:"rgb(var(--card))",
                      border:"1px solid rgb(var(--border))",
                      borderRadius:"var(--radius)",
                      boxShadow:"0 4px 16px rgb(0 0 0/.12)",
                      zIndex:200,maxHeight:220,overflowY:"auto",
                    }}>
                      {filteredCompanies.length > 0 ? filteredCompanies.map(c => (
                        <button
                          key={c.id}
                          onMouseDown={() => { toggleSub(c.id); setSearchQuery(""); setDropdownOpen(false); }}
                          style={{
                            display:"flex",alignItems:"center",gap:10,width:"100%",
                            padding:"10px 14px",background:"none",border:"none",
                            cursor:"pointer",textAlign:"left",color:"rgb(var(--foreground))",
                            borderBottom:"1px solid rgb(var(--border))",
                          }}
                          className="sub-dropdown-item"
                        >
                          <span className="font-mono" style={{fontSize:13,color:"rgb(var(--primary))",minWidth:36}}>{c.id}</span>
                          <span style={{fontSize:14}}>{c.name}</span>
                        </button>
                      )) : (
                        <div style={{padding:"16px 14px",fontSize:13,color:"rgb(var(--muted))"}}>
                          {searchQuery ? "找不到符合的公司" : "所有公司皆已訂閱"}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {/* 已訂閱清單 */}
                {subscribedCompanies.length > 0 ? (
                  <div>
                    <div style={{fontSize:12,fontWeight:600,color:"rgb(var(--muted))",marginBottom:8,letterSpacing:".04em"}}>已訂閱</div>
                    <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
                      {subscribedCompanies.map(c => (
                        <span key={c.id} style={{
                          display:"inline-flex",alignItems:"center",gap:6,
                          padding:"4px 10px",borderRadius:"var(--radius-lg,20px)",
                          background:"rgb(var(--primary)/.12)",
                          border:"1px solid rgb(var(--primary)/.25)",
                          fontSize:13,fontWeight:500,
                        }}>
                          <span className="font-mono" style={{color:"rgb(var(--primary))"}}>{c.id}</span>
                          <span>{c.name}</span>
                          <button
                            onClick={() => toggleSub(c.id)}
                            disabled={isSaving}
                            style={{
                              background:"none",border:"none",cursor:"pointer",
                              padding:0,lineHeight:1,color:"rgb(var(--muted))",
                              fontSize:15,marginLeft:2,
                            }}
                            title={`取消訂閱 ${c.name}`}
                          >×</button>
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{fontSize:13,color:"rgb(var(--muted))"}}>尚未訂閱任何公司</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}