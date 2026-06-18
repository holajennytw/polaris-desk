"use client";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { AlertItem } from "@/components/polaris/AlertItem";
import { useNotifications } from "@/hooks/useNotifications";
import { useAlerts } from "@/hooks/useAlerts";
import { useContraAlerts } from "@/hooks/useContraAlerts";
import { useReadStore } from "@/hooks/useReadStore";

const TABS = ["feed","tracking","rules"] as const;
const TAB_LABELS: Record<string, string> = { feed:"風險動態", tracking:"追蹤通知", rules:"訂閱設定" };

export default function NotificationsPage() {
  const { data: notifs } = useNotifications();
  const { data: alerts } = useAlerts();
  const contraAlerts = useContraAlerts();
  const rs = useReadStore();
  const allAlerts = [...(alerts ?? []), ...contraAlerts];
  const [tab, setTab] = useState<typeof TABS[number]>("feed");

  const items = notifs?.items ?? [];
  const trackItems = items.filter(i=>i.type==="tracking");

  return (
    <div className="page-scroll">
      <div className="page narrow">
        <div className="page-head">
          <div className="page-eyebrow">通知 · /notifications</div>
          <h1 className="page-title">通知中心</h1>
          <p className="page-desc">風險監控、追蹤動態與訂閱設定。</p>
        </div>
        <div className="news-tabs">
          {TABS.map(t=>(
            <button key={t} className={"news-tab"+(t===tab?" active":"")} onClick={()=>setTab(t)}>{TAB_LABELS[t]}</button>
          ))}
        </div>
        {tab==="feed" && (
          <div className="panel" style={{marginTop:16}}>
            <div className="panel-head">
              <span className="panel-title"><Icon name="alert" size={15} style={{color:"rgb(var(--danger))",verticalAlign:"-2px",marginRight:6}}/>風險監控警示</span>
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
                <div key={n.id} className={"alert"+(n.read?" read":"")}>
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
            </div>
            <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
              <Icon name="target" size={32} style={{marginBottom:10,opacity:0.3}}/>
              <div style={{fontWeight:500,marginBottom:4}}>訂閱設定</div>
              <div style={{fontSize:13}}>選擇欲追蹤的公司，系統將自動推送法說會與財報更新通知</div>
              <div style={{fontSize:12,marginTop:8,opacity:0.6}}>功能開發中，敬請期待</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}