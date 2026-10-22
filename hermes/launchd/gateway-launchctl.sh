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
# and `hermes update` use): it lets running turns finish (up to
# agent.restart_after_turn_timeout), drains what is left, marks it to resume,
# exits 75, and KeepAlive relaunches it. The launcher waits that whole window,
# reporting what the gateway is waiting on, and never forces the stop: unloading
# the job or `launchctl kickstart -k` delivers SIGTERM, which Hermes treats as
# an unplanned kill — turns are not resumed and replies still being sent are
# left for the next boot.
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
# How long a planned restart can take: agent.restart_after_turn_timeout (the
# gateway lets in-flight turns finish before it stops; the runtime default is
# 1800 s — raise this with it) plus agent.restart_drain_timeout (50 s: the
# per-user launchd domain clamps ExitTimeOut to 60 s and Hermes keeps a 10 s
# cleanup reserve under it), the 30 s ThrottleInterval and margin. Overridable
# for a quick check (RESTART_WAIT=60 … restart); the gateway's own cap still
# applies, and a wait shorter than it ends in the exit-2 report below.
RESTART_WAIT="${RESTART_WAIT:-1950}"
GATEWAY_LOG="${HERMES_HOME:-$HOME/.hermes}/logs/gateway.log"

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

# The gateway's latest word on what this restart waits for (its "Restart deferred"
# line names the active turns): only lines logged since the signal was sent, so an
# earlier restart's wait is never shown as this one's.
restart_progress() {
  [ -r "$GATEWAY_LOG" ] || return 0
  tail -n 2000 "$GATEWAY_LOG" | awk -v since="$1" 'substr($1 " " $2, 1, 19) >= since && /Restart deferred: waiting on/' \
    | tail -n 1 | sed 's/^.*Restart deferred: //' | cut -c1-200
}

# Returns 1 without touching anything when no gateway is running. Exits 2 when
# the gateway was asked to restart but has not relaunched within RESTART_WAIT:
# it is still the old process, finishing its turns, and nothing here may force
# it (install must not fall through to a reload, which would SIGTERM it).
graceful_restart() {
  old=$(gateway_pid)
  case "$old" in '' | -) return 1 ;; esac
  echo "restarting $LABEL (pid $old): letting active turns finish, then draining (up to ${RESTART_WAIT}s)..."
  since=$(date '+%Y-%m-%d %H:%M:%S')
  kill -USR1 "$old" || return 1
  waited=0
  while [ "$waited" -lt "$RESTART_WAIT" ]; do
    sleep 2
    waited=$((waited + 2))
    new=$(gateway_pid)
    case "$new" in '' | - | "$old") ;; *)
      echo "restarted $LABEL (pid $new) after ${waited}s"
      return 0 ;;
    esac
    if [ $((waited % 30)) -eq 0 ]; then
      progress=$(restart_progress "$since")
      echo "  ${waited}s: ${progress:-waiting for the gateway to stop}"
    fi
  done
  echo "WARN: $LABEL (pid $old) has not relaunched after ${RESTART_WAIT}s. This is not a failure:" >&2
  echo "      the gateway is still running, the restart is still pending inside it, and it will stop" >&2
  echo "      and relaunch on its own once its turns finish or its own cap passes. Leave it, or watch" >&2
  echo "      $GATEWAY_LOG. Do not kill it and do not run install: that drops the turns it is finishing." >&2
  exit 2
}

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents"
    remove_legacy
    rendered=$(mktemp)
    trap 'rm -f "$rendered"' EXIT
    sed "s|__HOME__|$HOME|g" "$TMPL" > "$rendered"
    chmod 644 "$rendered"
    if cmp -s "$rendered" "$DEST" && graceful_restart; then
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
