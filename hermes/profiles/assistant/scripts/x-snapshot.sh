#!/bin/sh
# x-snapshot — record the main account's public X counts for x-access `insights`.
#
# An assistant-profile cron script (no_agent — zero LLM cost), every six hours: one paced
# read of the main account's recent posts through the x-access engine, appended to
# ~/.x-access/metrics.jsonl. Silent on success and on a pause (the next run catches up);
# a real failure (no engine, cookies refused) exits nonzero so Hermes alerts.
# Contract: docs/x-access.md "Metrics". The job itself lives in the machine-local cron:
#
#   hermes -p assistant cron create "0 */6 * * *" --name x-snapshot --no-agent \
#     --script x-snapshot.sh --deliver telegram

set -u

# The profile home is this script's parent as invoked (<HERMES_HOME>/scripts/..), not $HERMES_HOME:
# the multiplex gateway's process env may name another profile. Its config.yaml has the handle.
home=$(cd "$(dirname "$0")/.." && pwd)
engine="$(cd "$(dirname "$0")" && pwd -P)/../../../plugins/x-access/xa.py"

# Hermes' own interpreter: the engine reads the profile's config.yaml with hermes_yaml.
exec "$HOME/.config/bin/hermes-python" "$engine" snapshot "$home"
