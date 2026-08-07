#!/usr/bin/env bash
#
# Bootstrap this dotconfig repo.
#
#   ./install.sh          recreate symlinks only (idempotent, offline)
#   ./install.sh --deps   also bootstrap Homebrew (if missing), `brew bundle`,
#                         GitHub CLI extensions and `mise install`
#
# Symlink policy: real files live in this repo; tool dirs (~/.claude, ~/.codex,
# ...) only hold symlinks. This script never overwrites a real file — if a
# tool replaced a link with a regular file it warns and skips instead, so
# re-running it doubles as a drift detector.

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status=0

# GitHub CLI extensions. `gh` has no manifest of its own — the installed set is
# only discoverable via `gh extension list` — so this array is the declaration.
#   github/gh-stack  native stacked pull requests; required by the
#                    git-pullrequest and approach-github-projects skills
GH_EXTENSIONS=(
  github/gh-stack
)

usage() {
  cat <<'EOF'
Usage: ./install.sh [--deps] [--help]

  (no args)  recreate symlinks only (idempotent, offline)
  --deps     additionally bootstrap Homebrew if missing, run `brew bundle`,
             install the declared GitHub CLI extensions, and run `mise install`
  --help     show this help
EOF
}

find_brew() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
    return 0
  fi
  local candidate
  for candidate in "$HOME/.homebrew/bin/brew" /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Idempotent: `gh extension install` errors on an already-installed extension,
# so only install what `gh extension list` does not already report.
install_gh_extensions() {
  local bindir="$1" gh_bin installed ext rc=0
  gh_bin="$bindir/gh"
  [ -x "$gh_bin" ] || gh_bin="$(command -v gh || true)"
  if [ ! -x "$gh_bin" ]; then
    echo "[deps] gh not found — skipping GitHub CLI extensions"
    return 1
  fi
  installed="$("$gh_bin" extension list 2>/dev/null || true)"
  for ext in "${GH_EXTENSIONS[@]}"; do
    if printf '%s\n' "$installed" | grep -qF -- "$ext"; then
      echo "[deps] gh extension $ext already installed"
      continue
    fi
    echo "[deps] gh extension install $ext"
    "$gh_bin" extension install "$ext" || rc=1
  done
  return $rc
}

install_deps() {
  local rc=0
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
    "$brew" bundle --file="$DOTFILES/Brewfile" || rc=1

  # GitHub CLI extensions — `gh` itself comes from the Brewfile above.
  install_gh_extensions "$(dirname "$brew")" || rc=1

  # Language runtimes + global npm CLIs declared in mise/config.toml
  local mise_bin
  mise_bin="$(dirname "$brew")/mise"
  if [ -x "$mise_bin" ]; then
    echo "[deps] mise install (runtimes from mise/config.toml)"
    "$mise_bin" install --yes || rc=1
  else
    echo "[deps] mise not found next to brew — skipping runtime install"
    rc=1
  fi

  return $rc
}

# Populate a real, machine-local skill root with one symlink per repo-curated
# skill (flat: <root>/<name> -> <repo>/agents/curated/<name>). The root is NOT
# a symlink into the repo: it doubles as the install target of third-party
# skill installers (`skills` CLI, `hyperframes skills`), whose writes must
# land machine-local instead of inside the repo. Installer-owned entries are
# left untouched; dangling links into the repo agents/ tree (skill deleted or
# relocated) are pruned.
link_skills_into() {
  local src="$1" root="$2" entry name
  if [ -L "$root" ]; then
    rm "$root"
    echo "  migrated: $root was a symlink — now a real directory"
  fi
  mkdir -p "$root"
  for entry in "$src"/*/; do
    [ -d "$entry" ] || continue
    name="$(basename "$entry")"
    link "${entry%/}" "$root/$name"
  done
  for entry in "$root"/*; do
    [ -L "$entry" ] && [ ! -e "$entry" ] || continue
    case "$(readlink "$entry")" in
      "$DOTFILES"/agents/*)
        rm "$entry"
        echo "  pruned dangling: $entry"
        ;;
    esac
  done
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

# Shared skill root: ~/.agents/skills is the cross-agent convention honored by
# codex, opencode, copilot, grok and gemini (claude reads ~/.claude/skills, so
# that one is bridged to the same dir below). It stays a REAL machine-local
# directory — third-party installers write into it — and repo-curated skills
# are linked in one by one from agents/curated/. The curated tree deliberately
# does NOT live at agents/skills: ~/.config/agents/skills is a registered
# install target of `hyperframes skills` (amp/universal convention), so that
# path is surrendered to tool droppings and git-ignored wholesale. The
# installer's ~/.agents/.skill-lock.json is per-machine update state and
# stays out of the repo, same split as hermes/.
echo "[agents]"
link_skills_into "$DOTFILES/agents/curated" "$HOME/.agents/skills"

echo "[claude]"
link "$DOTFILES/claude/CLAUDE.md"        "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/claude/settings.json"    "$HOME/.claude/settings.json"
link "$DOTFILES/claude/keybindings.json" "$HOME/.claude/keybindings.json"
# Claude Code is the one CLI that does not read ~/.agents/skills, so its skill
# dir is bridged to the shared MUTABLE root, never into the repo: installers
# (`hyperframes skills`) treat ~/.claude/skills as a write target, and their
# cross-CLI symlinks resolve through this path.
link "$HOME/.agents/skills"              "$HOME/.claude/skills"
link "$DOTFILES/claude/agents"           "$HOME/.claude/agents"
link "$DOTFILES/claude/commands"         "$HOME/.claude/commands"

# codex and copilot have no repo-curated skills (both read ~/.agents/skills);
# their ~/.*/skills dirs stay REAL and machine-local so app-seeded content
# (codex skills/.system) and installer droppings never land inside the repo.
echo "[codex]"
link "$DOTFILES/codex/AGENTS.md"   "$HOME/.codex/AGENTS.md"
link "$DOTFILES/codex/prompts"     "$HOME/.codex/prompts"

echo "[copilot]"
link "$DOTFILES/copilot/copilot-instructions.md" "$HOME/.copilot/copilot-instructions.md"
link "$DOTFILES/copilot/mcp-config.json"         "$HOME/.copilot/mcp-config.json"
link "$DOTFILES/copilot/agents"                  "$HOME/.copilot/agents"

echo "[gemini]"
link "$DOTFILES/gemini/settings.json" "$HOME/.gemini/settings.json"
link "$DOTFILES/gemini/GEMINI.md"     "$HOME/.gemini/GEMINI.md"
link "$DOTFILES/gemini/commands"      "$HOME/.gemini/commands"

echo "[grok]"
# config.toml is seeded, not symlinked: the grok CLI atomically rewrites it on
# run (temp file + rename), which would replace a symlink with a real file every
# launch. Seed the repo baseline on first install, then let the CLI own the live
# file — like codex, whose config is likewise app-managed. AGENTS.md holds user
# rules the CLI does not rewrite, so it stays a symlink.
[ -f "$HOME/.grok/config.toml" ] || { mkdir -p "$HOME/.grok"; cp "$DOTFILES/grok/config.toml" "$HOME/.grok/config.toml"; echo "  seeded ~/.grok/config.toml from grok/config.toml (CLI owns it after)"; }
link "$DOTFILES/grok/AGENTS.md"   "$HOME/.grok/AGENTS.md"

echo "[hermes]"
link "$DOTFILES/hermes/config.yaml" "$HOME/.hermes/config.yaml"
# Persona is private/local; seed from the tracked SOUL.example.md when the real
# (gitignored, per-machine) SOUL.md is absent, then symlink it. Never clobbers.
[ -f "$DOTFILES/hermes/SOUL.example.md" ] && [ ! -f "$DOTFILES/hermes/SOUL.md" ] && { cp "$DOTFILES/hermes/SOUL.example.md" "$DOTFILES/hermes/SOUL.md"; echo "  seeded hermes/SOUL.md from template (personalize locally; untracked)"; }
link "$DOTFILES/hermes/SOUL.md"     "$HOME/.hermes/SOUL.md"
link "$DOTFILES/hermes/mcp.json"    "$HOME/.hermes/mcp.json"
link "$DOTFILES/hermes/cron"        "$HOME/.hermes/cron"
link "$DOTFILES/hermes/skills"      "$HOME/.hermes/skills"
# User plugins (e.g. image-gen fallback chains). One shared repo dir, linked
# into the default home here and into every profile home in the loop below
# (plugins are profile-scoped under each profile's HERMES_HOME).
link "$DOTFILES/hermes/plugins"     "$HOME/.hermes/plugins"
# Disable bundled-skill seeding (else the first `hermes` run seeds ~73 skills
# into the symlinked skills dir = this repo). Bundled skills are read in place
# via config.yaml skills.external_dirs instead.
link "$DOTFILES/hermes/.no-bundled-skills" "$HOME/.hermes/.no-bundled-skills"
# Named profiles: link tracked distribution-owned files for each repo profile.
# (Bundled skills are read from the agent clone via skills.external_dirs.)
for p in "$DOTFILES"/hermes/profiles/*/; do
  [ -d "$p" ] || continue
  n="$(basename "$p")"
  [ -f "$p/config.example.yaml" ] && [ ! -f "$p/config.yaml" ] && { cp "$p/config.example.yaml" "$p/config.yaml"; echo "  seeded $n/config.yaml from template (personalize locally; untracked)"; }
  [ -f "$p/config.yaml" ]        && link "$p/config.yaml"        "$HOME/.hermes/profiles/$n/config.yaml"
  [ -f "$p/profile.yaml" ]       && link "$p/profile.yaml"       "$HOME/.hermes/profiles/$n/profile.yaml"
  [ -f "$p/SOUL.example.md" ] && [ ! -f "$p/SOUL.md" ] && { cp "$p/SOUL.example.md" "$p/SOUL.md"; echo "  seeded $n/SOUL.md from template (personalize locally; untracked)"; }
  [ -f "$p/SOUL.md" ]            && link "$p/SOUL.md"            "$HOME/.hermes/profiles/$n/SOUL.md"
  [ -f "$p/mcp.json" ]          && link "$p/mcp.json"          "$HOME/.hermes/profiles/$n/mcp.json"
  [ -d "$p/cron" ]              && link "$p/cron"              "$HOME/.hermes/profiles/$n/cron"
  [ -d "$p/scripts" ]          && link "$p/scripts"          "$HOME/.hermes/profiles/$n/scripts"
  [ -d "$p/skills" ]            && link "$p/skills"            "$HOME/.hermes/profiles/$n/skills"
  [ -f "$p/.no-bundled-skills" ] && link "$p/.no-bundled-skills" "$HOME/.hermes/profiles/$n/.no-bundled-skills"
  # Shared user-plugins dir into each profile home (discovery is HERMES_HOME-scoped).
  [ -d "$DOTFILES/hermes/plugins" ] && link "$DOTFILES/hermes/plugins" "$HOME/.hermes/profiles/$n/plugins"
done

echo "[workspaces]"
# Assistant's terminal.cwd. Symlink the tracked area/ops AGENTS.md (link() creates the
# parent dirs); groups + repos under Projects/ and Personal/ are local, scaffolded on demand.
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
