#!/bin/sh
# x-ranking-watch — the wake gate of the Assistant's weekly X-ranking watch.
#
# A cron script for a job WITH an agent: prints {"wakeAgent": false} when X's published defaults match
# the baseline, otherwise a report the Assistant turns into an OpenCode plan.
# The job is kept beside the private config since its delivery names a chat; its run.sh execs this
# script where install.sh copied it. Contract: docs/x-access.md "Ranking watch".

set -u

here="$(cd "$(dirname "$0")" && pwd -P)"
home="$(dirname "$here")"
engine="$(cd "$home/plugins/social/x-access" 2>/dev/null && pwd -P)/ranking_watch.py"

if [ ! -f "$engine" ]; then
  echo "x-ranking-watch: the x-access plugin is not linked under $home/plugins (run install.sh)" >&2
  exit 1
fi

exec "$HOME/.config/bin/hermes-python" "$engine" check "$@"
