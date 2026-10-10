#!/usr/bin/env bash
#
# Give a task worktree of this repo the untracked pieces its tests need.
#
#   ./worktree-setup.sh                   link into the live private overlay
#   ./worktree-setup.sh --private <dir>   link into another private checkout
#                                         (e.g. a paired candidate worktree)
#
# A worktree only carries tracked files, so it lacks what the live checkout
# gets from install scripts: the private overlay links (per-profile SOUL.md and
# config.yaml, private plugins) and opencode/node_modules. This script mirrors
# every gitignored symlink of the live checkout that points into the private
# overlay, links opencode/node_modules to the live copy, and nothing else.
#
# It writes only inside this worktree, refuses to run in the live checkout,
# never overwrites a real file, and is idempotent. HOME, ~/.hermes and the
# live checkout are never touched.

set -euo pipefail

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
status=0

usage() {
  cat <<'EOF'
Usage: ./worktree-setup.sh [--private <dir>] [--help]

  (no args)        link the private overlay links to the live overlay
  --private <dir>  link them to <dir> instead (a private-dotconfig checkout)
  --help           show this help
EOF
}

private_dir=""
while [ $# -gt 0 ]; do
  case "$1" in
    --private)
      [ $# -ge 2 ] || { usage >&2; exit 2; }
      private_dir="$2"
      shift 2
      ;;
    --help | -h)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

common="$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir)"
LIVE="$(cd "$(dirname "$common")" && pwd -P)"
if [ "$WT" = "$LIVE" ]; then
  echo "ERROR: $WT is the live checkout; run this in a task worktree" >&2
  exit 1
fi

link() {
  local target="$1" dest="$2"
  case "$dest" in
    "$WT"/*) ;;
    *)
      echo "ERROR: refusing to write outside the worktree: $dest"
      status=1
      return
      ;;
  esac
  if [ ! -e "$target" ]; then
    echo "SKIP: missing target: $target"
    status=1
    return
  fi
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "WARN: $dest exists and is not a symlink — not overwriting"
    status=1
    return
  fi
  if ! git -C "$WT" check-ignore -q -- "${dest#"$WT"/}"; then
    echo "WARN: $dest is not gitignored here — not linking"
    status=1
    return
  fi
  mkdir -p "$(dirname "$dest")"
  ln -sfn "$target" "$dest"
  echo "  ok: $dest -> $target"
}

echo "[private]"
live_private=""
[ -d "$LIVE/private" ] && live_private="$(cd "$LIVE/private" && pwd -P)"
if [ -n "$private_dir" ]; then
  private_dir="$(cd "$private_dir" && pwd -P)"
else
  private_dir="$live_private"
fi
if [ -z "$live_private" ] || [ -z "$private_dir" ]; then
  echo "  skipped: no private overlay at $LIVE/private"
else
  link "$private_dir" "$WT/private"
  # --directory lists an ignored directory once instead of its contents, so
  # links inside ignored trees (venvs, node_modules) are never visited.
  while IFS= read -r rel; do
    rel="${rel%/}"
    [ -L "$LIVE/$rel" ] || continue
    target="$(readlink "$LIVE/$rel")"
    case "$target" in
      "$LIVE/private/"*) sub="${target#"$LIVE/private/"}" ;;
      "$live_private/"*) sub="${target#"$live_private/"}" ;;
      *) continue ;;
    esac
    link "$private_dir/$sub" "$WT/$rel"
  done < <(git -C "$LIVE" ls-files --others --ignored --exclude-standard --directory)
fi

echo "[opencode]"
if [ -d "$WT/opencode/node_modules" ] && [ ! -L "$WT/opencode/node_modules" ]; then
  echo "  ok: $WT/opencode/node_modules is installed in this worktree"
elif [ -d "$LIVE/opencode/node_modules" ]; then
  link "$LIVE/opencode/node_modules" "$WT/opencode/node_modules"
  if ! cmp -s "$LIVE/opencode/package.json" "$WT/opencode/package.json"; then
    echo "WARN: opencode/package.json differs from the live checkout;"
    echo "      replace the link with: npm install --prefix \"$WT/opencode\""
  fi
else
  echo "  skipped: no opencode/node_modules in $LIVE (run ./install.sh --deps there)"
fi

exit $status
