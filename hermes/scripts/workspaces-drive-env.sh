# Sourced by launchd/workspaces-drive-launchctl.sh and scripts/workspaces-drive-run.sh:
# the settings of the Workspaces Drive mount (docs/ops/workspaces-drive.md) and the
# helpers both share. POSIX sh; defines WSD_* variables and wsd_* functions only.
#
# Settings resolve in one order: the environment, then the machine-local
# override $HERMES_LOCAL/workspaces-drive/settings.env (the private overlay links
# its own there), then the defaults below. The override is sourced as shell, so
# it sets plain assignments only.

HERMES_LOCAL="${HERMES_LOCAL:-$HOME/.hermes/local}"
WSD_DIR="${WSD_DIR:-$HERMES_LOCAL/workspaces-drive}"
WSD_SETTINGS="${WSD_SETTINGS:-$WSD_DIR/settings.env}"
if [ -f "$WSD_SETTINGS" ]; then
  # shellcheck disable=SC1090
  . "$WSD_SETTINGS"
fi

: "${WSD_WORKSPACES:=$HOME/Workspaces}"
: "${WSD_MOUNT:=$WSD_WORKSPACES/.drive}"
# Folder in My Drive that holds the whole tree; no spaces (it is part of a
# remote string).
: "${WSD_DRIVE_PATH:=Workspaces}"
# OAuth scope the drive remote asks for at setup: drive (sees files added from
# the web or a phone) or drive.file (sees only what this mount created).
: "${WSD_DRIVE_SCOPE:=drive}"
# Top-level trees of the mount, each stored plain or encrypted (rclone crypt).
: "${WSD_TREES:=Projects=plain Personal=crypt}"
# Directories of each Group that live on Drive, as links into the mount.
: "${WSD_LINK_DIRS:=assets}"
# Groups never linked, as Tree/Group words.
: "${WSD_SKIP_GROUPS:=}"
: "${WSD_CACHE_MAX_SIZE:=20G}"
: "${WSD_CACHE_MAX_AGE:=168h}"
# How long the mount trusts a directory listing. Drive's change feed (polled
# every minute) refreshes it sooner; this bounds how long a copy made outside
# the mount (migrate) can stay invisible.
WSD_DIR_CACHE_TIME=2m
# Seconds between maintenance passes (new Group links, AppleDouble sweep).
: "${WSD_MAINTENANCE_INTERVAL:=900}"
# soft + deadtimeout: a dead server fails calls and unmounts instead of
# hanging them; locallocks: the server has no lock manager, so a lock request
# would wait forever; nonegnamecache: a name the client once found missing is
# asked again, so files added on Drive from elsewhere appear; nobrowse: no
# Desktop/Finder volume.
: "${WSD_NFS_OPTIONS:=locallocks,soft,intr,timeo=50,retrans=2,deadtimeout=30,mutejukebox,nonegnamecache,nobrowse}"

WSD_CONFIG="$WSD_DIR/rclone.conf"
WSD_CACHE="$WSD_DIR/cache"
WSD_DRIVE_REMOTE=wsdrive-drive
WSD_CRYPT_REMOTE=wsdrive-crypt
WSD_SECRET_PROJECT=hermes
WSD_SECRET_SCOPE=workspaces-drive
WSD_CONFIG_PASS_ITEM=WORKSPACES_DRIVE_CONFIG_PASS
SECRET="${SECRET_CLI:-$HOME/.config/bin/secret}"

wsd_die() { echo "workspaces-drive: $*" >&2; exit 1; }

# rclone on the encrypted config. The config password comes from the Keychain
# through --password-command at every start, so it is never in an environment
# or on a command line, and rclone may save a refreshed token into the file.
# wsd_exec_rclone replaces the calling shell, so a mount started with `&` has
# rclone's own PID and a stop reaches it; wsd_rclone runs it in a subshell.
wsd_exec_rclone() {
  exec rclone --config "$WSD_CONFIG" --ask-password=false \
    --password-command "$SECRET get $WSD_CONFIG_PASS_ITEM -p $WSD_SECRET_PROJECT --scope $WSD_SECRET_SCOPE --no-stage" \
    "$@"
}
wsd_rclone() { ( wsd_exec_rclone "$@" ); }

wsd_check_settings() {
  case "$WSD_DRIVE_PATH" in
    ''|*' '*|/*|*/) wsd_die "WSD_DRIVE_PATH must be a relative folder without spaces: '$WSD_DRIVE_PATH'" ;;
  esac
  case "$WSD_DRIVE_SCOPE" in
    drive|drive.file) ;;
    *) wsd_die "WSD_DRIVE_SCOPE must be drive or drive.file: '$WSD_DRIVE_SCOPE'" ;;
  esac
  for spec in $WSD_TREES; do
    case "$spec" in
      *=plain|*=crypt) ;;
      *) wsd_die "WSD_TREES entries are Tree=plain or Tree=crypt: '$spec'" ;;
    esac
  done
}

# The remote path a tree, a Group directory or anything below maps to:
# wsd_remote <Tree> [<rest>]. Plain trees sit under the Drive folder by name;
# encrypted ones under the same folder through the crypt remote, which keeps
# directory names readable and encrypts file names and contents.
wsd_remote() {
  tree=$1
  rest=${2:-}
  mode=
  for spec in $WSD_TREES; do
    [ "${spec%%=*}" = "$tree" ] && mode=${spec#*=}
  done
  case "$mode" in
    plain) printf '%s:%s/%s%s\n' "$WSD_DRIVE_REMOTE" "$WSD_DRIVE_PATH" "$tree" "${rest:+/$rest}" ;;
    crypt) printf '%s:%s%s\n' "$WSD_CRYPT_REMOTE" "$tree" "${rest:+/$rest}" ;;
    *) return 1 ;;
  esac
}

# One remote whose top-level directories are the trees (rclone combine), so a
# single mount shows plain and encrypted trees side by side.
wsd_combine() {
  upstreams=
  for spec in $WSD_TREES; do
    tree=${spec%%=*}
    upstreams="$upstreams${upstreams:+ }$tree=$(wsd_remote "$tree")"
  done
  printf ":combine,upstreams='%s':\n" "$upstreams"
}

wsd_mounted() {
  mount | grep -q " on $WSD_MOUNT (nfs"
}

# The link a Group directory gets: relative when the mount sits inside the
# workspace (so the link resolves inside ~/Workspaces), absolute otherwise.
wsd_link_target() {
  tree=$1 group=$2 dir=$3
  case "$WSD_MOUNT" in
    "$WSD_WORKSPACES"/*) printf '../../%s/%s/%s/%s\n' "${WSD_MOUNT#"$WSD_WORKSPACES"/}" "$tree" "$group" "$dir" ;;
    *) printf '%s/%s/%s/%s\n' "$WSD_MOUNT" "$tree" "$group" "$dir" ;;
  esac
}

wsd_skipped() {
  for s in $WSD_SKIP_GROUPS; do
    [ "$s" = "$1" ] && return 0
  done
  return 1
}

# One lock for everything that changes Group links (a links pass and
# migrate), so a pass never links a directory a migration has just moved aside.
# lockf(1) holds it in the kernel for the life of the command it runs, so a
# holder that dies releases it. Exit 75 means another holder has it.
WSD_LOCK="$WSD_DIR/links.lock"
wsd_with_lock() {
  timeout=$1
  shift
  mkdir -p "$WSD_DIR"
  lockf -k -s -t "$timeout" "$WSD_LOCK" "$@"
}

# Give every Group of every tree its Drive directories as links into the
# mount. Both helpers below reach Drive through rclone, never through the
# mount: macOS refuses a shell that launchd started any access to a network
# volume, and the mount picks the change up from Drive's change feed.
# A missing directory is created on Drive and linked; a correct link is
# left alone; a real local directory or a link elsewhere is reported, never
# moved (migration is its own command). Prints one line per change or finding.
# --check reports what would be linked and changes nothing; --quiet (the
# repeated maintenance passes) prints changes only. Callers that change links
# run it under wsd_with_lock.
wsd_links() {
  wsd_mounted || wsd_die "the mount is not up at $WSD_MOUNT"
  check= quiet=
  case "${1:-}" in
    --check) check=1 ;;
    --quiet) quiet=1 ;;
  esac
  found=0
  for spec in $WSD_TREES; do
    tree=${spec%%=*}
    [ -d "$WSD_WORKSPACES/$tree" ] || continue
    for g in "$WSD_WORKSPACES/$tree"/*/; do
      [ -d "$g" ] || continue
      group=$(basename "$g")
      wsd_skipped "$tree/$group" && continue
      for dir in $WSD_LINK_DIRS; do
        here="$WSD_WORKSPACES/$tree/$group/$dir"
        want=$(wsd_link_target "$tree" "$group" "$dir")
        if [ -L "$here" ]; then
          [ "$(readlink "$here")" = "$want" ] && continue
          [ -n "$quiet" ] || echo "foreign link: $tree/$group/$dir -> $(readlink "$here") (left alone)"
          found=1
        elif [ -e "$here" ]; then
          [ -n "$quiet" ] || echo "local: $tree/$group/$dir is a real directory; move it with: migrate $tree/$group"
          found=1
        elif [ -n "$check" ]; then
          echo "would link: $tree/$group/$dir"
        else
          wsd_rclone mkdir "$(wsd_remote "$tree" "$group/$dir")" ||
            { echo "failed: could not create $tree/$group/$dir on Drive"; found=1; continue; }
          ln -s "$want" "$here"
          echo "linked: $tree/$group/$dir -> $want"
        fi
      done
    done
  done
  return $found
}

# AppleDouble (._*) and .DS_Store files: macOS writes them for extended
# attributes the NFS server cannot keep. Deleted on Drive for good (not to its
# trash, which they would fill), across every tree.
wsd_sweep() {
  wsd_mounted || return 0
  wsd_rclone delete "$(wsd_combine)" --include '._*' --include .DS_Store \
    --drive-use-trash=false --fast-list -q 2>/dev/null || true
}
