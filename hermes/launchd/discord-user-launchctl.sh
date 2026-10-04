#!/usr/bin/env bash
# Engine venv and sync LaunchAgent for discord-access (the user's own Discord account).
#
# The plugin reads the local mirror (~/.local/state/hermes-discord) that this agent keeps current,
# and runs plugins/discord-access/engine.py on the venv built here for anything that talks to
# Discord. The user token lives only in the Keychain (secret project discord-user); nothing
# here prints or stores it.
#
#   setup       build the engine venv from engines/discord-user/requirements.lock (hash-locked)
#   install     setup if needed, render and load the agent: one sync run every 5 minutes
#   uninstall   stop and remove the agent (the venv, mirror and sync list stay)
#   run         one sync run now, in this terminal (prints the run summary)
#   status      agent state, token presence (no value) and the last sync summary
#
# The token: `secret set DISCORD_USER_TOKEN -p discord-user` (paste it; never on the command line).
# HERMES_CONFIG_DIR overrides the checkout (a task worktree); install always targets the live one.
set -euo pipefail

CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
LABEL="local.discord-user.sync"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOCK="$CONFIG_DIR/engines/discord-user/requirements.lock"
VENV="$CONFIG_DIR/local/discord-user/venv"
ENGINE="$CONFIG_DIR/plugins/discord-access/engine.py"
STATE="${HERMES_DISCORD_STATE:-$HOME/.local/state/hermes-discord}"
LOG="$HOME/Library/Logs/discord-user-sync.log"
SECRET="$HOME/.config/bin/secret"
PYTHON_VERSION="3.12.11"

die() { echo "error: $*" >&2; exit 1; }

has_token() {
  "$SECRET" show DISCORD_USER_TOKEN -p discord-user --shared >/dev/null 2>&1
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
  "$VENV/bin/python" -c 'import curl_cffi' || die "curl_cffi does not import in $VENV"
  echo "engine venv ready: $VENV"
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

install_agent() {
  [ "$CONFIG_DIR" = "$HOME/.config/hermes" ] || die "install targets the live checkout only; unset HERMES_CONFIG_DIR"
  has_token || die "no token yet: secret set DISCORD_USER_TOKEN -p discord-user"
  [ -x "$VENV/bin/python" ] || setup
  [ -f "$TMPL" ] || die "missing template: $TMPL"
  mkdir -p "$STATE" && chmod 700 "$STATE"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|__PYTHON__|$VENV/bin/python|g" -e "s|__ENGINE__|$ENGINE|g" -e "s|__STATE__|$STATE|g" \
      -e "s|__HOME__|$HOME|g" -e "s|__LOG__|$LOG|g" "$TMPL" > "$tmp"
  plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "rendered plist is invalid"; }
  mkdir -p "$(dirname "$DEST")"
  mv "$tmp" "$DEST"
  unload_agent
  launchctl bootstrap "gui/$UID" "$DEST" || die "launchctl bootstrap failed for $DEST"
  launchctl enable "gui/$UID/$LABEL" 2>/dev/null || true
  echo "loaded $LABEL (a sync run every 5 minutes); log: $LOG"
}

last_sync() {
  [ -f "$STATE/mirror.db" ] || { echo "  no mirror yet"; return; }
  # Not -readonly: Apple's sqlite3 cannot open a WAL database read-only once its -shm is gone.
  /usr/bin/sqlite3 "$STATE/mirror.db" "SELECT value FROM meta WHERE key = 'last_sync'" 2>/dev/null \
    | sed 's/^/  last sync: /' || true
  /usr/bin/sqlite3 "$STATE/mirror.db" "SELECT value FROM meta WHERE key = 'auth'" 2>/dev/null \
    | sed 's/^/  token check: /' || true
}

case "${1:-}" in
  setup)
    setup
    ;;
  install)
    install_agent
    ;;
  uninstall)
    unload_agent
    rm -f "$DEST"
    echo "unloaded and removed $DEST (venv, mirror and sync list kept)"
    ;;
  run)
    [ -x "$VENV/bin/python" ] || die "no engine venv: $0 setup"
    mkdir -p "$STATE" && chmod 700 "$STATE"
    (cd "$STATE" && HERMES_DISCORD_STATE="$STATE" "$VENV/bin/python" "$ENGINE" sync </dev/null)
    ;;
  status)
    echo "venv    : $VENV $([ -x "$VENV/bin/python" ] && echo '(ready)' || echo '(missing: setup)')"
    echo "token   : $(has_token && echo 'in Keychain' || echo 'missing: secret set DISCORD_USER_TOKEN -p discord-user')"
    echo "plist   : $DEST $([ -f "$DEST" ] && echo '(installed)' || echo '(absent)')"
    if launchctl print "gui/$UID/$LABEL" >"/tmp/.discord-user-print.$$" 2>/dev/null; then
      grep -E '^[[:space:]]+(state|pid|last exit code|run interval) = ' "/tmp/.discord-user-print.$$" \
        | sed 's/^[[:space:]]*/  /'
    else
      echo "  agent not loaded"
    fi
    rm -f "/tmp/.discord-user-print.$$"
    last_sync
    ;;
  *)
    die "usage: $0 setup | install | uninstall | run | status"
    ;;
esac
