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
#   resident-session.sh list
#   resident-session.sh close <key> [--note "<note>"]
#
# Contract (see the orchestration skill, <ResidentSessions>):
#   - One key = one live specialist session, scoped to a chat topic and
#     purpose (e.g. "12116-creator-pv"). Keys are [a-zA-Z0-9._-]+.
#   - Turns are strictly serialized per key (mkdir lock). A busy key
#     fails fast with exit 75 — never queue blindly; wait for the
#     completion notification of the in-flight turn.
#   - The specialist's reply is this script's stdout. The session id is
#     re-captured from stderr on every turn and written back to the
#     registry, so compaction-induced id rotation never strands a key.
#   - Long turns are expected: ALWAYS invoke via terminal
#     background=true + notify_on_complete. TURN_TIMEOUT (default 5400s)
#     hard-kills a runaway turn.
#   - `close` marks the registry entry closed after delivery is
#     accepted. Resident sessions are per-deliverable, not immortal:
#     close on acceptance so context rot never accumulates.
#
# Registry: ~/.hermes/profiles/assistant/resident-sessions/<key>.json
# (runtime state, never tracked in git). Turn log: <key>.log.

set -u

HERMES="$(command -v hermes || echo "$HOME/.local/bin/hermes")"
REG_DIR="${RESIDENT_SESSION_DIR:-$HOME/.hermes/profiles/assistant/resident-sessions}"
TURN_TIMEOUT="${TURN_TIMEOUT:-5400}"

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
    if k == "turns+":
        data["turns"] = int(data.get("turns") or 0) + int(v or 1)
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

check_key() {
  case "$1" in
    (*[!a-zA-Z0-9._-]*|'') die "invalid key '$1' (use [a-zA-Z0-9._-]+)";;
  esac
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
    printf 'resident-session: key %s has a turn in flight (lock: %s)\n' \
      "$rt_key" "$lock" >&2
    exit 75
  fi
  trap 'rm -rf "$lock" 2>/dev/null' EXIT INT TERM

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
    sleep 5
    waited=$((waited + 5))
  done
  wait "$pid"
  rc=$?

  sid="$(sed -n 's/^.*session_id: *\([A-Za-z0-9_-]*\).*$/\1/p' "$err" | tail -1)"
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
    if [ -f "$reg" ] && [ "$(json_get "$reg" status)" != "closed" ]; then
      die "key $key already exists (status: $(json_get "$reg" status)); use send, or close it first"
    fi
    json_update "$reg" "key=$key" "profile=$PROFILE" "topic=$TOPIC" \
      "session_id=" "status=starting" "created_at=$(now_iso)" "turns=0"
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
    [ -n "$sid" ] || die "key $key has no session id recorded (start failed?)"
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
    found=0
    for f in "$REG_DIR"/*.json; do
      [ -f "$f" ] || continue
      found=1
      python3 - "$f" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print("{:<28} {:<10} {:<8} turns={:<3} last={} topic={}".format(
    d.get("key",""), d.get("profile",""), d.get("status",""),
    d.get("turns",0), d.get("last_turn_at","-"), d.get("topic","") or "-"))
EOF
    done
    [ "$found" -eq 1 ] || echo "no resident sessions"
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
