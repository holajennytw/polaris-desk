"use client";
import { Icon } from "@/components/ui/Icon";
import type { CitationTrackerVM } from "@/types/viewmodel";

interface CitationListProps {
  citations: CitationTrackerVM[];
  onOpen?: (cite: string) => void;
}

export function CitationList({ citations, onOpen }: CitationListProps) {
  return (
    <div className="cite-list">
      {citations.map((c) => (
        <button
          key={c.ix}
          className="cite-item"
          onClick={() => onOpen?.(c.cite)}
        >
          <span className="cite-ix font-mono">{c.ix}</span>
          <div className="cite-body">
            <div className="cite-label">{c.label}</div>
            <div className="cite-detail font-mono">{c.detail}</div>
          </div>
          <Icon name="chevR" size={15} style={{ color: "rgb(var(--muted))" }} />
        </button>
      ))}
    </div>
  );
}
