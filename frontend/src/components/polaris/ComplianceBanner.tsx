// NFR-031 合規橫幅 — 每個有 AI 輸出的頁面都要有
import { Icon } from "@/components/ui/Icon";

export function ComplianceBanner({ message }: { message?: string }) {
  return (
    <div className="compliance">
      <Icon name="shield" size={15} />
      <span>
        <b>NFR-031</b>{" "}
        <span className="ctxt">
          {message ?? "以下為事實摘要，非投資建議。"}
        </span>
      </span>
    </div>
  );
}
