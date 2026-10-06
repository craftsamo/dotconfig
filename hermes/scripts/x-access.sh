#!/usr/bin/env bash
# Engine manager for the x-access plugin (read-only X through twscrape).
#
# The plugin runs plugins/social/x-access/bridge.py with the interpreter of an isolated venv
# under the ignored hermes/local/twscrape/, built from the hash-locked
# engines/twscrape/requirements.lock. The sub-account's session cookies live only in the
# Keychain (X_READER_COOKIES, project hermes, scope x-reader), never in a file:
#
#   secret set X_READER_COOKIES -p hermes --scope x-reader -D COOKIE
#
#   install   build or refresh the venv from the lock (Python 3.12.11, uv)
#   status    engine version, whether the cookies are stored, and what the tool last saw
#             of them (no request to X, the cookie value is never printed)
set -euo pipefail

HERMES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$HERMES_DIR/engines/twscrape/requirements.lock"
VENV="$HERMES_DIR/local/twscrape/venv"
PYTHON_VERSION="3.12.11"
STATE="$HOME/.x-access/state.json"
SECRET="$HOME/.config/bin/secret"

die() { echo "error: $*" >&2; exit 1; }

version() {
  "$VENV/bin/python" -c 'import importlib.metadata as m; print(m.version("twscrape"))'
}

case "${1:-}" in
  install)
    command -v uv >/dev/null 2>&1 || die "uv not found"
    [ -f "$LOCK" ] || die "missing $LOCK"
    if [ ! -x "$VENV/bin/python" ]; then
      UV_NO_CONFIG=1 uv venv "$VENV" --python "$PYTHON_VERSION" --managed-python
    fi
    [ "$("$VENV/bin/python" --version 2>&1)" = "Python $PYTHON_VERSION" ] \
      || die "unexpected Python in $VENV; remove it and run install again"
    UV_NO_CONFIG=1 uv pip sync --python "$VENV/bin/python" --require-hashes --strict "$LOCK"
    echo "installed twscrape $(version) in $VENV"
    ;;
  status)
    if [ -x "$VENV/bin/python" ]; then
      echo "engine:  twscrape $(version) ($VENV)"
    else
      echo "engine:  not installed (run: $0 install)"
    fi
    if "$SECRET" show X_READER_COOKIES -p hermes --scope x-reader >/dev/null 2>&1; then
      echo "cookies: stored (X_READER_COOKIES, project hermes, scope x-reader)"
    else
      echo "cookies: missing (secret set X_READER_COOKIES -p hermes --scope x-reader -D COOKIE)"
    fi
    if [ -f "$STATE" ] && [ -x "$VENV/bin/python" ]; then
      "$VENV/bin/python" - "$STATE" <<'PY'
import json, sys, time
state = json.load(open(sys.argv[1]))
now = time.time()
calls = [t for t in state.get("calls") or [] if now - t < 86400]
print(f"reads:   {sum(1 for t in calls if now - t < 3600)} in the last hour, {len(calls)} in 24 h")
if state.get("refused"):
    print(f"refused: X refused these cookies ({state['refused'].get('error')}); store fresh ones")
if state.get("rate_limited_until"):
    print(f"limited: until {state['rate_limited_until']} (UTC) if still in the future")
PY
    fi
    ;;
  *)
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
