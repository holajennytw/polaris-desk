#!/bin/bash
# Block Claude from accessing .env* files via any tool.
# Covers: Read (file_path), Bash/PowerShell (command), Grep (path/glob).
# Claude Code PreToolUse hook — exit 2 = block the tool call.

INPUT=$(cat)

check_env_pattern() {
  echo "$1" | grep -qiE '(^|[/\\])\.env(\.[^/\\[:space:]"'"'"']+)?([[:space:]"'"'"'\\]|$)'
}

# Read tool — check file_path
FILE_PATH=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null || echo "")
if [ -n "$FILE_PATH" ]; then
  if check_env_pattern "$FILE_PATH"; then
    echo "BLOCKED: .env 檔案含敏感金鑰，禁止讀入對話上下文。請直接在終端機操作。" >&2
    exit 2
  fi
  exit 0
fi

# Bash / PowerShell tool — check command string
COMMAND=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || echo "")
if [ -n "$COMMAND" ]; then
  if check_env_pattern "$COMMAND"; then
    echo "BLOCKED: 指令含 .env 路徑，禁止執行以防金鑰洩漏至對話上下文。" >&2
    exit 2
  fi
  exit 0
fi

# Grep tool — check path field
GREP_PATH=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('path',''))" 2>/dev/null || echo "")
if [ -n "$GREP_PATH" ]; then
  if check_env_pattern "$GREP_PATH"; then
    echo "BLOCKED: Grep 目標含 .env 路徑，禁止搜尋以防值洩漏。" >&2
    exit 2
  fi
fi

exit 0
