#!/usr/bin/env python3
"""從 src/polaris/notifications/demo.html 生成 standalone 版 demo。

Standalone 版 = 同一套 UI + 注入 fetch 攔截層，把通知管線邏輯
（validate → 去重 → 接地 → 合規 6 關鍵字 floor → digest → 收件匣）
用 JS 在瀏覽器內重現 —— 無後端、file:// 直開即玩，供放 GitHub / Google
Drive 給團隊非同步看 UI/UX。

單一事實來源是 demo.html；改了 UI 之後重跑本 script 再生 artifact：

    python scripts/build_standalone_demo.py

注意：JS mock 只重現確定性 floor（同 graph/compliance.py 的 6 關鍵字），
不含 Gemini smart 層與 Slack 外送——頁頂 ribbon 有標示，避免誤導。
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "polaris" / "notifications" / "demo.html"
OUT = REPO / "docs" / "demo" / "notification-center-demo.html"

RIBBON = """
<div style="background:linear-gradient(90deg,#1a2440,#243254);border-bottom:1px solid #e3b04b55;
  color:#e3b04b;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;
  padding:8px 28px;text-align:center">
  STANDALONE 模擬版 — 管線邏輯（去重 / 接地 / 6 關鍵字合規攔截 / digest）以 JS 重現，無後端、可離線直開。
  真實管線版：repo 內 <b>PORT=8765 python -m polaris.api</b> → /demo/notifications
</div>
"""

# 與 src/polaris/graph/compliance.py BUYSELL_KEYWORDS、notifications/ 管線語意對齊。
MOCK_JS = r"""
<script>
"use strict";
/* Standalone mock backend：攔截 /notifications* fetch，於瀏覽器內重現管線語意。
   對齊 polaris.notifications（specs/002）：validate → 去重 → 接地 → 合規 floor
   → digest / 派送。僅含確定性 floor；無 Gemini smart 層、無 Slack 外送。 */
(function () {
  const KEYWORDS = ["建議買進", "建議賣出", "加碼", "減碼", "看多", "看空"];
  const TYPES = ["watchdog_alert","watchlist_event","data_ingested","research_done",
                 "contradiction","pipeline_health","ops_alert"];
  const LABELS = {watchdog_alert:"合規警示", watchlist_event:"追蹤事件", data_ingested:"新資料入庫",
                  research_done:"研究完成", contradiction:"來源矛盾", pipeline_health:"管線健康",
                  ops_alert:"成本警報", compliance_incident:"合規事故"};
  const EVIDENCE_CAP = 50;

  let seen, digestIndex, items;
  function reset(){ seen = new Set(); digestIndex = new Map(); items = new Map(); }
  reset();

  const summarize = ev => ((ev.body || ev.title || "").slice(0, 100));

  function build(ev, complianceStatus){
    const nid = "ntf-" + ev.event_id;
    return {
      notification_id: nid, event_id: ev.event_id, type: ev.type, audience: ev.audience,
      ticker: ev.ticker ?? null, title: ev.title, summary: summarize(ev),
      severity: ev.severity || "info", evidence: (ev.evidence || []).slice(),
      deep_link: "/notifications/" + nid, created_at: ev.occurred_at, read_at: null,
      compliance_status: complianceStatus, digest_count: 1,
    };
  }

  function makeIncident(ev){
    const nid = "ntf-incident-" + ev.event_id;
    return {
      notification_id: nid, event_id: ev.event_id, type: "compliance_incident",
      audience: "internal", ticker: ev.ticker ?? null,
      title: "合規事故：事件 " + ev.event_id + " 文案遭攔截",
      summary: "通知文案命中合規規則，已攔截未派送；請依憲法原則 I 記錄 incident 並補測試。",
      severity: "alert", evidence: (ev.evidence || []).slice(),
      deep_link: "/notifications/" + nid, created_at: ev.occurred_at, read_at: null,
      compliance_status: "skipped", digest_count: 1,
    };
  }

  function publish(ev){
    if (!ev || !ev.event_id || !ev.title || !ev.occurred_at || !TYPES.includes(ev.type)
        || !["user","internal"].includes(ev.audience))
      return {status:"rejected", notification:null, reason:"invalid event: 缺必填欄位或型別不合法"};
    if (seen.has(ev.event_id))
      return {status:"deduped", notification:null, reason:"event_id already seen: " + ev.event_id};
    seen.add(ev.event_id);
    if (ev.audience === "user" && !(ev.evidence || []).length)
      return {status:"rejected", notification:null, reason:"user-facing event requires non-empty evidence"};

    let complianceStatus = "skipped";
    if (ev.audience === "user"){
      const draft = ev.title + "\n" + summarize(ev);
      if (KEYWORDS.some(kw => draft.includes(kw))){
        const incident = makeIncident(ev);
        items.set(incident.notification_id, incident);
        return {status:"blocked", notification:incident,
                reason:"compliance blocked event " + ev.event_id + "; incident filed"};
      }
      complianceStatus = "passed";
    }

    const n = build(ev, complianceStatus);
    const day = String(ev.occurred_at).slice(0, 10);
    const key = (n.ticker ?? "") + "|" + n.type + "|" + day;
    if (n.severity === "info" && digestIndex.has(key)){
      const existing = items.get(digestIndex.get(key));
      if (existing){
        const count = existing.digest_count + 1;
        const prefix = existing.ticker ? existing.ticker + " " : "";
        const merged = Object.assign({}, existing, {
          title: prefix + "今日 " + count + " 則更新",
          summary: (LABELS[existing.type] || existing.type) + " ×" + count,
          digest_count: count,
          evidence: existing.evidence.concat(n.evidence).slice(0, EVIDENCE_CAP),
          created_at: n.created_at,
        });
        items.set(merged.notification_id, merged);
        return {status:"digested", notification:merged, reason:""};
      }
    }
    items.set(n.notification_id, n);
    if (n.severity === "info") digestIndex.set(key, n.notification_id);
    return {status:"delivered", notification:n, reason:""};
  }

  function listResponse(params){
    const ticker = params.get("ticker"), type = params.get("type");
    const all = [...items.values()]
      .filter(n => (!ticker || n.ticker === ticker) && (!type || n.type === type))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0));
    const unread = [...items.values()].filter(n => !n.read_at).length;
    return {items: all, unread_count: unread, delivery_failures: []};
  }

  function json(data, status){
    return new Response(JSON.stringify(data),
      {status: status || 200, headers: {"Content-Type": "application/json"}});
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    const u = String(url);
    if (!u.startsWith("/notifications")) return realFetch(url, opts);
    if (u === "/notifications/reset") { reset(); return Promise.resolve(json({status:"reset"})); }
    if (u === "/notifications/events")
      return Promise.resolve(json(publish(JSON.parse((opts && opts.body) || "{}"))));
    const read = u.match(/^\/notifications\/(.+)\/read$/);
    if (read){
      const n = items.get(decodeURIComponent(read[1]));
      if (!n) return Promise.resolve(json({detail:"notification not found"}, 404));
      const updated = Object.assign({}, n, {read_at: new Date().toISOString().slice(0, 19)});
      items.set(updated.notification_id, updated);
      return Promise.resolve(json(updated));
    }
    return Promise.resolve(json(listResponse(new URL(u, "http://x").searchParams)));
  };
})();
</script>
"""


def main() -> None:
    html = SRC.read_text(encoding="utf-8")
    marker = "<script>\n\"use strict\";"
    if marker not in html:
        raise SystemExit("demo.html 主 script 標記未找到 — 檢查 build 標記是否仍對齊")
    html = html.replace("<body>", "<body>" + RIBBON, 1)
    html = html.replace(marker, MOCK_JS + marker, 1)
    html = html.replace("<title>北辰 Polaris Desk — 通知中心 Demo</title>",
                        "<title>北辰 Polaris Desk — 通知中心 Demo（standalone）</title>", 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"✓ {OUT.relative_to(REPO)}（{len(html):,} bytes）")


if __name__ == "__main__":
    main()
