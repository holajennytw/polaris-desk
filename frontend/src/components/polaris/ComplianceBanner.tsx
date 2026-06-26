import { Icon } from "@/components/ui/Icon";

export function ComplianceBanner({ message }: { message?: string }) {
  return (
    <div className="compliance">
      <Icon name="shield" size={15} />
      <span>
        <span className="ctxt">
          {message ?? "以下為事實摘要，非投資建議。"}
        </span>
      </span>
    </div>
  );
}
