#!/usr/bin/env bash
#
# Install the Hermes Agent binary for this dotfiles setup — one idempotent
# command that captures the otherwise-manual flow. Safe to re-run.
#
#   ~/.config/hermes/setup.sh
#
# What it does (no shell-rc edits, no interactive wizard):
#   1. Clone NousResearch/hermes-agent via ghq (only if missing)
#   2. Create a Python 3.11 venv with uv (only if missing)
#   3. uv sync --extra all --locked   (hash-verified; pip fallback)
#   4. Symlink ~/.local/bin/hermes -> venv/bin/hermes
#
# The config/SOUL/mcp/cron symlinks into ~/.hermes/ are created separately by
# ../install.sh. Secrets come from the macOS Keychain via bin/hermes
# (secret-shim); this script never creates ~/.hermes/.env.
#
# Deliberately NOT the upstream setup-hermes.sh: that appends a PATH line to
# ~/.zshrc — which is a symlink into this repo — and runs interactive prompts.
#
# To UPDATE later, use `hermes update` (git pull + re-sync), not this script.

set -euo pipefail

REPO_PATH="github.com/NousResearch/hermes-agent"
REPO_URL="https://$REPO_PATH"
PYTHON_VERSION="3.11"

die() {
  echo "error: $*" >&2
  exit 1
}

command -v ghq >/dev/null 2>&1 ||
  die "ghq not found — it is in the Brewfile; run ./install.sh --deps first"
command -v uv >/dev/null 2>&1 ||
  die "uv not found — it is provided by mise; run ./install.sh --deps first"

# Keep uv from discovering unrelated pyproject/uv.toml from a parent dir.
export UV_NO_CONFIG=1

# 1. Clone (only if missing — updates are `hermes update`'s job)
SRC="$(ghq root)/$REPO_PATH"
if [ -d "$SRC/.git" ]; then
  echo "[hermes] source present: $SRC"
else
  echo "[hermes] cloning $REPO_URL ..."
  ghq get "$REPO_URL"
fi

cd "$SRC"

# 2. venv (only if missing)
if [ -x "venv/bin/python" ]; then
  echo "[hermes] venv present ($(venv/bin/python --version 2>&1))"
else
  echo "[hermes] creating venv (Python $PYTHON_VERSION) ..."
  uv venv venv --python "$PYTHON_VERSION"
fi

# 3. Dependencies — idempotent and non-destructive. `uv sync` installs the
# hash-verified locked [all] set; --inexact keeps any extra packages already in
# the venv, so re-runs do NOT prune Hermes' lazily-installed backends (TTS,
# Bedrock, ...) that get added on first use. Fall back to a fresh PyPI resolve
# if the lockfile is stale.
echo "[hermes] installing dependencies (uv sync --extra all) ..."
export VIRTUAL_ENV="$SRC/venv" UV_PROJECT_ENVIRONMENT="$SRC/venv"
uv sync --extra all --locked --inexact ||
  uv pip install -e ".[all]" ||
  uv pip install -e "."

# 4. Symlink into ~/.local/bin (already on PATH via zsh/env.zsh, behind the
# bin/hermes secret-shim). ln -sfn is idempotent.
mkdir -p "$HOME/.local/bin"
ln -sfn "$SRC/venv/bin/hermes" "$HOME/.local/bin/hermes"
echo "[hermes] linked ~/.local/bin/hermes -> $SRC/venv/bin/hermes"

echo "[hermes] done."
echo "[hermes] verify:  hermes --version"
echo "[hermes] symlinks: ../install.sh    (creates ~/.hermes/{config.yaml,SOUL.md,mcp.json,cron})"
echo "[hermes] keys:     secret set OPENROUTER_API_KEY    (injected from the Keychain, no .env)"
