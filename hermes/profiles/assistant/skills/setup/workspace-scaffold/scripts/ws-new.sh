#!/usr/bin/env bash
#
# Scaffold a repo or personal area in ~/Workspaces (flat layout).
#
#   ws-new.sh repo <owner>/<repo>   -> Projects/github/<owner>/<repo> (+ git init + AGENTS.md)
#   ws-new.sh personal <name>        -> Personal/<name>/ (no git)
#
# Idempotent: never re-inits an existing repo or overwrites an existing AGENTS.md.
set -euo pipefail

WS="${WORKSPACES_DIR:-$HOME/Workspaces}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TPL="$SKILL_DIR/templates/repo.AGENTS.md"

usage() {
  echo "usage: ws-new.sh repo <owner>/<repo> | ws-new.sh personal <name>" >&2
  exit 2
}

cmd="${1:-}"
arg="${2:-}"
[ -n "$cmd" ] && [ -n "$arg" ] || usage

case "$cmd" in
  repo)
    case "$arg" in */*) : ;; *) echo "repo needs <owner>/<repo>" >&2; exit 2 ;; esac
    dest="$WS/Projects/github/$arg"
    mkdir -p "$dest"
    [ -d "$dest/.git" ] || git -C "$dest" init -q
    if [ -f "$TPL" ] && [ ! -f "$dest/AGENTS.md" ]; then
      cp "$TPL" "$dest/AGENTS.md"
    fi
    echo "created $dest (git + AGENTS.md stub — fill it in)"
    ;;
  personal)
    dest="$WS/Personal/$arg"
    mkdir -p "$dest"
    echo "created $dest (no git)"
    ;;
  *)
    usage
    ;;
esac
