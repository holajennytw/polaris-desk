#!/usr/bin/env bash
# 批次 embed 補救：把指定 ticker（或全部）已抽取但未進 BQ 的塊補入 polaris_dev_wayne。
# 從 main repo .env 讀 GEMINI_API_KEY（多把逗號分隔，腳本會輪替、跳過 429 用罄的把）。
set -u
cd /Users/shihhuichi/code/polaris-desk/.claude/worktrees/clever-rhodes-cc1234

export GEMINI_API_KEY=$(awk -F= '/^GEMINI_API_KEY=/{sub(/^GEMINI_API_KEY=/,"");print}' /Users/shihhuichi/code/polaris-desk/.env)
export BQ_DATASET=polaris_dev_wayne VECTOR_BACKEND=bigquery
export PYTHONUNBUFFERED=1   # 即時把進度寫進 LOG（否則 block-buffer 到結束才出現）

LOG=/tmp/embed_recovery.log
ARGS=()
for t in "$@"; do ARGS+=(--ticker "$t"); done

echo "=== EMBED START $(date '+%F %T %Z') tickers: ${*:-ALL} ===" | tee -a "$LOG"
# bash 3.2 + set -u：空陣列 "${ARGS[@]}" 會報 unbound → 用 +展開 規避。
uv run python scripts/vision_reembed_recovery.py ${ARGS[@]+"${ARGS[@]}"} >>"$LOG" 2>&1
rc=$?
echo "=== EMBED DONE rc=$rc $(date '+%F %T %Z') ===" | tee -a "$LOG"
