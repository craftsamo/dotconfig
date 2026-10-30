#!/bin/sh
# Run the Workspaces Drive mount in the foreground (the LaunchAgent
# local.hermes.workspaces-drive.mount keeps it alive): rclone nfsmount of the
# Drive folder at ~/Workspaces/.drive, then a maintenance pass at start and
# every WSD_MAINTENANCE_INTERVAL seconds that links new Groups' directories and
# sweeps AppleDouble files. Design: docs/ops/workspaces-drive.md.
#
# Exit 78 (configuration error) when setup has not run; launchd retries after
# its throttle interval, so finishing setup is enough to bring the mount up.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source=workspaces-drive-env.sh
. "$HERE/workspaces-drive-env.sh"

# One links pass, run by the maintenance loop under the links lock.
if [ "${1:-}" = links-pass ]; then
  wsd_links "${2:-}" || true
  exit 0
fi

[ -x "$SECRET" ] || { echo "workspaces-drive-run: the secret CLI is missing at $SECRET" >&2; exit 78; }
command -v rclone >/dev/null 2>&1 || { echo "workspaces-drive-run: rclone not on PATH (brew install rclone)" >&2; exit 78; }
[ -s "$WSD_CONFIG" ] || { echo "workspaces-drive-run: no rclone config at $WSD_CONFIG; run: launchd/workspaces-drive-launchctl.sh setup" >&2; exit 78; }
wsd_check_settings

mkdir -p "$WSD_MOUNT" "$WSD_CACHE"
# A mount left by a server that died: drop it before mounting again.
if wsd_mounted; then
  diskutil unmount force "$WSD_MOUNT" >/dev/null 2>&1 || umount -f "$WSD_MOUNT" 2>/dev/null || true
fi
# Anything in the mount point while nothing is mounted was written to the
# local disk by mistake; mounting over it would hide it.
if [ -n "$(ls -A "$WSD_MOUNT" 2>/dev/null)" ]; then
  echo "workspaces-drive-run: $WSD_MOUNT is not empty while unmounted; move its contents away first" >&2
  exit 78
fi

wsd_exec_rclone nfsmount "$(wsd_combine)" "$WSD_MOUNT" \
  --vfs-cache-mode full --cache-dir "$WSD_CACHE" \
  --vfs-cache-max-size "$WSD_CACHE_MAX_SIZE" --vfs-cache-max-age "$WSD_CACHE_MAX_AGE" \
  --dir-cache-time "$WSD_DIR_CACHE_TIME" --drive-skip-shortcuts \
  -o "$WSD_NFS_OPTIONS" &
RCLONE_PID=$!
MAINT_PID=
stop() {
  [ -n "$MAINT_PID" ] && kill "$MAINT_PID" 2>/dev/null || true
  kill -TERM "$RCLONE_PID" 2>/dev/null || true
  wait "$RCLONE_PID" 2>/dev/null || true
  exit 0
}
trap stop TERM INT HUP

i=0
until wsd_mounted; do
  if ! kill -0 "$RCLONE_PID" 2>/dev/null; then
    wait "$RCLONE_PID" || exit $?
    exit 1
  fi
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "workspaces-drive-run: $WSD_MOUNT did not mount within 30s" >&2
    kill -TERM "$RCLONE_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 0.5
done
echo "workspaces-drive-run: mounted $WSD_MOUNT"

(
  # The sleep runs as a child of its own so a stop ends it too, instead of
  # leaving it behind for a whole interval.
  SLEEP_PID=
  trap '[ -n "$SLEEP_PID" ] && kill "$SLEEP_PID" 2>/dev/null; exit 0' TERM
  # The first pass reports every finding; later ones print changes only. A
  # pass that finds the lock held (a migration running) waits for the next.
  mode=
  while :; do
    if wsd_mounted; then
      if wsd_with_lock 0 sh "$HERE/workspaces-drive-run.sh" links-pass $mode; then
        mode=--quiet
      fi
      wsd_sweep
    fi
    sleep "$WSD_MAINTENANCE_INTERVAL" &
    SLEEP_PID=$!
    wait "$SLEEP_PID" || true
  done
) &
MAINT_PID=$!

status=0
wait "$RCLONE_PID" || status=$?
kill "$MAINT_PID" 2>/dev/null || true
exit "$status"
