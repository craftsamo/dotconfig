#!/bin/sh
# Manage the Cloudflare Tunnel connector LaunchAgent: the way a public hostname
# reaches the gateway's loopback webhook listener (docs/ops/webhook.md). The
# tunnel itself is made and routed in the Cloudflare dashboard; this machine
# holds only its connector token, in the Keychain.
set -eu

LABEL=local.hermes.cloudflared.tunnel
CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LAUNCHER="$CONFIG_DIR/launchd/bin/hermes-cloudflared-tunnel"
RUN_SCRIPT="$CONFIG_DIR/scripts/cloudflared-run.sh"
SECRET="${SECRET_CLI:-$HOME/.config/bin/secret}"
METRICS_PORT="${CLOUDFLARED_METRICS_PORT:-20241}"
READY_URL="http://127.0.0.1:$METRICS_PORT/ready"
STARTUP_ATTEMPTS="${CLOUDFLARED_STARTUP_ATTEMPTS:-20}"
STARTUP_SLEEP_SECONDS="${CLOUDFLARED_STARTUP_SLEEP_SECONDS:-3}"

ACTION="${1:-install}"

die() { echo "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found"; }

require_runtime() {
  [ -f "$TMPL" ] || die "template not found: $TMPL"
  [ -x "$LAUNCHER" ] || die "launcher not executable: $LAUNCHER"
  [ -f "$RUN_SCRIPT" ] || die "run script not found: $RUN_SCRIPT"
  [ -x "$SECRET" ] || die "the secret CLI is missing at $SECRET"
  need cloudflared
  need plutil
  need curl
  case "$METRICS_PORT" in
    ''|*[!0-9]*) die "CLOUDFLARED_METRICS_PORT must be numeric: $METRICS_PORT" ;;
  esac
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
}

# The token is checked for presence only (`show` prints metadata, never the
# value); the run script reads it at every start.
require_token() {
  "$SECRET" show CLOUDFLARE_TUNNEL_TOKEN -p hermes --scope cloudflare-access >/dev/null 2>&1 || die \
    "no CLOUDFLARE_TUNNEL_TOKEN in the Keychain. In the Cloudflare dashboard (Zero Trust → Networks → Tunnels)
make a tunnel, copy its connector token, and store it with:
  secret set CLOUDFLARE_TUNNEL_TOKEN -p hermes --scope cloudflare-access --no-stage -D TOKEN"
}

render_plist() {
  HOME_ESCAPED=$(printf '%s\n' "$HOME" | sed 's/[&|]/\\&/g')
  sed -e "s|__HOME__|$HOME_ESCAPED|g" -e "s|__METRICS_PORT__|$METRICS_PORT|g" "$TMPL" > "$DEST.tmp"
  plutil -lint "$DEST.tmp" >/dev/null
  mv -f "$DEST.tmp" "$DEST"
}

unload_agent() {
  launchctl unload "$DEST" 2>/dev/null || true
}

load_agent() {
  launchctl load -w "$DEST"
}

wait_ready() {
  ATTEMPT=0
  while [ "$ATTEMPT" -lt "$STARTUP_ATTEMPTS" ]; do
    if curl -fs -m 3 -o /dev/null "$READY_URL"; then
      return 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep "$STARTUP_SLEEP_SECONDS"
  done
  echo "cloudflared did not report ready on $READY_URL; check ~/Library/Logs/cloudflared-tunnel.log" >&2
  return 1
}

case "$ACTION" in
  install)
    require_runtime
    require_token
    render_plist
    unload_agent
    load_agent
    wait_ready
    echo "loaded $LABEL ($DEST); the tunnel's hostnames are routed in the Cloudflare dashboard"
    ;;
  restart)
    require_runtime
    [ -f "$DEST" ] || die "$LABEL is not installed; run install"
    require_token
    unload_agent
    load_agent
    wait_ready
    echo "restarted $LABEL"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    echo "--- connector ---"
    if curl -fs -m 3 "$READY_URL"; then
      echo
    else
      echo "connector not ready on 127.0.0.1:$METRICS_PORT"
    fi
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    echo "unloaded + removed $LABEL (the Keychain token is retained)"
    ;;
  *)
    echo "usage: $0 install | restart | status | uninstall" >&2
    exit 1
    ;;
esac
