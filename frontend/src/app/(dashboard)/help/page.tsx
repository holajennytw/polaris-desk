import { Icon } from "@/components/ui/Icon";

const SECTIONS = [
  {
    icon: "brain" as const,
    title: "研究助理",
    body: "在查詢列輸入問題，按送出後系統會逐步顯示推理過程（THINK / ACT / OBS），最後輸出可溯源的事實摘要。每個摘要皆可點擊查看原始文件。",
  },
  {
    icon: "scale" as const,
    title: "同業比較",
    body: "輸入欲比較的兩家公司，系統自動解析公司名稱、季別與比較維度，並顯示財務、法說、新聞、估值倍數等多維度對比。",
  },
  {
    icon: "shield" as const,
    title: "NFR-031 合規說明",
    body: "本系統所有 AI 輸出均為事實摘要，不構成任何投資建議。每個數字與結論皆可溯源至原始文件。合規橫幅出現在輸出頁面，確保使用者知悉。",
  },
  {
    icon: "database" as const,
    title: "資料庫管理",
    body: "在資料庫頁面可查看已有的文件清單，包括財報、法說會簡報、逐字稿與績效報告。系統自動於文件更新後觸發重新索引。",
  },
  {
    icon: "alert" as const,
    title: "風險監控",
    body: "監控系統在分析時擷取、法說會、新聞等相關資料公開資訊，進行合規初篩後推送警示。",
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