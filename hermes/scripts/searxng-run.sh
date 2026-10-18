#!/bin/sh
# Run the SearXNG container in the foreground for launchd
# (local.hermes.searxng.engine). The image is read from the hash-locked pin and
# the rendered settings directory is mounted in; the port is published on the
# loopback interface only.
#
# Exits non-zero (and lets launchd retry after its ThrottleInterval) when the
# Docker daemon is not reachable yet, e.g. while Docker Desktop is starting.
set -eu

CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
RUNTIME_DIR="${SEARXNG_RUNTIME_DIR:-$CONFIG_DIR/local/searxng}"
LOCK="$CONFIG_DIR/engines/searxng/image.lock"
NAME="${SEARXNG_CONTAINER:-hermes-searxng}"
PORT="${SEARXNG_PORT:-10104}"

IMAGE=$(sed -n 's/^image=//p' "$LOCK" | head -n 1)
[ -n "$IMAGE" ] || { echo "image pin missing in $LOCK" >&2; exit 1; }
[ -f "$RUNTIME_DIR/etc/settings.yml" ] || {
  echo "settings not rendered: run launchd/searxng-launchctl.sh install" >&2
  exit 1
}
case "$PORT" in
  ''|*[!0-9]*) echo "SEARXNG_PORT must be numeric: $PORT" >&2; exit 1 ;;
esac

docker info >/dev/null 2>&1 || { echo "docker daemon not reachable; launchd will retry" >&2; exit 1; }
# A container left behind by an unclean stop blocks the name.
docker rm -f "$NAME" >/dev/null 2>&1 || true

exec docker run --rm --name "$NAME" \
  --publish "127.0.0.1:$PORT:8080" \
  --volume "$RUNTIME_DIR/etc:/etc/searxng" \
  --env "SEARXNG_BASE_URL=http://127.0.0.1:$PORT/" \
  "$IMAGE"
