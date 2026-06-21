#!/usr/bin/env bash
# Throttled wrapper around `gh` — prevents the API-burst pattern that got the
# account hit by GitHub's anti-abuse / secondary rate limit (and suspended,
# 2026-06-22). Use this INSTEAD of bare `gh` for any GitHub interaction,
# especially content-generating ones (comments, PR/issue create, reviews).
#
# What it enforces (mirrors GitHub's own "avoid secondary rate limits" guidance:
# https://docs.github.com/rest/using-the-rest-api/rate-limits-for-the-rest-api):
#   1. SERIAL  — never two `gh` calls at once (atomic mkdir lock; flock-free so
#                it works on macOS, which ships no flock).
#   2. SPACED  — a minimum gap between calls, persisted ACROSS invocations so a
#                loop of separate `gh-throttle.sh` calls can't burst. Mutating
#                calls (create/comment/edit/merge/review/POST…) get a bigger gap.
#   3. BACKOFF — on a secondary/primary rate-limit error, exponential back-off
#                and retry instead of hammering (which is what escalates a soft
#                throttle into a suspension).
#   4. LOGGED  — every call is appended to a log so bursts are visible after.
#
# This wrapper can't WRITE your consolidated comment for you, but it DOES refuse
# to spray: past GH_THROTTLE_COMMENT_CAP comment-creations per window it errors
# out (exit 3) and tells you to batch into one. See AGENTS.md.
#
# Usage:
#   scripts/gh-throttle.sh pr comment 132 --body "…"
#   scripts/gh-throttle.sh api -X POST repos/:owner/:repo/issues/1/comments -f body=hi
#   scripts/gh-throttle.sh --audit          # show recent throttled calls
#
# Tunables (env, all optional):
#   GH_THROTTLE_MUTATING_GAP  seconds between mutating calls   (default 5)
#   GH_THROTTLE_READ_GAP      seconds between read-only calls  (default 1)
#   GH_THROTTLE_MAX_RETRIES   retries on rate-limit error      (default 4)
#   GH_THROTTLE_BACKOFF_BASE  first back-off, doubles each try (default 60)
#   GH_THROTTLE_LOCK_TIMEOUT  stale-lock break, seconds        (default 120)
#   GH_THROTTLE_COMMENT_CAP   max comment-creations per window (default 8)
#   GH_THROTTLE_COMMENT_WINDOW window for the cap, seconds      (default 3600)
#   GH_THROTTLE_FORCE=1       bypass the comment cap once (use deliberately)
#   GH_THROTTLE_BIN           gh binary                        (default gh)
#   GH_THROTTLE_STATE_DIR     state/log dir  (default $TMPDIR/polaris-gh-throttle)
#   GH_THROTTLE_DRYRUN=1      print the plan, don't call gh
set -euo pipefail

MUTATING_GAP="${GH_THROTTLE_MUTATING_GAP:-5}"
READ_GAP="${GH_THROTTLE_READ_GAP:-1}"
MAX_RETRIES="${GH_THROTTLE_MAX_RETRIES:-4}"
BACKOFF_BASE="${GH_THROTTLE_BACKOFF_BASE:-60}"
LOCK_TIMEOUT="${GH_THROTTLE_LOCK_TIMEOUT:-120}"
COMMENT_CAP="${GH_THROTTLE_COMMENT_CAP:-8}"
COMMENT_WINDOW="${GH_THROTTLE_COMMENT_WINDOW:-3600}"
GH_BIN="${GH_THROTTLE_BIN:-gh}"
STATE_DIR="${GH_THROTTLE_STATE_DIR:-${TMPDIR:-/tmp}/polaris-gh-throttle}"

LOCK_DIR="$STATE_DIR/lock"
STAMP_FILE="$STATE_DIR/last_call_epoch"
LOG_FILE="$STATE_DIR/calls.log"
COMMENT_FILE="$STATE_DIR/comment_epochs"

mkdir -p "$STATE_DIR"

now()  { date +%s; }
log()  { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG_FILE"; }
note() { printf '⏳ gh-throttle: %s\n' "$*" >&2; }

# --audit: dump the recent call log and exit.
if [ "${1:-}" = "--audit" ]; then
  [ -f "$LOG_FILE" ] && tail -n "${2:-40}" "$LOG_FILE" || echo "(no calls logged yet at $LOG_FILE)"
  exit 0
fi

if [ "$#" -eq 0 ]; then
  echo "usage: gh-throttle.sh <gh args…>   |   gh-throttle.sh --audit [N]" >&2
  exit 2
fi

# ---- classify: is this a mutating / content-generating call? ----------------
# These are what GitHub's content-creation limits actually target.
is_mutating() {
  case " $* " in
    *" create "*|*" comment "*|*" edit "*|*" merge "*|*" review "*|*" close "*\
    |*" reopen "*|*" delete "*|*" ready "*|*" pin "*|*" unpin "*|*" lock "*\
    |*" unlock "*|*" transfer "*|*" rename "*|*" upload "*|*" add "*|*" remove "*)
      return 0 ;;
  esac
  # `gh api` with a write method, field flags, or a request body = mutating.
  case " $* " in
    *" api "*)
      case " $* " in
        *" -X POST "*|*" -X PATCH "*|*" -X PUT "*|*" -X DELETE "*\
        |*" --method POST "*|*" --method PATCH "*|*" --method PUT "*|*" --method DELETE "*\
        |*" -f "*|*" -F "*|*" --field "*|*" --raw-field "*|*" --input "*)
          return 0 ;;
      esac ;;
  esac
  return 1
}

if is_mutating "$@"; then
  GAP="$MUTATING_GAP"; KIND="mutating"
else
  GAP="$READ_GAP";     KIND="read"
fi

# A comment CREATION specifically — `gh pr|issue comment` (without --edit-last),
# or an `api` POST to a *.../comments endpoint. Editing an existing comment is
# fine; spraying new ones is the exact behaviour that got the account flagged.
is_comment() {
  case " $* " in *" --edit-last "*) return 1 ;; esac
  case " $* " in
    *" pr comment "*|*" issue comment "*) return 0 ;;
  esac
  case " $* " in
    *" api "*) case " $* " in *comments*) is_mutating "$@" && return 0 ;; esac ;;
  esac
  return 1
}

# ---- serialize: atomic mkdir lock (no flock on macOS) ------------------------
acquire_lock() {
  local waited=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    # Break a stale lock left by a crashed call.
    if [ -d "$LOCK_DIR" ]; then
      local age; age=$(( $(now) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || stat -c %Y "$LOCK_DIR" 2>/dev/null || now) ))
      if [ "$age" -gt "$LOCK_TIMEOUT" ]; then
        note "breaking stale lock (${age}s old)"; rmdir "$LOCK_DIR" 2>/dev/null || true; continue
      fi
    fi
    [ "$waited" -ge "$LOCK_TIMEOUT" ] && { note "lock wait exceeded ${LOCK_TIMEOUT}s, giving up"; exit 75; }
    sleep 1; waited=$(( waited + 1 ))
  done
}
acquire_lock
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# ---- space: sleep until the min gap since the last call has elapsed ----------
if [ -f "$STAMP_FILE" ]; then
  last=$(cat "$STAMP_FILE" 2>/dev/null || echo 0)
  elapsed=$(( $(now) - last ))
  if [ "$elapsed" -lt "$GAP" ]; then
    wait_s=$(( GAP - elapsed ))
    note "waiting ${wait_s}s ($KIND gap)…"
    sleep "$wait_s"
  fi
fi

# ---- hard cap on comment CREATION (rolling window) --------------------------
# This is the rail that bare `gh` doesn't have: refuse to spray comments.
# Batch your findings into ONE comment instead. Override once with GH_THROTTLE_FORCE=1.
if is_comment "$@"; then
  cutoff=$(( $(now) - COMMENT_WINDOW ))
  recent=0
  if [ -f "$COMMENT_FILE" ]; then
    tmp="$COMMENT_FILE.$$"
    awk -v c="$cutoff" '$1+0 >= c' "$COMMENT_FILE" >"$tmp" 2>/dev/null || true
    mv "$tmp" "$COMMENT_FILE"
    recent=$(wc -l <"$COMMENT_FILE" | tr -d ' ')
  fi
  if [ "$recent" -ge "$COMMENT_CAP" ] && [ "${GH_THROTTLE_FORCE:-0}" != "1" ]; then
    note "REFUSED — $recent comments in the last $((COMMENT_WINDOW/60))min already (cap $COMMENT_CAP)."
    note "Batch your findings into ONE comment, or set GH_THROTTLE_FORCE=1 to override deliberately."
    log "CAP  refused comment ($recent/$COMMENT_CAP) gh $*"
    exit 3
  fi
  now >>"$COMMENT_FILE"
fi

if [ "${GH_THROTTLE_DRYRUN:-0}" = "1" ]; then
  note "DRYRUN ($KIND) would run: $GH_BIN $*"
  now >"$STAMP_FILE"
  exit 0
fi

# ---- run with rate-limit-aware exponential back-off -------------------------
attempt=0; backoff="$BACKOFF_BASE"; rc=0
while :; do
  out_file="$STATE_DIR/last_stdout.$$"
  set +e
  "$GH_BIN" "$@" >"$out_file" 2>&1
  rc=$?
  set -e
  cat "$out_file"
  now >"$STAMP_FILE"

  if [ "$rc" -eq 0 ]; then
    log "OK   ($KIND) gh $*"
    rm -f "$out_file"; exit 0
  fi

  # Retry ONLY on rate-limit signals; surface every other failure immediately.
  if grep -qiE 'secondary rate limit|exceeded a secondary|api rate limit exceeded|rate limit|retry-after|too many requests|http 429' "$out_file" \
     && [ "$attempt" -lt "$MAX_RETRIES" ]; then
    attempt=$(( attempt + 1 ))
    note "rate-limited (rc=$rc). back-off ${backoff}s, retry $attempt/$MAX_RETRIES…"
    log "RL   ($KIND) backoff=${backoff}s retry=$attempt gh $*"
    rm -f "$out_file"
    sleep "$backoff"
    backoff=$(( backoff * 2 ))
    continue
  fi

  log "FAIL rc=$rc ($KIND) gh $*"
  rm -f "$out_file"
  exit "$rc"
done
