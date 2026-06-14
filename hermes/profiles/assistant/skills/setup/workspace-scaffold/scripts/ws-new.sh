#!/usr/bin/env bash
#
# Scaffold groups/repos in ~/Workspaces (nested layout).
#
#   ws-new.sh group projects <Group>   -> Projects/<Group>/{github,docs,data,teams} + AGENTS.md
#   ws-new.sh group personal <Group>   -> Personal/<Group>/{data,docs} + AGENTS.md (no git)
#   ws-new.sh repo <Group> <repo>       -> Projects/<Group>/github/<repo> (+ git init + AGENTS.md)
#
# Idempotent: never re-inits an existing repo or overwrites an existing AGENTS.md.
set -euo pipefail

WS="${WORKSPACES_DIR:-$HOME/Workspaces}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat >&2 <<'EOF'
usage:
  ws-new.sh group projects <Group>   # Projects/<Group>/{github,docs,data,teams}
  ws-new.sh group personal <Group>   # Personal/<Group>/{data,docs} (no git)
  ws-new.sh repo <Group> <repo>       # Projects/<Group>/github/<repo> (+ git init)
EOF
  exit 2
}

# Names: letters/digits/dot/underscore/hyphen; no slash, no "..", no leading dot or hyphen.
valid() { case "$1" in ''|*[!A-Za-z0-9._-]*|.*|-*|*..*) return 1 ;; *) return 0 ;; esac; }

seed() { # seed <template> <dest-AGENTS.md>
  [ -f "$1" ] && [ ! -f "$2" ] && cp "$1" "$2" || true
}

case "${1:-}" in
  group)
    area="${2:-}"; name="${3:-}"
    valid "$name" || { echo "ws-new: bad group name: '$name'" >&2; usage; }
    case "$area" in
      projects)
        base="$WS/Projects/$name"
        mkdir -p "$base/github" "$base/docs" "$base/data" "$base/teams"
        seed "$SKILL_DIR/templates/group.AGENTS.md" "$base/AGENTS.md"
        ;;
      personal)
        base="$WS/Personal/$name"
        mkdir -p "$base/data" "$base/docs"
        seed "$SKILL_DIR/templates/personal-group.AGENTS.md" "$base/AGENTS.md"
        ;;
      *) usage ;;
    esac
    echo "ws-new: created group $base"
    ;;
  repo)
    group="${2:-}"; repo="${3:-}"
    valid "$group" || { echo "ws-new: bad group: '$group'" >&2; usage; }
    valid "$repo"  || { echo "ws-new: bad repo: '$repo'" >&2; usage; }
    dest="$WS/Projects/$group/github/$repo"
    mkdir -p "$dest"
    [ -d "$dest/.git" ] || git -C "$dest" init -q
    seed "$SKILL_DIR/templates/repo.AGENTS.md" "$dest/AGENTS.md"
    echo "ws-new: created repo $dest (git + AGENTS.md stub — fill it in)"
    ;;
  *) usage ;;
esac
