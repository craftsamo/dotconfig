#!/bin/sh
# Install / restart / uninstall the Hermes multiplex gateway LaunchAgent on THIS host.
#
# Run on the GATEWAY HOST ONLY — one bot token = one live connection per bot,
# so don't load this where another machine already runs these gateways.
#
# `install` renders the template (substituting __HOME__ -> $HOME, since launchd
# can't expand ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist
# is host-local and never committed; only the template lives in git. When the
# job is already loaded and the rendered plist is unchanged, install restarts
# the gateway gracefully instead of reloading it.
#
# `restart` sends SIGUSR1, the gateway's own planned restart (what `/restart`
# and `hermes update` use): it drains running turns, marks them to resume, exits
# 75, and KeepAlive relaunches it. Unloading the job instead delivers SIGTERM,
# which Hermes treats as an unplanned kill: turns are not resumed and replies
# still being sent are left for the next boot.
#
# Older agents (ai.hermes.keychain-multiplex, local.hermes.gateway.multiplex,
# local.hermes.gateway.assistant)
# are unloaded and removed on install so two pollers never run at once
# (Telegram getUpdates 409).
set -e

LABEL=ai.hermes.multiplex
LEGACY_LABELS="ai.hermes.keychain-multiplex local.hermes.gateway.multiplex local.hermes.gateway.assistant"
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
# Covers agent.restart_drain_timeout (180 s) plus the 30 s ThrottleInterval.
RESTART_WAIT=300

remove_legacy() {
  for legacy in $LEGACY_LABELS; do
    legacy_dest="$HOME/Library/LaunchAgents/$legacy.plist"
    if [ -f "$legacy_dest" ]; then
      launchctl unload -w "$legacy_dest" 2>/dev/null || true
      rm -f "$legacy_dest"
      echo "unloaded + removed legacy $legacy"
    fi
  done
}

# PID of the running gateway; "-" when loaded but not running, empty when not loaded.
gateway_pid() {
  launchctl list | awk -v label="$LABEL" '$3 == label { print $1 }'
}

# Returns 1 without touching anything when no gateway is running.
graceful_restart() {
  old=$(gateway_pid)
  case "$old" in '' | -) return 1 ;; esac
  echo "restarting $LABEL (pid $old): draining active turns (up to ${RESTART_WAIT}s)..."
  kill -USR1 "$old" || return 1
  waited=0
  while [ "$waited" -lt "$RESTART_WAIT" ]; do
    sleep 2
    waited=$((waited + 2))
    new=$(gateway_pid)
    case "$new" in '' | - | "$old") continue ;; esac
    echo "restarted $LABEL (pid $new)"
    return 0
  done
  echo "WARN: $LABEL did not relaunch within ${RESTART_WAIT}s; forcing a restart" >&2
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
  echo "restarted $LABEL (forced)"
}

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents"
    remove_legacy
    rendered=$(mktemp)
    sed "s|__HOME__|$HOME|g" "$TMPL" > "$rendered"
    chmod 644 "$rendered"
    if cmp -s "$rendered" "$DEST" && graceful_restart; then
      rm -f "$rendered"
      exit 0
    fi
    mv "$rendered" "$DEST"
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    echo "loaded $LABEL ($DEST)"
    ;;
  restart)
    graceful_restart || { echo "$LABEL is not running; use install" >&2; exit 1; }
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    remove_legacy
    echo "unloaded + removed $LABEL"
    ;;
  status)
    launchctl list | grep -e "$LABEL" -e ai.hermes.keychain-multiplex -e local.hermes.gateway || echo "$LABEL not loaded"
    ;;
  *)
    echo "usage: $0 [install|restart|uninstall|status]" >&2
    exit 1
    ;;
esac
