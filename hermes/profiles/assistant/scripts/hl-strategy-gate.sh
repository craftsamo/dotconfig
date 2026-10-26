#!/bin/sh
# hl-strategy-gate — the wake gate of the Assistant's Hyperliquid strategies.
#
# An assistant-profile cron script for a job WITH an agent: it reads every active strategy under
# <profile home>/hl-strategies/ through Hyperliquid's public /info endpoint and prints one JSON line.
# When nothing is to be done or said that line is {"wakeAgent": false} and no model runs; otherwise
# it lists the exact hyperliquid quotes the rules call for, and the Assistant follows the
# hyperliquid-access:run-strategy skill. It never signs or reads a key. Contract:
# docs/hyperliquid.md "Strategies". The job lives in the machine-local cron; the
# hyperliquid-access:configure-strategy skill's "Running it" section has the cronjob call.

set -u

# The scheduler runs this script where install.sh copied it, <HERMES_HOME>/scripts (cron resolves
# real paths, so a link cannot serve), so the profile home is its parent — not $HERMES_HOME, which
# under the multiplex gateway may name another profile. The repository, where hl_gate.py lives, is
# found through the home's plugins tree: a real directory of links into it. The web3 engine lives
# in the machine-local runtime root.
here="$(cd "$(dirname "$0")" && pwd -P)"
home="$(dirname "$here")"
hermes="$(cd "$home/plugins/web3/_shared" 2>/dev/null && pwd -P)/../../.."
# Engine runtime root: machine-local, outside the repository (HERMES_LOCAL overrides).
HERMES_LOCAL="${HERMES_LOCAL:-$HOME/.hermes/local}"
python="$HERMES_LOCAL/web3/venv/bin/python"

if [ ! -x "$python" ]; then
  echo "hl-strategy-gate: the web3 engine is not installed (scripts/web3.sh install)" >&2
  exit 1
fi
if [ ! -d "$home" ]; then
  echo "hl-strategy-gate: no profile home at $home" >&2
  exit 1
fi
exec "$python" "$hermes/plugins/web3/_shared/hl_gate.py" "$home/hl-strategies"
