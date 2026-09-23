#!/usr/bin/env bash
# Verify the hermes-agent checkout still carries every local patch.
#
# Local fixes live as `fix/*` branches in the hermes-agent checkout and are
# merged into the running branch (`local`). `hermes update` can drop them
# silently, and several guard behavior with no visible error when missing
# (e.g. completion notifications for secondary profiles, real-profile browser
# isolation). The branch list is the ledger: this script checks it against
# HEAD instead of a hand-kept list in the docs.
#
# Also checks the upstream case-collision workaround: on case-insensitive APFS
# the two `contributors/emails/agent@[Aa]gents-Mac-mini.local` files are one
# file, and without skip-worktree on the lowercase twin the checkout is
# permanently dirty and every rebase/merge refuses to start.
#
# Usage: scripts/check-local-patches.sh [hermes-agent-dir]
# Exit: 0 all present, 1 something missing, 2 checkout not found.
set -euo pipefail

dir="${1:-${HERMES_AGENT_DIR:-$(ghq root 2>/dev/null)/github.com/NousResearch/hermes-agent}}"
if ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
  echo "hermes-agent checkout not found: $dir" >&2
  exit 2
fi

status=0
head_ref="$(git -C "$dir" symbolic-ref --quiet --short HEAD || echo '(detached)')"
echo "checkout: $dir"
echo "HEAD:     $head_ref @ $(git -C "$dir" rev-parse --short HEAD)"
[ "$head_ref" = "local" ] || { echo "WARN  HEAD is not the 'local' branch"; status=1; }

branches="$(git -C "$dir" for-each-ref --format='%(refname:short)' 'refs/heads/fix/*')"
if [ -z "$branches" ]; then
  echo "WARN  no fix/* branches found"
  status=1
fi
while IFS= read -r b; do
  [ -n "$b" ] || continue
  if git -C "$dir" merge-base --is-ancestor "$b" HEAD; then
    echo "ok    $b"
  else
    echo "MISS  $b is not merged into HEAD"
    status=1
  fi
done <<<"$branches"

twin="contributors/emails/agent@agents-Mac-mini.local"
if git -C "$dir" ls-files --error-unmatch -- "$twin" >/dev/null 2>&1; then
  if git -C "$dir" ls-files -v -- "$twin" | grep -q '^S '; then
    echo "ok    skip-worktree on $twin"
  else
    echo "MISS  skip-worktree on $twin (git update-index --skip-worktree -- '$twin')"
    status=1
  fi
fi

exit "$status"
