import { Icon } from "@/components/ui/Icon";

const SECTIONS = [
  {
    icon: "brain" as const,
    title: "研究助理",
    body: "在查詢列輸入問題，按送出後系統會逐步顯示推理過程，最後輸出可溯源的事實摘要。每個摘要皆可點擊查看原始文件。",
  },
  {
    icon: "scale" as const,
    title: "同業比較",
    body: "輸入欲比較的兩家公司，系統自動解析公司名稱、季別與比較維度，並顯示財務、法說、新聞、估值倍數等多維度對比。",
  },
  {
    icon: "shield" as const,
    title: "事實摘要",
    body: "本系統所有 AI 輸出均為事實摘要，不構成任何投資建議。每個數字與結論均可溯源至原始文件，確保使用者知悉。",
  },
  {
    icon: "alert" as const,
    title: "通知中心",
    body: "訂閱追蹤的公司或主題有重大消息發布時，系統會即時通知使用者。",
  },
];

export default function HelpPage() {
  return (
    <div className="page-scroll">
      <div className="page">
        <div className="page-head">
          <div className="page-eyebrow">說明中心 · help</div>
          <h1 className="page-title">說明中心</h1>
          <p className="page-desc">了解 Polaris Desk 各功能的使用方式。</p>
        </div>
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          {SECTIONS.map((s,i)=>(
            <div key={i} className="panel">
              <div className="panel-head">
                <span className="panel-title">
                  <Icon name={s.icon} size={16} style={{color:"rgb(var(--primary))",verticalAlign:"-3px",marginRight:8}}/>
                  {s.title}
                </span>
              </div>
              <div className="panel-body" style={{color:"rgb(var(--foreground))",lineHeight:1.7}}>
                {s.body}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}