#!/usr/bin/env bash
# 抽取（vision-OCR → JSONL，不入庫、不吃 embedding 配額）剩餘 ticker。
# Vertex GA flash，逐 ticker 序列、可重跑（chunk id idempotent）。
set -u
cd /Users/shihhuichi/code/polaris-desk/.claude/worktrees/clever-rhodes-cc1234

export GEMINI_USE_VERTEX=1 VISION_EXTRACTION=1
export GEMINI_MODEL_FLASH=gemini-2.5-flash GEMINI_MODEL_PRO=gemini-2.5-pro

LOG=/tmp/extract_remaining.log
# 只跑「未完成抽取」的 ticker（6669/2892 已完成，交由 embed 補救）；6505(14 decks)最後。
TICKERS="3034 3037 3231 2886 3711 6505"

echo "=== EXTRACT START $(date '+%F %T %Z') tickers: $TICKERS ===" | tee -a "$LOG"
for t in $TICKERS; do
  echo "--- [$t] start $(date '+%T') ---" | tee -a "$LOG"
  uv run python scripts/vision_ingest_pilot.py --ticker "$t" --concurrency 4 --throttle 0.5 >>"$LOG" 2>&1
  rc=$?
  n=$(wc -l < "data/vision_chunks/$t.jsonl" 2>/dev/null | tr -d ' ')
  echo "--- [$t] done rc=$rc chunks=${n:-0} $(date '+%T') ---" | tee -a "$LOG"
done
echo "=== EXTRACT ALL DONE $(date '+%F %T %Z') ===" | tee -a "$LOG"
