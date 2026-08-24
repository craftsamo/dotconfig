#!/bin/sh
# resident-session — conversational specialist sessions (Workflow v5).
#
# The assistant's primitive for the "resident session" execution tier:
# heavy interactive work (creation, writing, research, engineering) runs
# in a persistent `hermes -p <profile> chat` session that the assistant
# supervises conversationally, instead of a kanban card round-trip.
#
#   resident-session.sh start <key> --profile <name> [--topic "<t>"] \
#       (-q "<brief>" | -f <file> | stdin)
#   resident-session.sh send  <key> (-q "<msg>" | -f <file> | stdin) \
#       [--image <path>]
#   resident-session.sh status [<key>]
#   resident-session.sh list  [--open | --all]
#   resident-session.sh close <key> [--note "<note>"]
#
# Contract (see assistant-pipeline references/execute/resident-sessions.md):
#   - One key = one live specialist session, scoped to a chat topic and
#     purpose (e.g. "12116-creator-pv"). Keys are [a-zA-Z0-9._-]+.
#   - Turns are strictly serialized per key (mkdir lock). A busy key
#     fails fast with exit 75 — never queue blindly; wait for the
#     completion notification of the in-flight turn. A lock whose holder
#     died is reclaimed automatically, so a killed turn cannot wedge a
#     key for good.
#   - The specialist's reply is this script's stdout. The session id is
#     re-captured from stderr on every turn and written back to the
#     registry, so compaction-induced id rotation never strands a key.
#   - A key whose first turn died before the CLI reported a session id
#     never established a conversation: re-run `start` with the brief to
#     restart it in place (the attempt is counted in `restarts`). Only a
#     key that HAS a session id is protected from `start`.
#   - Long turns are expected: ALWAYS invoke via terminal
#     background=true + notify_on_complete. TURN_TIMEOUT (default 5400s)
#     hard-kills a runaway turn.
#   - `close` marks the registry entry closed after delivery is
#     accepted. Resident sessions are per-deliverable, not immortal:
#     close on acceptance so context rot never accumulates.
#
# Registry: ~/.hermes/profiles/assistant/resident-sessions/<key>.json
# (runtime state, never tracked in git). Turn log: <key>.log.
#
# Tunables (env): TURN_TIMEOUT, POLL_INTERVAL, LOCK_STALE_AFTER,
# RESIDENT_SESSION_DIR, HERMES.

set -u

HERMES="${HERMES:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"
REG_DIR="${RESIDENT_SESSION_DIR:-$HOME/.hermes/profiles/assistant/resident-sessions}"
TURN_TIMEOUT="${TURN_TIMEOUT:-5400}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
LOCK_STALE_AFTER="${LOCK_STALE_AFTER:-60}"

# The assistant may run inside a worker/gateway process; the child CLI
# must resolve its own profile HOME, and must never think it is a
# kanban worker.
unset HERMES_HOME HERMES_KANBAN_TASK 2>/dev/null || :

die() { printf 'resident-session: %s\n' "$*" >&2; exit 1; }

json_get() { # json_get <file> <field>
  python3 - "$1" "$2" <<'EOF'
import json, sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))
except Exception:
    pass
EOF
}

json_update() { # json_update <file> key=value...  (creates file if absent)
  python3 - "$@" <<'EOF'
import json, os, sys, tempfile
path = sys.argv[1]
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
for kv in sys.argv[2:]:
    k, _, v = kv.partition("=")
    if k.endswith("+"):
        base = k[:-1]
        data[base] = int(data.get(base) or 0) + int(v or 1)
    else:
        data[k] = v
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
with os.fdopen(fd, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
    f.write("\n")
os.replace(tmp, path)
EOF
}

now_iso() { date '+%Y-%m-%dT%H:%M:%S'; }

# The CLI prints `session_id: <id>` on stderr; take the last occurrence so a
# resumed turn reports the id it actually ran under. Empty when the turn died
# before the CLI got that far.
extract_sid() { # extract_sid <stderr-file>
  [ -f "$1" ] || return 0
  sed -n 's/^.*session_id: *\([A-Za-z0-9_-]*\).*$/\1/p' "$1" | tail -1
}

check_key() {
  case "$1" in
    (*[!a-zA-Z0-9._-]*|'') die "invalid key '$1' (use [a-zA-Z0-9._-]+)";;
  esac
}

# Age of a lock directory. Its mtime is stamped when the holder creates
# out/err inside it, so this is effectively the turn's start time.
lock_age_seconds() { # lock_age_seconds <lockdir>
  python3 - "$1" <<'EOF'
import os, sys, time
try:
    print(int(time.time() - os.path.getmtime(sys.argv[1])))
except Exception:
    pass
EOF
}

# A lock survives a SIGKILL'd or crashed holder (the EXIT trap never runs) and
# would otherwise wedge the key forever. Reclaim only on proof of abandonment.
lock_is_stale() { # lock_is_stale <lockdir>
  ls_age="$(lock_age_seconds "$1")"
  [ -n "$ls_age" ] || return 1
  # A live turn self-kills at TURN_TIMEOUT and drops the lock in its trap, so
  # anything older cannot be live — reclaim even when the recorded pid now
  # answers, which is what pid reuse looks like.
  [ "$ls_age" -ge $((TURN_TIMEOUT + 120)) ] && return 0
  # Below that, require the holder to be provably gone. The age floor also
  # covers the window between mkdir and the pid write.
  [ "$ls_age" -ge "$LOCK_STALE_AFTER" ] || return 1
  ls_pid="$(cat "$1/pid" 2>/dev/null)"
  [ -n "$ls_pid" ] || return 0
  kill -0 "$ls_pid" 2>/dev/null && return 1
  return 0
}
read_prompt() { # -q "..." | -f file | stdin  → PROMPT
  PROMPT=""
  IMAGE=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -q) shift; PROMPT="${1:-}";;
      -f) shift; [ -f "${1:-}" ] || die "prompt file not found: ${1:-}"; PROMPT="$(cat "$1")";;
      --image) shift; IMAGE="${1:-}"; [ -f "$IMAGE" ] || die "image not found: $IMAGE";;
      --profile) shift; PROFILE="${1:-}";;
      --topic) shift; TOPIC="${1:-}";;
      --note) shift; NOTE="${1:-}";;
      *) die "unknown argument: $1";;
    esac
    shift
  done
  if [ -z "$PROMPT" ] && [ ! -t 0 ]; then PROMPT="$(cat)"; fi
  [ -n "$PROMPT" ] || die "no prompt (-q, -f, or stdin)"
}

# run_turn <key> <profile> <resume_id_or_empty>
# Prompt in $PROMPT, optional image in $IMAGE. Prints the reply.
run_turn() {
  rt_key="$1" rt_profile="$2" rt_resume="$3"
  reg="$REG_DIR/$rt_key.json"
  log="$REG_DIR/$rt_key.log"
  lock="$REG_DIR/$rt_key.lock"

  if ! mkdir "$lock" 2>/dev/null; then
    if lock_is_stale "$lock"; then
      stale_pid="$(cat "$lock/pid" 2>/dev/null)"
      stale_age="$(lock_age_seconds "$lock")"
      claim="$lock.stale.$$"
      # Claim the abandoned lock by renaming it. rename is atomic, so of two
      # racing reclaimers only one takes it away; the loser then simply loses
      # the mkdir below. Re-check the pid through the rename: if a live turn
      # grabbed the lock in between, we took the wrong directory and put it
      # straight back.
      if mv "$lock" "$claim" 2>/dev/null; then
        if [ "$(cat "$claim/pid" 2>/dev/null)" = "$stale_pid" ]; then
          printf 'resident-session: reclaiming stale lock %s (holder pid %s, age %ss)\n' \
            "$lock" "${stale_pid:-unknown}" "${stale_age:-?}" >&2
          rm -rf "$claim" 2>/dev/null
        else
          mv "$claim" "$lock" 2>/dev/null
        fi
      fi
    fi
    if ! mkdir "$lock" 2>/dev/null; then
      printf 'resident-session: key %s has a turn in flight (lock: %s, holder pid %s, age %ss)\n' \
        "$rt_key" "$lock" "$(cat "$lock/pid" 2>/dev/null || echo unknown)" \
        "$(lock_age_seconds "$lock")" >&2
      exit 75
    fi
  fi
  trap 'rm -rf "$lock" 2>/dev/null' EXIT INT TERM
  printf '%s\n' "$$" >"$lock/pid"

  out="$lock/out" err="$lock/err"
  set -- -p "$rt_profile" --cli chat -Q -q "$PROMPT"
  [ -n "$rt_resume" ] && set -- "$@" --resume "$rt_resume"
  [ -n "${IMAGE:-}" ] && set -- "$@" --image "$IMAGE"

  {
    printf '\n=== turn %s (%s) ===\n' "$(now_iso)" "${rt_resume:-new}"
    printf 'prompt: %.400s\n' "$PROMPT"
  } >>"$log"

  "$HERMES" "$@" >"$out" 2>"$err" &
  pid=$!
  waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$TURN_TIMEOUT" ]; then
      kill -TERM "$pid" 2>/dev/null; sleep 10
      kill -KILL "$pid" 2>/dev/null
      printf 'TIMEOUT after %ss\n' "$TURN_TIMEOUT" >>"$log"
      json_update "$reg" "status=timeout" "last_turn_at=$(now_iso)"
      die "turn timed out after ${TURN_TIMEOUT}s (key $rt_key)"
    fi
    sleep "$POLL_INTERVAL"
    waited=$((waited + POLL_INTERVAL))
  done
  wait "$pid"
  rc=$?

  sid="$(extract_sid "$err")"
  {
    printf -- '--- reply (rc=%s, session=%s) ---\n' "$rc" "${sid:-unknown}"
    cat "$out"
    printf -- '--- stderr tail ---\n'
    tail -5 "$err"
  } >>"$log"

  if [ "$rc" -ne 0 ]; then
    json_update "$reg" "status=error" "last_turn_at=$(now_iso)"
    printf 'resident-session: turn failed (rc=%s); stderr tail:\n' "$rc" >&2
    tail -10 "$err" >&2
    exit "$rc"
  fi

  json_update "$reg" \
    "session_id=${sid:-$rt_resume}" "status=idle" \
    "last_turn_at=$(now_iso)" "turns+=1"
  cat "$out"
}

cmd="${1:-}"; [ -n "$cmd" ] && shift || die "usage: resident-session.sh start|send|status|list|close ..."
mkdir -p "$REG_DIR"

case "$cmd" in
  start)
    key="${1:-}"; shift || :
    check_key "$key"
    PROFILE="" TOPIC=""
    read_prompt "$@"
    [ -n "$PROFILE" ] || die "start requires --profile <name>"
    reg="$REG_DIR/$key.json"
    RESTART=0
    if [ -f "$reg" ]; then
      existing_st="$(json_get "$reg" status)"
      existing_sid="$(json_get "$reg" session_id)"
      if [ -n "$existing_sid" ]; then
        # A real conversation exists behind this key; starting over would
        # orphan it.
        [ "$existing_st" = "closed" ] || die \
          "key $key is live (status: $existing_st, session $existing_sid, turns $(json_get "$reg" turns)); use send, or close it first"
      elif [ "$existing_st" != "closed" ]; then
        # The first turn died before the CLI reported a session id. Such a key
        # used to be stranded for good — `send` refuses it for having no id and
        # `start` refused it for already existing. Restart it in place, unless
        # a turn really is still running.
        if [ -d "$REG_DIR/$key.lock" ] && ! lock_is_stale "$REG_DIR/$key.lock"; then
          printf 'resident-session: key %s has a turn in flight (lock: %s); not restarting\n' \
            "$key" "$REG_DIR/$key.lock" >&2
          exit 75
        fi
        RESTART=1
      fi
    fi
    if [ "$RESTART" -eq 1 ]; then
      json_update "$reg" "key=$key" "profile=$PROFILE" "topic=$TOPIC" \
        "session_id=" "status=starting" "turns=0" "restarts+=1"
      printf 'resident-session: restarting %s — previous attempt never established a session (restart #%s)\n' \
        "$key" "$(json_get "$reg" restarts)" >&2
    else
      json_update "$reg" "key=$key" "profile=$PROFILE" "topic=$TOPIC" \
        "session_id=" "status=starting" "created_at=$(now_iso)" "turns=0" \
        "closed_at=" "close_note="
    fi
    run_turn "$key" "$PROFILE" ""
    ;;
  send)
    key="${1:-}"; shift || :
    check_key "$key"
    reg="$REG_DIR/$key.json"
    [ -f "$reg" ] || die "unknown key $key (start it first)"
    st="$(json_get "$reg" status)"
    [ "$st" = "closed" ] && die "key $key is closed"
    sid="$(json_get "$reg" session_id)"
    [ -n "$sid" ] || die "key $key never established a session (status: $st); re-run 'start' with the brief to restart it"
    read_prompt "$@"
    run_turn "$key" "$(json_get "$reg" profile)" "$sid"
    ;;
  status)
    key="${1:-}"
    if [ -n "$key" ]; then
      check_key "$key"
      [ -f "$REG_DIR/$key.json" ] || die "unknown key $key"
      cat "$REG_DIR/$key.json"
    else
      "$0" list
    fi
    ;;
  list)
    # One python3 process for the whole registry: the per-file loop cost 23s
    # at 101 keys. Closed keys are hidden by default so the live ones are
    # readable; newest turn first.
    LIST_ALL=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --all) LIST_ALL=1;;
        --open) LIST_ALL=0;;
        *) die "unknown argument: $1";;
      esac
      shift
    done
    python3 - "$REG_DIR" "$LIST_ALL" <<'EOF'
import glob, json, os, sys
reg_dir, show_all = sys.argv[1], sys.argv[2] == "1"
rows, hidden = [], 0
for path in sorted(glob.glob(os.path.join(reg_dir, "*.json"))):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    if not show_all and d.get("status") == "closed":
        hidden += 1
        continue
    rows.append(d)
rows.sort(key=lambda d: str(d.get("last_turn_at") or d.get("created_at") or ""),
          reverse=True)
for d in rows:
    print("{:<28} {:<10} {:<8} turns={:<3} last={} topic={}".format(
        d.get("key", ""), d.get("profile", ""), d.get("status", ""),
        d.get("turns", 0), d.get("last_turn_at", "-"), d.get("topic", "") or "-"))
if not rows:
    print("no resident sessions" if show_all else "no open resident sessions")
if hidden:
    print("({} closed hidden; --all to show)".format(hidden))
EOF
    ;;
  close)
    key="${1:-}"; shift || :
    check_key "$key"
    reg="$REG_DIR/$key.json"
    [ -f "$reg" ] || die "unknown key $key"
    NOTE=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --note) shift; NOTE="${1:-}";;
        *) die "unknown argument: $1";;
      esac
      shift
    done
    json_update "$reg" "status=closed" "closed_at=$(now_iso)" "close_note=$NOTE"
    echo "closed $key"
    ;;
  *)
    die "unknown command: $cmd"
    ;;
esac
