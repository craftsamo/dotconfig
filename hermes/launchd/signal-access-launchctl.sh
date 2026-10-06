#!/usr/bin/env bash
# Link the user's Signal account and run its sync LaunchAgent (signal-access).
#
# The signal tool reads the local mirror (~/.local/state/hermes-signal/mirror.db) that this agent
# keeps current, and sends through the socket of the signal-cli daemon the agent owns. signal-cli's
# keys and received files live in the same private state directory (mode 700, excluded from Time
# Machine). The phone number never enters tracked files: signal-cli learns it while linking.
#
#   link [NAME]   link this Mac as a Signal linked device (scan the QR code on the phone under
#                 Settings > Linked devices), then install. NAME is the device name shown on the
#                 phone (default "Hermes"). Refuses while a device is still linked; a device
#                 that Signal unlinked has its old keys moved aside first (the mirror stays)
#   install       render, load and start the agent (needs a linked account)
#   uninstall     stop and remove the agent (keys and mirror stay)
#   restart       reload the agent (after a signal-cli upgrade)
#   status        agent state and the mirror's sync status
#
# Unlinking for good: uninstall, remove the device on the phone, then delete the state directory.
# HERMES_CONFIG_DIR overrides the checkout (a task worktree); install always targets the live one.
set -euo pipefail

CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
LABEL="local.hermes.signal-access.sync"
LEGACY_LABEL="local.signal.sync"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
VENV="$CONFIG_DIR/local/signal-sync/venv"
SYNC="$CONFIG_DIR/plugins/messaging/signal-access/sync.py"
STATE="${HERMES_SIGNAL_STATE:-$HOME/.local/state/hermes-signal}"
DATA="$STATE/signal-cli"
LOG="$HOME/Library/Logs/signal-access-sync.log"
LEGACY_LOG="$HOME/Library/Logs/signal-sync.log"
PYTHON_VERSION="3.12.11"

die() { echo "error: $*" >&2; exit 1; }

CLI="$(command -v signal-cli || true)"
[ -n "$CLI" ] || die "signal-cli is not on PATH (brew install signal-cli)"

# Everything but status changes the live agent or the account: never from a task worktree.
case "${1:-}" in
  link|setup|install|uninstall|restart)
    [ "$CONFIG_DIR" = "$HOME/.config/hermes" ] || die "$1 targets the live checkout only; unset HERMES_CONFIG_DIR"
    ;;
esac

prepare_state() {
  mkdir -p "$STATE" && chmod 700 "$STATE"
  # Keys, the mirror and messages that disappeared elsewhere stay out of backups.
  tmutil addexclusion "$STATE" >/dev/null 2>&1 || echo "warning: could not exclude $STATE from Time Machine" >&2
}

setup() {
  command -v uv >/dev/null 2>&1 || die "uv not found (brew install uv)"
  if [ ! -x "$VENV/bin/python" ] || [ "$("$VENV/bin/python" --version 2>&1)" != "Python $PYTHON_VERSION" ]; then
    rm -rf "$VENV"
    mkdir -p "$(dirname "$VENV")"
    UV_NO_CONFIG=1 uv venv "$VENV" --python "$PYTHON_VERSION" --managed-python -q
  fi
  echo "sync interpreter ready: $VENV"
}

# "<number> <registered>" of the linked account from signal-cli's own files, empty when none.
account_state() {
  [ -x "$VENV/bin/python" ] || setup >/dev/null
  HERMES_SIGNAL_STATE="$STATE" "$VENV/bin/python" - "$CONFIG_DIR/plugins/messaging/signal-access/store.py" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("signal_store", sys.argv[1])
store = importlib.util.module_from_spec(spec); spec.loader.exec_module(store)
account = store.linked_account()
if account:
    print(account["number"], "no" if account.get("registered") is False else "yes")
PY
}

unload_agent() {
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  local i
  for i in $(seq 1 50); do
    launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1 || return 0
    sleep 0.2
  done
  echo "warning: $LABEL still present after bootout" >&2
}

load_agent() {
  local i
  for i in 1 2 3; do
    if launchctl bootstrap "gui/$UID" "$DEST" 2>/dev/null; then
      launchctl enable "gui/$UID/$LABEL" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  die "launchctl bootstrap failed for $DEST"
}

# The label this agent had before the launchd naming cleanup: stop and drop it so
# two copies never run, and carry its log over once.
retire_legacy() {
  launchctl bootout "gui/$UID/$LEGACY_LABEL" 2>/dev/null || true
  local i
  for i in $(seq 1 50); do
    launchctl print "gui/$UID/$LEGACY_LABEL" >/dev/null 2>&1 || break
    sleep 0.2
  done
  rm -f "$HOME/Library/LaunchAgents/$LEGACY_LABEL.plist"
  if [ -f "$LEGACY_LOG" ] && [ ! -e "$LOG" ]; then mv "$LEGACY_LOG" "$LOG"; fi
}

install_agent() {
  [ -x "$VENV/bin/python" ] || setup
  prepare_state
  local acct
  acct="$(account_state)"
  [ -n "$acct" ] || die "no linked Signal account (run: $0 link)"
  [ "${acct#* }" = "yes" ] || die "Signal unlinked this device (run: $0 link)"
  [ -f "$TMPL" ] || die "missing template: $TMPL"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|__PYTHON__|$VENV/bin/python|g" -e "s|__SYNC__|$SYNC|g" -e "s|__STATE__|$STATE|g" \
      -e "s|__HOME__|$HOME|g" -e "s|__LOG__|$LOG|g" "$TMPL" > "$tmp"
  plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "rendered plist is invalid"; }
  mkdir -p "$(dirname "$DEST")"
  mv "$tmp" "$DEST"
  retire_legacy
  unload_agent
  load_agent
  echo "loaded $LABEL; log: $LOG"
}

case "${1:-}" in
  link)
    NAME="${2:-Hermes}"
    [ -x "$VENV/bin/python" ] || setup
    prepare_state
    acct="$(account_state)"
    if [ -n "$acct" ]; then
      [ "${acct#* }" = "no" ] || die "a Signal account is still linked here; to link again: $0 uninstall,
       remove this device on the phone (Settings > Linked devices), wait for $0 status to say unlinked, then link"
      unload_agent
      retire_legacy
      stamp="$(date +%Y%m%d%H%M%S)"
      mv "$DATA/data" "$DATA/data.unlinked-$stamp"
      echo "moved the unlinked device's keys aside ($DATA/data.unlinked-$stamp)"
    fi
    unload_agent
    retire_legacy
    echo "On the phone: Signal > Settings > Linked devices > Link new device, and scan this code."
    (umask 077 && "$CLI" --data-dir "$DATA" link -n "$NAME")
    install_agent
    ;;
  setup)
    setup
    ;;
  install)
    install_agent
    ;;
  uninstall)
    unload_agent
    retire_legacy
    rm -f "$DEST"
    echo "unloaded and removed $DEST (keys and mirror kept in $STATE)"
    ;;
  restart)
    [ -f "$DEST" ] || die "not installed: $DEST"
    unload_agent
    load_agent
    echo "reloaded $LABEL"
    ;;
  status)
    echo "plist   : $DEST $([ -f "$DEST" ] && echo '(installed)' || echo '(absent)')"
    if launchctl print "gui/$UID/$LABEL" >"/tmp/.signal-access-print.$$" 2>/dev/null; then
      grep -E '^[[:space:]]+(state|pid|last exit code) = ' "/tmp/.signal-access-print.$$" \
        | head -3 | sed 's/^[[:space:]]*/  /'
    else
      echo "  agent not loaded"
    fi
    rm -f "/tmp/.signal-access-print.$$"
    acct="$(account_state || true)"
    if [ -n "$acct" ]; then
      echo "account : ${acct% *} ($([ "${acct#* }" = yes ] && echo linked || echo 'unlinked by Signal'))"
    else
      echo "account : none linked"
    fi
    if [ -f "$STATE/mirror.db" ]; then
      # Not -readonly: Apple's sqlite3 cannot open a WAL database read-only once its -shm is gone.
      /usr/bin/sqlite3 "$STATE/mirror.db" \
        "SELECT key || ': ' || COALESCE(value, '') FROM meta WHERE key IN ('status', 'error', 'last_event', 'refreshed')" \
        2>/dev/null | sed 's/^/  /' || true
      /usr/bin/sqlite3 "$STATE/mirror.db" "SELECT 'messages: ' || COUNT(*) FROM messages" 2>/dev/null \
        | sed 's/^/  /' || true
    else
      echo "  no mirror yet"
    fi
    ;;
  *)
    die "usage: $0 link [NAME] | setup | install | uninstall | restart | status"
    ;;
esac
