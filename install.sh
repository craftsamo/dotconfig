#!/usr/bin/env bash
#
# Bootstrap this dotfiles repo.
#
#   ./install.sh          recreate symlinks only (idempotent, offline)
#   ./install.sh --deps   also bootstrap Homebrew (if missing) + `brew bundle`
#
# Symlink policy: real files live in this repo; tool dirs (~/.claude, ~/.codex,
# ...) only hold symlinks. This script never overwrites a real file — if a
# tool replaced a link with a regular file it warns and skips instead, so
# re-running it doubles as a drift detector.

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--deps] [--help]

  (no args)  recreate symlinks only (idempotent, offline)
  --deps     additionally bootstrap Homebrew if missing and run `brew bundle`
  --help     show this help
EOF
}

find_brew() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
    return 0
  fi
  local candidate
  for candidate in /opt/homebrew/bin/brew "$HOME/.homebrew/bin/brew" /usr/local/bin/brew; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

install_deps() {
  local brew
  if ! brew="$(find_brew)"; then
    echo "[deps] Homebrew not found — installing per-user into ~/.homebrew"
    mkdir -p "$HOME/.homebrew"
    curl -fsSL https://github.com/Homebrew/brew/tarball/master |
      tar xz --strip-components 1 -C "$HOME/.homebrew"
    brew="$HOME/.homebrew/bin/brew"
  fi
  echo "[deps] using $brew"
  # --adopt: take ownership of manually installed apps instead of failing.
  # NO_UPGRADE: only install what's missing; never upgrade behind your back.
  HOMEBREW_CASK_OPTS="--adopt" HOMEBREW_BUNDLE_NO_UPGRADE=1 \
    "$brew" bundle --file="$DOTFILES/Brewfile"

  # Language runtimes + global npm CLIs declared in mise/config.toml
  local mise_bin
  mise_bin="$(dirname "$brew")/mise"
  if [ -x "$mise_bin" ]; then
    echo "[deps] mise install (runtimes from mise/config.toml)"
    "$mise_bin" install --yes
  else
    echo "[deps] mise not found next to brew — skipping runtime install"
    return 1
  fi
}

link() {
  local target="$1" dest="$2"
  if [ ! -e "$target" ]; then
    echo "SKIP: missing target: $target"
    status=1
    return
  fi
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "WARN: $dest exists and is not a symlink — not overwriting (drift?)"
    status=1
    return
  fi
  mkdir -p "$(dirname "$dest")"
  ln -sfn "$target" "$dest"
  echo "  ok: $dest -> $target"
}

deps=0
for arg in "$@"; do
  case "$arg" in
    --deps) deps=1 ;;
    --help | -h)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# A bundle failure should not stop the symlink phase; surface it via exit code.
if [ "$deps" = 1 ]; then
  install_deps || status=1
fi

echo "[claude]"
link "$DOTFILES/claude/CLAUDE.md"        "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/claude/settings.json"    "$HOME/.claude/settings.json"
link "$DOTFILES/claude/keybindings.json" "$HOME/.claude/keybindings.json"
link "$DOTFILES/claude/skills"           "$HOME/.claude/skills"
link "$DOTFILES/claude/agents"           "$HOME/.claude/agents"
link "$DOTFILES/claude/commands"         "$HOME/.claude/commands"

echo "[codex]"
link "$DOTFILES/codex/AGENTS.md"   "$HOME/.codex/AGENTS.md"
link "$DOTFILES/codex/prompts"     "$HOME/.codex/prompts"
link "$DOTFILES/codex/skills"      "$HOME/.codex/skills"

echo "[copilot]"
link "$DOTFILES/copilot/copilot-instructions.md" "$HOME/.copilot/copilot-instructions.md"
link "$DOTFILES/copilot/mcp-config.json"         "$HOME/.copilot/mcp-config.json"
link "$DOTFILES/copilot/agents"                  "$HOME/.copilot/agents"
link "$DOTFILES/copilot/skills"                  "$HOME/.copilot/skills"

echo "[gemini]"
link "$DOTFILES/gemini/settings.json" "$HOME/.gemini/settings.json"
link "$DOTFILES/gemini/GEMINI.md"     "$HOME/.gemini/GEMINI.md"
link "$DOTFILES/gemini/commands"      "$HOME/.gemini/commands"

echo "[hermes]"
link "$DOTFILES/hermes/config.yaml" "$HOME/.hermes/config.yaml"
link "$DOTFILES/hermes/SOUL.md"     "$HOME/.hermes/SOUL.md"
link "$DOTFILES/hermes/mcp.json"    "$HOME/.hermes/mcp.json"
link "$DOTFILES/hermes/cron"        "$HOME/.hermes/cron"
link "$DOTFILES/hermes/skills"      "$HOME/.hermes/skills"
# Disable bundled-skill seeding (else the first `hermes` run seeds ~73 skills
# into the symlinked skills dir = this repo). Bundled skills are read in place
# via config.yaml skills.external_dirs instead.
link "$DOTFILES/hermes/.no-bundled-skills" "$HOME/.hermes/.no-bundled-skills"
# Named profiles: link tracked distribution-owned files for each repo profile.
# (Bundled skills are read from the agent clone via skills.external_dirs.)
for p in "$DOTFILES"/hermes/profiles/*/; do
  [ -d "$p" ] || continue
  n="$(basename "$p")"
  [ -f "$p/config.yaml" ]        && link "$p/config.yaml"        "$HOME/.hermes/profiles/$n/config.yaml"
  [ -f "$p/profile.yaml" ]       && link "$p/profile.yaml"       "$HOME/.hermes/profiles/$n/profile.yaml"
  [ -f "$p/SOUL.md" ]            && link "$p/SOUL.md"            "$HOME/.hermes/profiles/$n/SOUL.md"
  [ -f "$p/mcp.json" ]          && link "$p/mcp.json"          "$HOME/.hermes/profiles/$n/mcp.json"
  [ -d "$p/cron" ]              && link "$p/cron"              "$HOME/.hermes/profiles/$n/cron"
  [ -d "$p/skills" ]            && link "$p/skills"            "$HOME/.hermes/profiles/$n/skills"
  [ -f "$p/.no-bundled-skills" ] && link "$p/.no-bundled-skills" "$HOME/.hermes/profiles/$n/.no-bundled-skills"
done

echo "[workspaces]"
# Assistant's terminal.cwd. Symlink the tracked area/ops AGENTS.md (link() creates the
# parent dirs); groups + repos under Projects/Personal are local, scaffolded on demand.
link "$DOTFILES/workspaces/AGENTS.md"               "$HOME/Workspaces/AGENTS.md"
link "$DOTFILES/workspaces/Projects/AGENTS.md"      "$HOME/Workspaces/Projects/AGENTS.md"
link "$DOTFILES/workspaces/Personal/AGENTS.md"      "$HOME/Workspaces/Personal/AGENTS.md"
link "$DOTFILES/workspaces/.scratch/AGENTS.md"      "$HOME/Workspaces/.scratch/AGENTS.md"
link "$DOTFILES/workspaces/.deliverables/AGENTS.md" "$HOME/Workspaces/.deliverables/AGENTS.md"
link "$DOTFILES/workspaces/.notes/AGENTS.md"        "$HOME/Workspaces/.notes/AGENTS.md"
link "$DOTFILES/workspaces/.inbox/AGENTS.md"        "$HOME/Workspaces/.inbox/AGENTS.md"

echo "[zsh]"
link "$DOTFILES/zsh/env.zsh"    "$HOME/.zshenv"
link "$DOTFILES/zsh/config.zsh" "$HOME/.zshrc"

exit $status
