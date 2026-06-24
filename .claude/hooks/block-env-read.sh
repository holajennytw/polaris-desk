#!/bin/bash
# Block Claude from accessing .env* files via any tool.
# Covers: Read (file_path), Bash/PowerShell (command), Grep (path/glob/pattern).
# Claude Code PreToolUse hook — exit 2 = block the tool call.
#
# Uses sed/grep only to avoid Python encoding/stdin issues on Windows Git Bash.
# Reads the raw hook JSON once; extracts field values via sed; checks .env patterns.

INPUT=$(cat)

# .env as a path component: /path/.env, \path\.env, .env.local, .env, etc.
ENV_PATTERN='(^|[/\\])\.env(\.[^/\\[:space:]"]+)?(["[:space:]/\\]|$)'

extract_field() {
  # Extract the string value of a JSON field from $INPUT using sed (BRE).
  # Works for compact/single-line JSON without escaped quotes in values.
  printf '%s' "$INPUT" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -1
}

block_if_env() {
  [ -n "$1" ] && printf '%s' "$1" | grep -qiE "$ENV_PATTERN"
}

# Read tool
FILE_PATH=$(extract_field file_path)
if block_if_env "$FILE_PATH"; then
  echo "BLOCKED: .env 檔案含敏感金鑰，禁止讀入對話上下文。請直接在終端機操作。" >&2
  exit 2
fi

# Bash / PowerShell tool
COMMAND=$(extract_field command)
if block_if_env "$COMMAND"; then
  echo "BLOCKED: 指令含 .env 路徑，禁止執行以防金鑰洩漏至對話上下文。" >&2
  exit 2
fi

# Grep tool — path, glob, and pattern fields
for FIELD in path glob pattern; do
  VAL=$(extract_field "$FIELD")
  if block_if_env "$VAL"; then
    echo "BLOCKED: Grep 目標含 .env 路徑，禁止搜尋以防值洩漏。" >&2
    exit 2
  fi
done

exit 0
