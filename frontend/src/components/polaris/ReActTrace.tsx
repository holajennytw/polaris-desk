"use client";
import type { ReActStepVM } from "@/types/viewmodel";

interface ReActTraceProps {
  steps: ReActStepVM[];
  activeIndex?: number;
  visibleCount?: number;
}

export function ReActTrace({ steps, activeIndex, visibleCount }: ReActTraceProps) {
  const visible = visibleCount !== undefined ? steps.slice(0, visibleCount) : steps;

  return (
    <div className="react-list">
      {visible.map((s, i) => (
        <div
          key={i}
          className={
            "react-step " +
            s.type +
            (activeIndex === i ? " active" : "")
          }
        >
          <div className="rs-bar" />
          <div className="rs-body">
            <span className="rs-type">{s.type}</span>
            {s.tool ? (
              <code className="rs-code">{s.text}</code>
            ) : (
              <span className="rs-text">{s.text}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
