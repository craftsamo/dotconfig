#!/usr/bin/env bash
# Engine venv, login and sync LaunchAgent for telegram-access (the user's own Telegram account).
#
# The telegram_account tool reads the local mirror (~/.local/state/hermes-telegram/mirror.db)
# that this agent keeps current, and asks the agent (plugins/telegram-access/sync.py on the venv
# built here, the only process connected to Telegram) for live reads, media and sends. The
# account's credentials live only in the Keychain (project hermes, scope telegram-access, which no
# Hermes profile receives); nothing here prints or stores them. The state directory is private
# (mode 700) and excluded from Time Machine.
#
#   setup       build the engine venv from engines/telegram-access/requirements.lock (hash-locked)
#   login       stop the agent, log in interactively (phone number, the code Telegram sends to
#               the app, the two-step verification password), store the session, then install.
#               Refuses while a session is still logged in (logout first)
#   logout      stop the agent, end the session at Telegram and forget it (the mirror stays)
#   install     setup if needed, render, load and start the agent (needs a session)
#   uninstall   stop and remove the agent (session, mirror and sync list stay)
#   restart     reload the agent (after a code or venv change)
#   status      venv, credentials (presence only), agent state and the mirror's sync status
#
# Before login, once: create an app at https://my.telegram.org (API development tools) and store
#   secret set TELEGRAM_API_ID   -p hermes --scope telegram-access
#   secret set TELEGRAM_API_HASH -p hermes --scope telegram-access
# (paste each when prompted; never on the command line).
# HERMES_CONFIG_DIR overrides the checkout (a task worktree); everything but setup and status
# targets the live checkout only.
set -euo pipefail

CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
LABEL="local.hermes.telegram-access.sync"
LEGACY_LABEL="local.telegram-access.sync"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOCK="$CONFIG_DIR/engines/telegram-access/requirements.lock"
VENV="$CONFIG_DIR/local/telegram-access/venv"
SYNC="$CONFIG_DIR/plugins/telegram-access/sync.py"
STATE="${HERMES_TELEGRAM_STATE:-$HOME/.local/state/hermes-telegram}"
LOG="$HOME/Library/Logs/telegram-access-sync.log"
LEGACY_LOG="$LOG"
SECRET="$HOME/.config/bin/secret"
PYTHON_VERSION="3.12.11"

die() { echo "error: $*" >&2; exit 1; }

# Everything that changes the live agent or the account: never from a task worktree.
case "${1:-}" in
  login|logout|install|uninstall|restart)
    [ "$CONFIG_DIR" = "$HOME/.config/hermes" ] || die "$1 targets the live checkout only; unset HERMES_CONFIG_DIR"
    ;;
esac

has() {
  "$SECRET" show "$1" -p hermes --scope telegram-access >/dev/null 2>&1
}

prepare_state() {
  mkdir -p "$STATE" && chmod 700 "$STATE"
  # The entity cache, the mirror and messages that disappeared elsewhere stay out of backups.
  tmutil addexclusion "$STATE" >/dev/null 2>&1 || echo "warning: could not exclude $STATE from Time Machine" >&2
}

setup() {
  command -v uv >/dev/null 2>&1 || die "uv not found (brew install uv)"
  [ -f "$LOCK" ] || die "missing lock: $LOCK"
  if [ ! -x "$VENV/bin/python" ] || [ "$("$VENV/bin/python" --version 2>&1)" != "Python $PYTHON_VERSION" ]; then
    rm -rf "$VENV"
    mkdir -p "$(dirname "$VENV")"
    UV_NO_CONFIG=1 uv venv "$VENV" --python "$PYTHON_VERSION" --managed-python -q
  fi
  UV_NO_CONFIG=1 uv pip sync --python "$VENV/bin/python" --require-hashes --strict -q "$LOCK"
  "$VENV/bin/python" -c 'import telethon' || die "telethon does not import in $VENV"
  echo "engine venv ready: $VENV"
}

need_api() {
  has TELEGRAM_API_ID || die "no api_id yet: secret set TELEGRAM_API_ID -p hermes --scope telegram-access"
  has TELEGRAM_API_HASH || die "no api_hash yet: secret set TELEGRAM_API_HASH -p hermes --scope telegram-access"
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
  need_api
  has TELEGRAM_USER_SESSION || die "not logged in yet: $0 login"
  [ -x "$VENV/bin/python" ] || setup
  prepare_state
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

run_sync() {
  (cd "$STATE" && HERMES_TELEGRAM_STATE="$STATE" "$VENV/bin/python" "$SYNC" "$@")
}

case "${1:-}" in
  setup)
    setup
    ;;
  login)
    need_api
    [ -x "$VENV/bin/python" ] || setup
    prepare_state
    # One connection per session: the agent must not run while a login or check connects.
    unload_agent
    retire_legacy
    run_sync login
    install_agent
    ;;
  logout)
    [ -x "$VENV/bin/python" ] || setup
    prepare_state
    unload_agent
    retire_legacy
    run_sync logout
    rm -f "$DEST"
    echo "removed $DEST"
    ;;
  install)
    install_agent
    ;;
  uninstall)
    unload_agent
    retire_legacy
    rm -f "$DEST"
    echo "unloaded and removed $DEST (session, mirror and sync list kept)"
    ;;
  restart)
    [ -f "$DEST" ] || die "not installed: $DEST"
    unload_agent
    load_agent
    echo "reloaded $LABEL"
    ;;
  status)
    echo "venv    : $VENV $([ -x "$VENV/bin/python" ] && echo '(ready)' || echo '(missing: setup)')"
    echo "api     : $(has TELEGRAM_API_ID && has TELEGRAM_API_HASH && echo 'in Keychain' || echo 'missing (see the header of this script)')"
    echo "session : $(has TELEGRAM_USER_SESSION && echo 'in Keychain' || echo "missing: $0 login")"
    echo "plist   : $DEST $([ -f "$DEST" ] && echo '(installed)' || echo '(absent)')"
    if launchctl print "gui/$UID/$LABEL" >"/tmp/.telegram-access-print.$$" 2>/dev/null; then
      grep -E '^[[:space:]]+(state|pid|last exit code) = ' "/tmp/.telegram-access-print.$$" \
        | head -3 | sed 's/^[[:space:]]*/  /'
    else
      echo "  agent not loaded"
    fi
    rm -f "/tmp/.telegram-access-print.$$"
    if [ -f "$STATE/mirror.db" ]; then
      # Not -readonly: Apple's sqlite3 cannot open a WAL database read-only once its -shm is gone.
      /usr/bin/sqlite3 "$STATE/mirror.db" \
        "SELECT key || ': ' || COALESCE(value, '') FROM meta WHERE key IN ('status', 'error', 'me_name', 'refreshed')" \
        2>/dev/null | sed 's/^/  /' || true
      /usr/bin/sqlite3 "$STATE/mirror.db" "SELECT 'chats: ' || COUNT(*) FROM chats; SELECT 'messages: ' || COUNT(*) FROM messages" \
        2>/dev/null | sed 's/^/  /' || true
    else
      echo "  no mirror yet"
    fi
    ;;
  *)
    die "usage: $0 setup | login | logout | install | uninstall | restart | status"
    ;;
esac
