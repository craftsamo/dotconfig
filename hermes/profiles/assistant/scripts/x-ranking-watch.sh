#!/bin/sh
# x-ranking-watch — the wake gate of the Assistant's weekly X-ranking watch.
#
# A cron script for a job WITH an agent: prints {"wakeAgent": false} when defaults match the baseline
# or the diff equals the one last reported, otherwise a report the Assistant turns into an OpenCode plan.
# The job is kept beside the private config since its delivery names a chat; its run.sh execs this
# script where install.sh copied it. Contract: docs/x-tools.md "Ranking watch".

set -u

engine="$HOME/.config/hermes/scripts/x-ranking-watch.py"

if [ ! -f "$engine" ]; then
  echo "x-ranking-watch: $engine is missing (run install.sh)" >&2
  exit 1
fi

exec "$HOME/.config/bin/hermes-python" "$engine" check "$@"
