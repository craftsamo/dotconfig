#!/bin/sh
# x-snapshot — record the main account's public X counts for x-access `insights`.
#
# One paced read of the main account's recent posts through the x-access engine, appended to
# ~/.x-access/metrics.jsonl (zero LLM cost: job.yaml runs this with no model). Silent on
# success and on a pause (the next run catches up); a real failure (no engine, cookies refused)
# exits nonzero so Hermes alerts. Contract: docs/x-access.md "Metrics".

set -u

# The owning profile's home comes from the cron-sync wrapper that execs this script; its
# config.yaml holds the handle. The engine sits in the same checkout as this manifest.
home="$HERMES_HOME"
engine="$(cd "$(dirname "$0")" && pwd -P)/../../../../plugins/social/x-access/xa.py"

# Hermes' own interpreter: the engine reads the profile's config.yaml with hermes_yaml.
exec "$HOME/.config/bin/hermes-python" "$engine" snapshot "$home"
