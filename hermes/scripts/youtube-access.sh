#!/usr/bin/env bash
# Engine manager for the youtube-access plugin (yt-dlp for transcripts and downloads).
#
# The plugin runs plugins/social/youtube-access/bridge.py with the interpreter of an isolated venv
# under the ignored hermes/local/yt-dlp/, built from the hash-locked
# engines/yt-dlp/requirements.lock. YouTube's player challenges are solved by Deno (Brewfile);
# merged video downloads need ffmpeg. The OAuth tokens of the user's channels are not this
# script's business: `yaccess` stores them in the Keychain (project hermes, scope youtube-access).
#
#   install   build or refresh the venv from the lock (Python 3.12.11, uv)
#   status    engine version, Deno / ffmpeg, the channels yaccess stored and today's usage
#             (no request to YouTube, no token is printed)
set -euo pipefail

HERMES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$HERMES_DIR/engines/yt-dlp/requirements.lock"
VENV="$HERMES_DIR/local/yt-dlp/venv"
PYTHON_VERSION="3.12.11"
STORE="$HOME/.youtube-access"
SECRET="$HOME/.config/bin/secret"

die() { echo "error: $*" >&2; exit 1; }

version() {
  "$VENV/bin/python" -c 'import importlib.metadata as m; print(m.version("yt-dlp"))'
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
    echo "installed yt-dlp $(version) in $VENV"
    command -v deno >/dev/null 2>&1 || echo "warning: deno not found; YouTube downloads need it (brew install deno)"
    command -v ffmpeg >/dev/null 2>&1 || echo "warning: ffmpeg not found; merged video downloads need it"
    ;;
  status)
    if [ -x "$VENV/bin/python" ]; then
      echo "engine:   yt-dlp $(version) ($VENV)"
    else
      echo "engine:   not installed (run: $0 install)"
    fi
    echo "deno:     $(command -v deno || echo missing)"
    echo "ffmpeg:   $(command -v ffmpeg || echo missing)"
    if "$SECRET" show YOUTUBE_OAUTH -p hermes --scope youtube-access >/dev/null 2>&1; then
      echo "tokens:   stored (YOUTUBE_OAUTH, project hermes, scope youtube-access)"
    else
      echo "tokens:   none (run: yaccess auth CLIENT_SECRET.json)"
    fi
    if [ -f "$STORE/channels.json" ] && [ -x "$VENV/bin/python" ]; then
      "$VENV/bin/python" - "$STORE" <<'PY'
import json, sys
from pathlib import Path
store = Path(sys.argv[1])
channels = json.loads((store / "channels.json").read_text()).get("channels") or {}
for cid, meta in channels.items():
    print(f"channel:  {meta.get('title')} {meta.get('handle') or ''} ({cid})")
try:
    quota = json.loads((store / "state.json").read_text()).get("quota") or {}
    print(f"quota:    {quota.get('units', 0)} units, {quota.get('search', 0)} searches, "
          f"{quota.get('upload', 0)} uploads on {quota.get('day', '-')} (Pacific)")
except (OSError, ValueError):
    pass
PY
    fi
    ;;
  *)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
