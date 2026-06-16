#!/bin/bash
# Polaris Desk — session-start hook (Claude Code on the web)
# Installs Python deps and wires GCP credentials from env vars.
#
# Required env vars (set in code.claude.com → Environment → Variables):
#   GOOGLE_SA_KEY_B64  — base64-encoded GCP service account JSON
#   GEMINI_API_KEY     — Gemini API key
#   GCP_PROJECT        — GCP project ID (e.g. polaris-desk-team)
#   VECTOR_BACKEND     — bigquery (default) or pgvector
#   COHERE_API_KEY     — (optional) enables Cohere Rerank
#
# How to base64-encode your SA key locally:
#   base64 -i ~/path/to/sa-key.json | tr -d '\n'
# Then paste the result as GOOGLE_SA_KEY_B64 in the env config.

set -euo pipefail

# Only run in Claude Code remote environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# ── 1. Python dependencies ────────────────────────────────────────────────────
echo "[session-start] Installing Python dependencies..."
uv venv --python 3.13 --quiet 2>/dev/null || uv venv --quiet
uv pip install -e ".[dev]" --quiet

# ── 2. GCP service account credentials ───────────────────────────────────────
SA_KEY_PATH="/tmp/polaris-sa-key.json"

if [ -n "${GOOGLE_SA_KEY_B64:-}" ]; then
  echo "[session-start] Decoding GCP service account key..."
  echo "$GOOGLE_SA_KEY_B64" | base64 -d > "$SA_KEY_PATH"
  chmod 600 "$SA_KEY_PATH"
  echo "export GOOGLE_APPLICATION_CREDENTIALS=$SA_KEY_PATH" >> "$CLAUDE_ENV_FILE"
  echo "[session-start] GOOGLE_APPLICATION_CREDENTIALS set → $SA_KEY_PATH"
else
  echo "[session-start] GOOGLE_SA_KEY_B64 not set — skipping GCP credentials (BQ smoke will skip)"
fi

# ── 3. Forward other GCP/API env vars to session ─────────────────────────────
for var in GEMINI_API_KEY GCP_PROJECT VECTOR_BACKEND COHERE_API_KEY; do
  val="${!var:-}"
  if [ -n "$val" ]; then
    echo "export $var=$val" >> "$CLAUDE_ENV_FILE"
    echo "[session-start] $var forwarded to session"
  fi
done

echo "[session-start] Done."
