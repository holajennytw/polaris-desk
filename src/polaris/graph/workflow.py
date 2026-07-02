"""LangGraph 5-node skeleton — wiring only (W1 D1 US1, R2).

工作流：Planner → Retriever → Calculator → Writer → Compliance → END
+ 跨節點 halt 條件邊：任一節點掛掉或回 halt=True，直接跳到 terminal 節點
  產出固定錯誤訊息，下游節點不再執行（spec SC-007 / FR-008 / FR-009）。

**本檔只負責 wiring**：節點實作在 :mod:`polaris.graph.nodes.stubs`；換真 agent
時只動 stubs.py，本檔的 add_node / add_edge 結構不必改（FR-007 / SC-005）。

langgraph 採延遲 import，未安裝時 `import polaris` 仍正常。
"""
from __future__ import annotations

from typing import Any

from polaris.graph.nodes import stubs
from polaris.graph.nodes.visual_reader import visual_reader
from polaris.graph.state import ResearchState


# ---------------------------------------------------------------------------
# Halt routing
# ---------------------------------------------------------------------------

def _route(state: dict[str, Any]) -> str:
    """節點執行完後的條件邊：halt=True → 跳 terminal；否則繼續下一個節點。"""
    return "terminal" if state.get("halt") else "continue"


#: L3「查無足夠來源」對外固定訊息（input_gate flag 開時，calculator 後 contexts 仍空 → 短路）。
NO_EVIDENCE_MESSAGE = (
    "查無足夠的可靠來源可回答此問題。可能是尚未收錄相關公司 / 期別的資料，"
    "請調整問題範圍或改問其他已收錄的標的。"
)


def _route_evidence(state: dict[str, Any]) -> str:
    """calculator 後的條件邊（僅 INPUT_GATE 開時掛上）。

    halt → terminal；retriever + calculator 都沒補進任何 context → no_evidence（不讓
    writer 從空脈絡生成、避免幻覺）；否則正常續接 writer。
    """
    if state.get("halt"):
        return "terminal"
    if not state.get("contexts"):
        return "no_evidence"
    return "continue"


def _no_evidence(state: dict[str, Any]) -> dict[str, Any]:
    """查無足夠來源的收尾節點：回固定訊息、無引用、compliance_status=unknown。"""
    return {
        "answer": NO_EVIDENCE_MESSAGE,
        "compliance_status": "unknown",
        "citations": [],
    }


def _terminal(state: dict[str, Any]) -> dict[str, Any]:
    """Halt 路徑的收尾節點：產出固定錯誤訊息、標 compliance_status=unknown。

    不被 @traced 包，刻意不出現在 trace 中（infrastructure node）。
    錯誤訊息會看最後一筆 trace 的 node_name 與 error_message 來決定：
    - 空 query（planner 報 "empty query"）→ "請提供具體問題。"
    - 其他節點例外 → "處理過程發生錯誤（節點：<name>），請查看 trace 細節。"
    """
    msg = "處理過程發生錯誤，請查看 trace 細節。"
    trace = state.get("trace") or []
    if trace:
        last = trace[-1]
        if getattr(last, "status", None) == "error":
            err = (getattr(last, "error_message", "") or "").lower()
            if "empty query" in err:
                msg = "請提供具體問題。"
            else:
                msg = (
                    f"處理過程發生錯誤（節點：{last.node_name}），"
                    "請查看 trace 細節。"
                )
    return {"answer": msg, "compliance_status": "unknown"}


# ---------------------------------------------------------------------------
# Workflow assembly
# ---------------------------------------------------------------------------

def build_workflow():
    """Build & compile the LangGraph 5-node workflow.

    每次呼叫都重新 read ``stubs`` 模組屬性，方便測試用 monkeypatch 換掉
    單一節點（FR-007 / SC-005 / T021 verification）。
    """
    from langgraph.graph import END, StateGraph  # 延遲 import

    g = StateGraph(ResearchState)

    # 5 個業務節點
    g.add_node("planner", stubs.planner)
    g.add_node("retriever", stubs.retriever)
    g.add_node("calculator", stubs.calculator)
    g.add_node("writer", stubs.writer)
    g.add_node("compliance", stubs.compliance)

    # visual_reader：retriever 後的 best-effort escalation（flag 關 → no-op，never halts）。
    # 看圖題且檢索文字缺數字時，render 被引用頁 → vision 讀圖補脈絡（Phase B）。
    g.add_node("visual_reader", visual_reader)

    # 1 個基礎設施節點（halt 收尾）
    g.add_node("terminal", _terminal)

    g.set_entry_point("planner")

    # 每個業務節點後接條件邊：halt 跳 terminal、否則下一個
    g.add_conditional_edges(
        "planner", _route, {"continue": "retriever", "terminal": "terminal"}
    )
    g.add_conditional_edges(
        "retriever", _route, {"continue": "visual_reader", "terminal": "terminal"}
    )
    # visual_reader never halts → 直接續接 calculator（best-effort，無條件邊）。
    g.add_edge("visual_reader", "calculator")
    # calculator 後：INPUT_GATE 開 → 多一條「查無足夠來源」短路邊（L3）；關 → wiring 不變。
    from polaris.config import settings

    if settings.input_gate:
        g.add_node("no_evidence", _no_evidence)
        g.add_conditional_edges(
            "calculator",
            _route_evidence,
            {"continue": "writer", "terminal": "terminal", "no_evidence": "no_evidence"},
        )
        g.add_edge("no_evidence", END)
    else:
        g.add_conditional_edges(
            "calculator", _route, {"continue": "writer", "terminal": "terminal"}
        )
    g.add_conditional_edges(
        "writer", _route, {"continue": "compliance", "terminal": "terminal"}
    )

    # 兩個結束邊
    g.add_edge("compliance", END)
    g.add_edge("terminal", END)

    return g.compile()


if __name__ == "__main__":
    app = build_workflow()
    result = app.invoke({"query": "台積電最近兩季毛利率趨勢？"})
    print(result)
