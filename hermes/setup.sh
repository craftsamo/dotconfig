#!/usr/bin/env bash
#
# Install the Hermes Agent runtime for this dotconfig setup — one idempotent
# command that captures the otherwise-manual flow. Safe to re-run.
#
#   ~/.config/hermes/setup.sh
#
# What it does (no shell-rc edits, no interactive wizard, no .env, no skill seeding):
#   1. Clone NousResearch/hermes-agent via ghq (only if missing)
#   2. Upstream `setup-hermes.sh --runtime-only`: stage the pinned uv, then Hermes'
#      package manager (PM) installs the pinned Python, tools and the hash-verified
#      `all` dependency generation, plus the checkout's test interpreter
#   3. Sync the capability extras below into the same generation (PM unions them)
#   4. Publish the checkout's launchers into ~/.local/bin (behind the bin/hermes
#      secret shim); an existing link into this checkout is adopted, a foreign
#      command is left alone
#
# PM owns the interpreter (Python 3.14) and the dependency generation; there is no
# in-tree venv/. Helpers that need Hermes' Python run through `hermes-python`.
# The config/SOUL/mcp symlinks into ~/.hermes/ are created separately by
# ../install.sh. Secrets come from the macOS Keychain via bin/hermes (secret-shim).
#
# Deliberately NOT the full upstream installer: it edits shell rc files (~/.zshrc
# is a symlink into this repo), seeds bundled skills and runs interactive stages.
#
# To UPDATE later, use `hermes update`, not this script.

set -euo pipefail

REPO_PATH="github.com/NousResearch/hermes-agent"
REPO_URL="https://$REPO_PATH"

# Capability extras on top of `all` (the set this machine uses; PM unions extras into one
# recorded selection, so re-running only adds). Trim for a leaner environment.
EXTRAS=(
  acp anthropic audio-io bedrock computer-use ddgs dingtalk discord doc-extract edge-tts exa fal
  feishu firecrawl google homeassistant mcp messaging modal parallel-web slack sms stt-whisper
  teams telegram trace-upload tts-premium uvloop vertex voice web wecom youtube
)

die() {
  echo "error: $*" >&2
  exit 1
}

command -v ghq >/dev/null 2>&1 ||
  die "ghq not found — it is in the Brewfile; run ./install.sh --deps first"

# 1. Clone (only if missing — updates are `hermes update`'s job)
SRC="${HERMES_AGENT_DIR:-$(ghq root)/$REPO_PATH}"
if [ -d "$SRC/.git" ]; then
  echo "[hermes] source present: $SRC"
else
  echo "[hermes] cloning $REPO_URL ..."
  ghq get "$REPO_URL"
fi

# 2. PM runtime + tools + `all` generation + test interpreter (no rc edits, no .env)
echo "[hermes] provisioning the PM runtime (first run takes a few minutes) ..."
( unset PYTHONHOME PYTHONPATH VIRTUAL_ENV UV_PYTHON UV_PROJECT_ENVIRONMENT
  bash "$SRC/setup-hermes.sh" --runtime-only --test-environment )

launcher="$SRC/.hermes/bin/hermes"
[ -x "$launcher" ] || die "PM did not publish $launcher"
store_py=$("$launcher" --print-runtime-command | /usr/bin/python3 -c 'import json, sys; print(json.load(sys.stdin)[0])')
echo "[hermes] store python: $store_py ($("$store_py" --version 2>&1))"

# 3. Capability extras into the same recorded selection
echo "[hermes] syncing extras: ${EXTRAS[*]} ..."
"$store_py" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
from pm import sync_venv
sync_venv(sys.argv[2:], explicit=True)
' "$SRC" "${EXTRAS[@]}"

# 4. User-facing launchers (wrapper scripts that forward to the checkout's own launcher)
mkdir -p "$HOME/.local/bin"
"$store_py" -I -X utf8 "$SRC/hermes_cli/_launchers.py" "$HOME/.local/bin"

echo "[hermes] done."
echo "[hermes] verify:  hermes --version ; hermes-python --print"
echo "[hermes] symlinks: ../install.sh    (creates ~/.hermes/{config.yaml,SOUL.md,mcp.json})"
echo "[hermes] keys:     secret set OPENROUTER_API_KEY -p hermes   (injected from the Keychain, no .env)"
