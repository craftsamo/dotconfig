#!/bin/sh
# Manage the Workspaces Drive mount: Group directories (assets/ by default)
# live in Google Drive and are reached through links into an rclone nfsmount
# at ~/Workspaces/.drive, so nothing of them stays on the local disk.
# Design and settings: docs/ops/workspaces-drive.md.
#
#   setup      once: Keychain items, the encrypted rclone config, the Google
#              login (opens a browser) and the Drive folders
#   install    render and load the LaunchAgent, wait for the mount
#   restart    reload the LaunchAgent
#   status     agent, mount, cache and what links would change
#   links      create missing Group links now (the agent also does it)
#   migrate T/G  move a Group's local directories to Drive and link them
#   uninstall  unload the agent and unmount (Drive data and config kept)
set -eu

LABEL=local.hermes.workspaces-drive.mount
CONFIG_DIR="${HERMES_CONFIG_DIR:-$HOME/.config/hermes}"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LAUNCHER="$CONFIG_DIR/launchd/bin/hermes-workspaces-drive-mount"
RUN_SCRIPT="$CONFIG_DIR/scripts/workspaces-drive-run.sh"
ENV_SCRIPT="$CONFIG_DIR/scripts/workspaces-drive-env.sh"
MOUNT_WAIT="${WSD_MOUNT_WAIT:-60}"
# 10 s steps: three times the mount's directory cache time (2 min).
MIGRATE_WAIT_STEPS="${WSD_MIGRATE_WAIT_STEPS:-36}"

[ -f "$ENV_SCRIPT" ] || { echo "settings script not found: $ENV_SCRIPT" >&2; exit 1; }
# shellcheck source=../scripts/workspaces-drive-env.sh
. "$ENV_SCRIPT"

ACTION="${1:-status}"

die() { echo "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found${2:+ ($2)}"; }

require_tools() {
  [ -x "$SECRET" ] || die "the secret CLI is missing at $SECRET"
  need rclone "brew install rclone"
  wsd_check_settings
}

has_item() {
  "$SECRET" show "$1" -p "$WSD_SECRET_PROJECT" --scope "$WSD_SECRET_SCOPE" --no-stage >/dev/null 2>&1
}

get_item() {
  "$SECRET" get "$1" -p "$WSD_SECRET_PROJECT" --scope "$WSD_SECRET_SCOPE" --no-stage
}

# A random value stored once, through stdin, kept out of `secret env`.
ensure_random_item() {
  has_item "$1" && return 0
  head -c 32 /dev/urandom | base64 | tr -d '\n=+/' |
    "$SECRET" set "$1" -p "$WSD_SECRET_PROJECT" --scope "$WSD_SECRET_SCOPE" --no-stage --no-env --new --stdin -j "$2" >/dev/null
  echo "  stored $1 in the Keychain ($WSD_SECRET_PROJECT/$WSD_SECRET_SCOPE)"
}

has_remote() {
  wsd_rclone listremotes 2>/dev/null | grep -qx "$1:"
}

json_string() {
  printf '"%s"' "$(printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
}

# Create a remote from the JSON parameters on stdin. They go through a
# short-lived `rclone rcd` on a unix socket in the private state directory, so
# keys and client secrets never appear on any command line (printf is a shell
# builtin; curl reads the body from stdin).
rc_create() {
  name=$1 type=$2
  need curl
  sock="$WSD_DIR/setup-rc.sock"
  out="$WSD_DIR/setup-rc.out"
  rm -f "$sock" "$out"
  rcd=
  # The daemon holds the decrypted config and answers anyone who reaches the
  # socket: it is stopped on every way out of here, a signal included (as a
  # background job it would ignore the terminal's Ctrl-C).
  stop_rcd() {
    [ -n "$rcd" ] && { kill "$rcd" 2>/dev/null || true; wait "$rcd" 2>/dev/null || true; }
    rcd=
    rm -f "$sock" "$out"
  }
  trap stop_rcd EXIT
  trap 'stop_rcd; exit 130' INT TERM HUP
  wsd_exec_rclone rcd --rc-addr "unix://$sock" --rc-no-auth >/dev/null 2>&1 &
  rcd=$!
  i=0
  while [ ! -S "$sock" ] && [ "$i" -lt 50 ]; do i=$((i + 1)); sleep 0.2; done
  [ -S "$sock" ] || die "rclone rcd did not open $sock (a unix socket path must stay under 104 bytes)"
  params=$(cat)
  rc=0
  printf '{"name":%s,"type":%s,"parameters":%s,"opt":{"obscure":true,"nonInteractive":true}}' \
      "$(json_string "$name")" "$(json_string "$type")" "$params" |
    curl -sS --fail --max-time 60 --unix-socket "$sock" -H 'Content-Type: application/json' \
      --data-binary @- http://localhost/config/create > "$out" || rc=$?
  if [ "$rc" -ne 0 ] || ! grep -q '"Error": ""' "$out"; then
    cat "$out" >&2 2>/dev/null || true
    die "could not create the rclone remote $name"
  fi
  stop_rcd
  trap - EXIT INT TERM HUP
}

setup() {
  require_tools
  mkdir -p "$WSD_DIR"
  chmod 700 "$WSD_DIR"
  ensure_random_item "$WSD_CONFIG_PASS_ITEM" "rclone config password for the Workspaces Drive mount"
  if [ ! -s "$WSD_CONFIG" ]; then
    : > "$WSD_CONFIG"
    chmod 600 "$WSD_CONFIG"
    wsd_rclone config encryption set >/dev/null
    echo "  created the encrypted rclone config $WSD_CONFIG"
  fi
  if ! has_remote "$WSD_DRIVE_REMOTE"; then
    client=
    # Your own OAuth client avoids rclone's shared, rate-limited one.
    if has_item WORKSPACES_DRIVE_CLIENT_ID && has_item WORKSPACES_DRIVE_CLIENT_SECRET; then
      client=",\"client_id\":$(json_string "$(get_item WORKSPACES_DRIVE_CLIENT_ID)"),\"client_secret\":$(json_string "$(get_item WORKSPACES_DRIVE_CLIENT_SECRET)")"
    fi
    printf '{"scope":%s%s}' "$(json_string "$WSD_DRIVE_SCOPE")" "$client" | rc_create "$WSD_DRIVE_REMOTE" drive
  fi
  if ! wsd_rclone about "$WSD_DRIVE_REMOTE:" >/dev/null 2>&1; then
    echo "  Google sign-in for $WSD_DRIVE_REMOTE (scope $WSD_DRIVE_SCOPE): answer y to use the browser,"
    echo "  then n when asked about a shared drive"
    wsd_rclone config reconnect "$WSD_DRIVE_REMOTE:"
  fi
  if ! has_remote "$WSD_CRYPT_REMOTE"; then
    ensure_random_item WORKSPACES_DRIVE_CRYPT_PASSWORD "rclone crypt password of the Workspaces Drive mount"
    ensure_random_item WORKSPACES_DRIVE_CRYPT_SALT "rclone crypt salt of the Workspaces Drive mount"
    printf '{"remote":%s,"filename_encryption":"standard","directory_name_encryption":"false","password":%s,"password2":%s}' \
      "$(json_string "$WSD_DRIVE_REMOTE:$WSD_DRIVE_PATH")" \
      "$(json_string "$(get_item WORKSPACES_DRIVE_CRYPT_PASSWORD)")" \
      "$(json_string "$(get_item WORKSPACES_DRIVE_CRYPT_SALT)")" | rc_create "$WSD_CRYPT_REMOTE" crypt
    echo "  created $WSD_CRYPT_REMOTE; keep WORKSPACES_DRIVE_CRYPT_PASSWORD and _SALT somewhere off this Mac too:"
    echo "  without them the encrypted trees cannot be read again"
  fi
  for spec in $WSD_TREES; do
    wsd_rclone mkdir "$(wsd_remote "${spec%%=*}")"
  done
  echo "setup done: $WSD_DRIVE_PATH/ on Drive holds $(echo "$WSD_TREES" | tr ' ' ',')"
}

require_setup() {
  [ -s "$WSD_CONFIG" ] || die "no rclone config at $WSD_CONFIG; run: $0 setup"
  has_item "$WSD_CONFIG_PASS_ITEM" || die "no $WSD_CONFIG_PASS_ITEM in the Keychain; run: $0 setup"
}

render_plist() {
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  HOME_ESCAPED=$(printf '%s\n' "$HOME" | sed 's/[&|]/\\&/g')
  LOCAL_ESCAPED=$(printf '%s\n' "$HERMES_LOCAL" | sed 's/[&|]/\\&/g')
  sed -e "s|__HOME__|$HOME_ESCAPED|g" -e "s|__HERMES_LOCAL__|$LOCAL_ESCAPED|g" "$TMPL" > "$DEST.tmp"
  plutil -lint "$DEST.tmp" >/dev/null
  mv -f "$DEST.tmp" "$DEST"
}

wait_mounted() {
  i=0
  while [ "$i" -lt "$MOUNT_WAIT" ]; do
    wsd_mounted && return 0
    i=$((i + 1))
    sleep 1
  done
  die "$WSD_MOUNT did not mount within ${MOUNT_WAIT}s; check ~/Library/Logs/workspaces-drive-mount.log"
}

check_copy() {
  case "$2" in
    "$WSD_CRYPT_REMOTE":*) wsd_rclone cryptcheck "$1" "$2" --one-way --exclude '._*' --exclude .DS_Store ;;
    *) wsd_rclone check "$1" "$2" --one-way --exclude '._*' --exclude .DS_Store ;;
  esac
}

# While a swap is in flight: put the local directory back if anything stops
# the migration before its copy is proven (an error, a signal).
MIG_HERE=
MIG_ASIDE=
rollback() {
  if [ -n "$MIG_ASIDE" ] && [ -d "$MIG_ASIDE" ]; then
    [ -L "$MIG_HERE" ] && rm -f "$MIG_HERE"
    [ -e "$MIG_HERE" ] || mv "$MIG_ASIDE" "$MIG_HERE"
    echo "rolled back: the local $MIG_HERE is in place again; the Drive copy is kept" >&2
  fi
  MIG_ASIDE=
}

LSOF=/usr/sbin/lsof
[ -x "$LSOF" ] || LSOF=$(command -v lsof 2>/dev/null || true)

# Copy a Group's local directories to Drive and check the copy, then swap
# each for its link, refuse while anything still has a file of the set-aside
# original open, wait until the mount lists every file, check the original
# against Drive once more, and only then delete it. Runs under the links lock
# (the `migrate` action takes it and calls this as `_migrate`).
migrate() {
  spec=${1:-}
  case "$spec" in
    */*) ;;
    *) die "usage: $0 migrate <Tree>/<Group>" ;;
  esac
  tree=${spec%%/*}
  group=${spec#*/}
  case "$group" in */*|'') die "usage: $0 migrate <Tree>/<Group>" ;; esac
  wsd_remote "$tree" >/dev/null || die "$tree is not a tree in WSD_TREES ($WSD_TREES)"
  wsd_mounted || die "the mount is not up at $WSD_MOUNT; run: $0 install"
  [ -n "$LSOF" ] || die "lsof not found; migrate needs it to know nothing still writes the files it deletes"
  trap rollback EXIT
  trap 'exit 130' INT TERM HUP
  moved=0
  for dir in $WSD_LINK_DIRS; do
    here="$WSD_WORKSPACES/$tree/$group/$dir"
    aside="$here.migrating"
    [ -L "$here" ] && { echo "already linked: $tree/$group/$dir"; continue; }
    [ -d "$here" ] || { echo "nothing to move: $tree/$group/$dir"; continue; }
    [ ! -e "$aside" ] && [ ! -L "$aside" ] || die "$aside already exists; move it away first"
    links=$(find "$here" -type l | head -n 5)
    [ -z "$links" ] || die "$tree/$group/$dir holds symlinks, which Drive cannot keep; resolve them first:
$links"
    remote=$(wsd_remote "$tree" "$group/$dir")
    count=$(find "$here" -type f ! -name '._*' ! -name .DS_Store | wc -l | tr -d ' ')
    echo "copying $tree/$group/$dir ($count files, $(du -sh "$here" | cut -f1)) to Drive"
    # The folder itself and empty subfolders too: rclone copies files only,
    # and an empty Group directory would otherwise leave its link dangling.
    wsd_rclone mkdir "$remote"
    wsd_rclone copy "$here" "$remote" --exclude '._*' --exclude .DS_Store --create-empty-src-dirs \
      --progress --stats-one-line
    check_copy "$here" "$remote"
    MIG_HERE=$here
    MIG_ASIDE=$aside
    mv "$here" "$aside"
    ln -s "$(wsd_link_target "$tree" "$group" "$dir")" "$here"
    # From here on a new open of the path reaches Drive; a process that
    # already had a file open would keep writing into the set-aside copy.
    # lsof's exit status says nothing here (it is 1 even when it lists files).
    holders=$("$LSOF" -t +D "$aside" 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$holders" ]; then
      die "files under $tree/$group/$dir are open in another process (PID $holders); close it and run migrate again"
    fi
    # The mount learns of the copy from Drive's change feed (about a minute),
    # at the latest when its directory listings expire (WSD_DIR_CACHE_TIME).
    i=0
    seen=0
    while [ "$i" -lt "$MIGRATE_WAIT_STEPS" ]; do
      seen=$(find "$WSD_MOUNT/$tree/$group/$dir/" -type f ! -name '._*' ! -name .DS_Store 2>/dev/null | wc -l | tr -d ' ')
      [ "$seen" -ge "$count" ] && break
      i=$((i + 1))
      sleep 10
    done
    [ "$seen" -ge "$count" ] || die "the mount shows $seen of $count files of $tree/$group/$dir after $((MIGRATE_WAIT_STEPS * 10))s"
    # Anything written into the original since the first check fails this one.
    check_copy "$aside" "$remote" || die "$tree/$group/$dir changed after it was copied; run migrate again"
    MIG_ASIDE=
    rm -rf "$aside"
    echo "moved: $tree/$group/$dir -> Drive ($count files)"
    moved=$((moved + 1))
  done
  echo "migrate $tree/$group: $moved director$( [ "$moved" = 1 ] && echo y || echo ies) moved"
}

case "$ACTION" in
  setup)
    setup
    ;;
  install)
    require_tools
    require_setup
    [ -f "$TMPL" ] || die "template not found: $TMPL"
    [ -x "$LAUNCHER" ] || die "launcher not executable: $LAUNCHER"
    [ -f "$RUN_SCRIPT" ] || die "run script not found: $RUN_SCRIPT"
    need plutil
    render_plist
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    wait_mounted
    echo "loaded $LABEL; Drive is mounted at $WSD_MOUNT"
    ;;
  restart)
    [ -f "$DEST" ] || die "$LABEL is not installed; run install"
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    wait_mounted
    echo "restarted $LABEL"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    if wsd_mounted; then
      echo "mounted: $WSD_MOUNT"
      echo "cache: $(du -sh "$WSD_CACHE" 2>/dev/null | cut -f1) (soft limit $WSD_CACHE_MAX_SIZE)"
      wsd_links --check || true
    else
      echo "not mounted: $WSD_MOUNT"
    fi
    ;;
  links|migrate)
    # Both change Group links: run this script again under the links lock
    # (waiting up to 30 s for a running pass), as `_links` / `_migrate`.
    [ "$ACTION" = links ] || require_tools
    rc=0
    wsd_with_lock "${WSD_LOCK_WAIT:-30}" sh "$0" "_$ACTION" "${2:-}" || rc=$?
    [ "$rc" -ne 75 ] || die "another links pass or migration holds $WSD_LOCK; try again shortly"
    exit "$rc"
    ;;
  _links)
    wsd_links || true
    ;;
  _migrate)
    migrate "${2:-}"
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    if wsd_mounted; then
      diskutil unmount force "$WSD_MOUNT" >/dev/null 2>&1 || true
    fi
    echo "unloaded + removed $LABEL; the Group links now point at nothing until install (Drive data, config and Keychain items kept)"
    ;;
  *)
    echo "usage: $0 setup | install | restart | status | links | migrate <Tree>/<Group> | uninstall" >&2
    exit 1
    ;;
esac
