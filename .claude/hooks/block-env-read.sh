#!/bin/bash
# Block Claude from accessing .env* files via any tool.
# Covers: Read (file_path), Bash/PowerShell (command), Grep (path/glob).
# Claude Code PreToolUse hook — exit 2 = block the tool call.
#
# Security stance: FAIL CLOSED. A security control that silently does nothing
# (e.g. when no JSON parser is on PATH) is worse than none — it grants false
# confidence. If we cannot reliably inspect a call, we block rather than allow.

INPUT=$(cat)

# A `.env` token bounded by start/end, path separators, whitespace, quotes,
# glob chars (*?) or `=` (covers `--env-file=.env`). The boundary deliberately
# EXCLUDES alphanumerics so `process.env` (Node.js) and similar identifiers do
# not trigger — at the cost of not matching files like `prod.env`. Optional
# extension (`.env.local`, `.env.prod`) is matched too.
ENV_BOUNDARY='[/\\[:space:]"'"'"'*?=]'
check_env_pattern() {
  printf '%s' "$1" | grep -qiE "(^|$ENV_BOUNDARY)\.env(\.[A-Za-z0-9_.-]+)?($ENV_BOUNDARY|\$)"
}

# Resolve a JSON parser once. Prefer jq (already used by this repo's tooling),
# then python3, then python. `python` alone is absent on modern macOS/Linux —
# the original script hard-coded it and so failed open everywhere.
JSON_PARSER=""
if command -v jq >/dev/null 2>&1; then
  JSON_PARSER="jq"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PARSER="python3"
elif command -v python >/dev/null 2>&1; then
  JSON_PARSER="python"
fi

get_field() {
  # $1 = JSON field name; prints its string value (empty if absent)
  case "$JSON_PARSER" in
    jq)
      printf '%s' "$INPUT" | jq -r --arg k "$1" '.[$k] // empty' 2>/dev/null
      ;;
    python3 | python)
      printf '%s' "$INPUT" | "$JSON_PARSER" -c \
        "import sys,json; print(json.load(sys.stdin).get(sys.argv[1],''))" "$1" 2>/dev/null
      ;;
    *)
      printf ''
      ;;
  esac
}

# No parser available → cannot inspect fields. Fail closed: scan the raw tool
# input as a backstop, and block on any .env reference. Warn either way so the
# misconfiguration is visible instead of silent.
if [ -z "$JSON_PARSER" ]; then
  echo "WARN: block-env-read.sh 找不到 jq/python3/python，無法精確解析工具參數；退回原始字串掃描並採保守攔截。" >&2
  if check_env_pattern "$INPUT"; then
    echo "BLOCKED: 偵測到 .env 參照且環境無 JSON 解析器可判讀 → 保守攔截以防金鑰洩漏。" >&2
    exit 2
  fi
  exit 0
fi

# Read tool — check file_path
FILE_PATH=$(get_field file_path)
if [ -n "$FILE_PATH" ]; then
  if check_env_pattern "$FILE_PATH"; then
    echo "BLOCKED: .env 檔案含敏感金鑰，禁止讀入對話上下文。請直接在終端機操作。" >&2
    exit 2
  fi
  exit 0
fi

# Bash / PowerShell tool — check command string
COMMAND=$(get_field command)
if [ -n "$COMMAND" ]; then
  if check_env_pattern "$COMMAND"; then
    echo "BLOCKED: 指令含 .env 路徑，禁止執行以防金鑰洩漏至對話上下文。" >&2
    exit 2
  fi
  exit 0
fi

# Grep tool — check both path AND glob (glob=".env*" scopes the search to .env
# files and leaks their values; checking only path let that slip through).
for field in path glob; do
  VALUE=$(get_field "$field")
  if [ -n "$VALUE" ] && check_env_pattern "$VALUE"; then
    echo "BLOCKED: Grep $field 含 .env，禁止搜尋以防值洩漏。" >&2
    exit 2
  fi
done

exit 0
