#!/bin/sh
# Manage the local SearXNG metasearch LaunchAgent (the keyless floor under the
# web_search cascade). Docker Desktop must be installed; the container image is
# pinned by digest in engines/searxng/image.lock.
set -eu

LABEL=local.hermes.searxng.engine
CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LAUNCHER="$CONFIG_DIR/launchd/bin/hermes-searxng-engine"
RUN_SCRIPT="$CONFIG_DIR/scripts/searxng-run.sh"
SETTINGS_TMPL="$CONFIG_DIR/engines/searxng/settings.yml.tmpl"
LOCK="$CONFIG_DIR/engines/searxng/image.lock"
# Engine runtime root: machine-local, outside the repository (HERMES_LOCAL overrides).
HERMES_LOCAL="${HERMES_LOCAL:-$HOME/.hermes/local}"
RUNTIME_DIR="${SEARXNG_RUNTIME_DIR:-$HERMES_LOCAL/searxng}"
SETTINGS="$RUNTIME_DIR/etc/settings.yml"
PORT="${SEARXNG_PORT:-10104}"
HEALTH_URL="http://127.0.0.1:$PORT/healthz"
STARTUP_ATTEMPTS="${SEARXNG_STARTUP_ATTEMPTS:-40}"
STARTUP_SLEEP_SECONDS="${SEARXNG_STARTUP_SLEEP_SECONDS:-3}"

ACTION="${1:-install}"

die() { echo "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found"; }

require_runtime() {
  [ -f "$TMPL" ] || die "template not found: $TMPL"
  [ -f "$SETTINGS_TMPL" ] || die "settings template not found: $SETTINGS_TMPL"
  [ -f "$LOCK" ] || die "image pin not found: $LOCK"
  [ -x "$LAUNCHER" ] || die "launcher not executable: $LAUNCHER"
  [ -f "$RUN_SCRIPT" ] || die "run script not found: $RUN_SCRIPT"
  need docker
  need plutil
  need curl
  case "$PORT" in
    ''|*[!0-9]*) die "SEARXNG_PORT must be numeric: $PORT" ;;
  esac
  mkdir -p "$RUNTIME_DIR/etc" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
}

# The secret key only signs SearXNG's own cookies. It is generated once per
# host into the ignored local/ tree and reused by later installs, so a
# re-render never invalidates anything.
render_settings() {
  SECRET_FILE="$RUNTIME_DIR/secret_key"
  if [ ! -s "$SECRET_FILE" ]; then
    umask 077
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SECRET_FILE"
    umask 022
  fi
  SECRET=$(cat "$SECRET_FILE")
  SECRET_ESCAPED=$(printf '%s\n' "$SECRET" | sed 's/[&|]/\\&/g')
  sed -e "s|__SECRET_KEY__|$SECRET_ESCAPED|g" "$SETTINGS_TMPL" > "$SETTINGS.tmp"
  mv -f "$SETTINGS.tmp" "$SETTINGS"
}

render_plist() {
  HOME_ESCAPED=$(printf '%s\n' "$HOME" | sed 's/[&|]/\\&/g')
  sed -e "s|__HOME__|$HOME_ESCAPED|g" -e "s|__PORT__|$PORT|g" "$TMPL" > "$DEST.tmp"
  plutil -lint "$DEST.tmp" >/dev/null
  mv -f "$DEST.tmp" "$DEST"
}

unload_agent() {
  launchctl unload "$DEST" 2>/dev/null || true
}

load_agent() {
  launchctl load -w "$DEST"
}

wait_healthy() {
  ATTEMPT=0
  while [ "$ATTEMPT" -lt "$STARTUP_ATTEMPTS" ]; do
    if curl -fs -m 3 -o /dev/null "$HEALTH_URL"; then
      return 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep "$STARTUP_SLEEP_SECONDS"
  done
  echo "SearXNG did not answer on $HEALTH_URL; check ~/Library/Logs/searxng-engine.log (is Docker Desktop running?)" >&2
  return 1
}

# The image is pulled ahead of the first load so the health wait measures the
# container start, not the download; the digest in the pin is what docker verifies.
pull_image() {
  IMAGE=$(sed -n 's/^image=//p' "$LOCK" | head -n 1)
  [ -n "$IMAGE" ] || die "image pin missing in $LOCK"
  docker info >/dev/null 2>&1 || die "docker daemon not reachable; start Docker Desktop first"
  docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE"
}

case "$ACTION" in
  install)
    require_runtime
    render_settings
    pull_image
    render_plist
    unload_agent
    load_agent
    wait_healthy
    echo "loaded $LABEL ($DEST) on 127.0.0.1:$PORT"
    ;;
  restart)
    require_runtime
    [ -f "$DEST" ] || die "$LABEL is not installed; run install"
    render_settings
    unload_agent
    load_agent
    wait_healthy
    echo "restarted $LABEL"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    echo "--- engine health ---"
    if curl -fs -m 3 -o /dev/null "$HEALTH_URL"; then
      echo "SearXNG ready on 127.0.0.1:$PORT"
    else
      echo "engine not ready on :$PORT"
    fi
    docker ps --filter "name=^hermes-searxng$" --format '{{.Names}} {{.Status}} {{.Image}}' 2>/dev/null || true
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    docker rm -f hermes-searxng >/dev/null 2>&1 || true
    echo "unloaded + removed $LABEL (settings and image retained)"
    ;;
  *)
    echo "usage: $0 install | restart | status | uninstall" >&2
    exit 1
    ;;
esac
