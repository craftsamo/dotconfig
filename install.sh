#!/usr/bin/env bash
#
# Bootstrap this dotconfig repo.
#
#   ./install.sh          recreate symlinks only (idempotent, offline)
#   ./install.sh --deps   also bootstrap Homebrew (if missing), `brew bundle`,
#                         GitHub CLI extensions, `mise install` and the
#                         OpenCode plugin dependencies (opencode/package.json)
#
# Symlink policy: real files live in this repo (a ghq checkout); ~/.config and
# the tool dirs (~/.claude, ~/.codex, ...) only hold symlinks. Each tracked
# top-level directory here becomes ~/.config/<name>, so XDG-native tools find
# it there while tools that write their own state into ~/.config stay outside
# the repository. This script never overwrites a real file — if a tool
# replaced a link with a regular file it warns and skips instead, so
# re-running it doubles as a drift detector.

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
XDG_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
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
    # OpenCode 2 does not install config-directory dependencies; the
    # custom-tools plugin imports zod from opencode/node_modules.
    echo "[deps] npm install (opencode/package.json)"
    "$mise_bin" exec -- npm install --prefix "$DOTFILES/opencode" --no-audit --no-fund || rc=1
    # The web_ui_check tool drives Playwright's headless shell; npm does not
    # download browsers.
    echo "[deps] playwright install chromium-headless-shell (web_ui_check)"
    "$mise_bin" exec -- "$DOTFILES/opencode/node_modules/.bin/playwright" install chromium-headless-shell || rc=1
  else
    echo "[deps] mise not found next to brew — skipping runtime install"
    rc=1
  fi

  return $rc
}

# Populate a real, machine-local skill root with one symlink per repo-curated
# skill (flat: <root>/<name> -> <repo>/agents/skills/<name>). The root is NOT
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

# Claude Code's skill dir stays a REAL machine-local directory holding one
# link per shared skill, not a link to the whole shared root: Claude Code
# syncs claude.ai skills into its own skills/synced/ (and retires them to
# skills/.trash/), and those need the Claude app's tools, so they must not
# surface in the shared root that every other CLI reads. Entries an installer
# copied in for real (`hyperframes skills` passes --copy) are left alone, and
# links whose shared skill disappeared are pruned. Older checkouts bridged the
# whole dir; that link is replaced and Claude Code's sync state moved back.
bridge_claude_skills() {
  local shared="$1" dest="$2" entry name
  if [ -L "$dest" ]; then
    rm "$dest"
    mkdir -p "$dest"
    for name in synced .trash; do
      if [ -e "$shared/$name" ]; then
        mv "$shared/$name" "$dest/$name" || status=1
      fi
    done
    echo "  migrated: $dest was a link to the shared root — now a real directory"
  fi
  mkdir -p "$dest"
  for entry in "$shared"/*/; do
    [ -d "$entry" ] || continue
    name="$(basename "$entry")"
    [ "$name" = synced ] && continue
    if [ -e "$dest/$name" ] && [ ! -L "$dest/$name" ]; then
      continue
    fi
    ln -sfn "$shared/$name" "$dest/$name"
  done
  echo "  ok: $dest -> per-skill links into $shared"
  for entry in "$dest"/*; do
    [ -L "$entry" ] && [ ! -e "$entry" ] || continue
    case "$(readlink "$entry")" in
      "$shared"/*)
        rm "$entry"
        echo "  pruned dangling: $entry"
        ;;
    esac
  done
}

# Turn a whole-directory link into the repo (<dest> -> <repo>/<rel>) into a
# real machine-local directory, moving every entry at <repo>/<rel> that Git
# neither tracks nor ignores — the state the tool wrote through the link —
# out of the repository into it. Tracked entries stay where they are; the
# caller links or copies them back. Ignored entries stay too: they are what
# the repo's own commands produce (node_modules, lock files, engine venvs)
# and belong beside their source. Dangling links (installer droppings written
# relative to the repo) are dropped and __pycache__ is left to be
# regenerated. A dest that is already a directory, or a link elsewhere, is
# left alone.
#
# Hermes' cron directory was the first case: it writes jobs.json, output/,
# executions.db and the locks into it, and a missing jobs.json reads as ZERO
# jobs, silently — so the state moves before the link goes, never after.
adopt_dir() {
  local dest="$1" target rel e name entries=()
  [ -L "$dest" ] || return 0
  target="$(readlink "$dest")"
  case "$target" in
    "$DOTFILES"/*) ;;
    *) return 0 ;;
  esac
  rel="${target#"$DOTFILES"/}"
  if [ -d "$target" ]; then
    while IFS= read -r -d '' e; do
      name="$(basename "$e")"
      [ "$name" = __pycache__ ] && continue
      if [ -L "$e" ] && [ ! -e "$e" ]; then
        rm "$e"
        echo "  dropped dangling: $e"
        continue
      fi
      [ -n "$(git -C "$DOTFILES" ls-files -- "$rel/$name")" ] && continue
      git -C "$DOTFILES" check-ignore -q -- "$rel/$name" && continue
      entries+=("$e")
    done < <(find "$target" -mindepth 1 -maxdepth 1 -print0)
  fi
  mkdir -p "$dest.new" || { echo "ERROR: cannot stage $dest.new"; status=1; return; }
  if [ ${#entries[@]} -gt 0 ] && ! mv "${entries[@]}" "$dest.new"/; then
    echo "ERROR: failed to move machine-local entries out of $target — left untouched"
    rmdir "$dest.new" 2>/dev/null
    status=1
    return
  fi
  rm "$dest"
  mv "$dest.new" "$dest"
  echo "  migrated: $dest is now a real directory (${#entries[@]} machine-local entries left the repo)"
}

# <dest> as a real directory holding a COPY of every tracked file under
# <repo>/<rel>. For the one place a link cannot serve: Hermes' cron scheduler
# resolves a job's script and the profile's scripts/ directory to their real
# paths and refuses a script outside that directory, so a linked script would
# resolve into the repo while the directory stays in HOME. The repo is the
# source: a copy that differs is overwritten (edits in HOME are lost; edit
# here), and the files the tool and the overlay write beside them (adhoc/,
# generated wrappers) are untouched.
copy_entries() {
  local rel="$1" dest="$2" file
  adopt_dir "$dest"
  if [ -e "$dest" ] && [ ! -d "$dest" ]; then
    echo "WARN: $dest exists and is not a directory — not touching"
    status=1
    return
  fi
  mkdir -p "$dest"
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    if [ -f "$dest/$file" ] && cmp -s "$DOTFILES/$rel/$file" "$dest/$file" \
       && [ "$(stat -f %p "$DOTFILES/$rel/$file")" = "$(stat -f %p "$dest/$file")" ]; then
      continue
    fi
    mkdir -p "$(dirname "$dest/$file")"
    cp -p "$DOTFILES/$rel/$file" "$dest/$file"
    echo "  copied: $dest/$file (from $rel/$file)"
  done < <(git -C "$DOTFILES" ls-files -z -- "$rel" | tr '\0' '\n' | sed "s#^$rel/##")
  echo "  ok: $dest = copies of $rel/ (the repo is the source)"
}

# <dest>: a file the person or the private overlay owns at a HOME path, never
# a link through this repo. Without the overlay it is seeded once from the
# tracked <example> (when one exists). An earlier run linked it through the
# repo (<dest> -> <repo>/<rel> -> overlay, or a seed left at <repo>/<rel>):
# the link is re-pointed at the file itself and the repo path emptied.
seed_or_adopt() {
  local dest="$1" repo_path="$DOTFILES/$2" example="$DOTFILES/$3" real
  # Earlier runs wrote the link with a doubled slash (<profile dir>//<file>).
  if [ -L "$dest" ] && [ "$(readlink "$dest" | sed 's#//*#/#g')" = "$repo_path" ]; then
    if [ -L "$repo_path" ] && real="$(realpath "$repo_path" 2>/dev/null)"; then
      ln -sfn "$real" "$dest"
      rm "$repo_path"
      echo "  migrated: $dest -> $real (no longer through the repo)"
    elif [ -L "$repo_path" ]; then
      rm "$dest" "$repo_path"
      echo "  dropped: $dest and $repo_path (a dangling overlay link)"
    elif [ -f "$repo_path" ]; then
      rm "$dest"
      mv "$repo_path" "$dest"
      echo "  migrated: $dest is the file itself (left the repo)"
    else
      rm "$dest"
    fi
  fi
  if [ ! -e "$dest" ] && [ ! -L "$dest" ] && [ -f "$example" ]; then
    mkdir -p "$(dirname "$dest")"
    cp "$example" "$dest"
    echo "  seeded $dest from $(basename "$example") (yours to edit; an untouched seed yields to the private overlay)"
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

# ~/.config/<name> -> <repo>/<name> for every tracked top-level directory. The
# set comes from the index, so a new managed tool needs no line here: commit
# its directory and re-run. Linking per directory (not the whole repo) keeps
# the state other tools write into ~/.config (gh, gcloud, ...) out of the
# repository and out of reach of `git clean`. A checkout that IS ~/.config
# (the pre-ghq layout) is left alone.
#
# The invariant: links point from HOME into the repo, never the other way,
# and a tool that writes its own files does so beside a link, never through
# one into the repo. The exceptions to the one-link-per-directory rule follow
# from it (here for ~/.config, and again for ~/.hermes below).
#
# Not linked: directories nothing reads at ~/.config/<name>. agents/ is the
# repo-curated shared skill tree, wired below into ~/.agents/skills; the path
# ~/.config/agents/skills is only an install target of `hyperframes skills`
# (amp/universal convention), whose relative links would dangle inside a
# linked directory, so it stays a plain machine-local directory.
CONFIG_UNLINKED=(agents)
# Linked per entry: a tool writes its own state into this directory (opencode
# keeps service.json there; `hyperframes skills` mirrors its store into
# opencode/skills with relative links; Hermes writes learned skills, usage
# and hub bookkeeping into its skill roots and bytecode beside its plugins).
# The HOME directory is a REAL machine-local one and each tracked entry of
# <repo>/<rel> is linked into it, so the tool's files land beside the links,
# outside the repository. A nested path listed here gets the same treatment
# inside its parent. The Hermes roots are appended in "[hermes]".
ENTRY_ROOTS=(opencode opencode/skills)
# Seeded, not linked: the tool rewrites the file by temp file + rename, which
# would replace a link with a real file on the first change (same as grok's
# config.toml). Copied from the repo once; the tool owns it after.
SEEDED=(opencode/cli.json)

in_list() {
  local needle="$1"
  shift
  printf '%s\n' "$@" | grep -qx -- "$needle"
}

# <dest> as a real directory holding one link per tracked entry of
# <repo>/<rel>. A link left at <dest> by an earlier run (whole-directory
# mode) is replaced by the directory, with the tool's state moved into it.
link_entries() {
  local rel="$1" dest="$2" child
  adopt_dir "$dest"
  if [ -e "$dest" ] && [ ! -d "$dest" ]; then
    echo "WARN: $dest exists and is not a directory — not touching"
    status=1
    return
  fi
  mkdir -p "$dest"
  while IFS= read -r child; do
    [ -n "$child" ] || continue
    if in_list "$rel/$child" "${ENTRY_ROOTS[@]}"; then
      link_entries "$rel/$child" "$dest/$child"
    elif in_list "$rel/$child" "${SEEDED[@]}"; then
      [ -e "$dest/$child" ] || { cp "$DOTFILES/$rel/$child" "$dest/$child"; echo "  seeded $dest/$child from the repo (the tool owns it after)"; }
    else
      link "$DOTFILES/$rel/$child" "$dest/$child"
    fi
  done < <(git -C "$DOTFILES" ls-files -z -- "$rel" | tr '\0' '\n' | sed "s#^$rel/##" | cut -d/ -f1 | sort -u)
}

echo "[config]"
if [ "$(cd "$XDG_CONFIG" 2>/dev/null && pwd -P)" = "$DOTFILES" ]; then
  echo "  skipped: $DOTFILES is $XDG_CONFIG itself"
else
  mkdir -p "$XDG_CONFIG"
  while IFS= read -r name; do
    [ -d "$DOTFILES/$name" ] || continue
    if in_list "$name" "${CONFIG_UNLINKED[@]}"; then
      # Drop a link an earlier run made before the name was excluded.
      if [ -L "$XDG_CONFIG/$name" ] && [ "$(readlink "$XDG_CONFIG/$name")" = "$DOTFILES/$name" ]; then
        rm "$XDG_CONFIG/$name"
        echo "  unlinked: $XDG_CONFIG/$name (not a config directory)"
      fi
    elif in_list "$name" "${ENTRY_ROOTS[@]}"; then
      link_entries "$name" "$XDG_CONFIG/$name"
    else
      link "$DOTFILES/$name" "$XDG_CONFIG/$name"
    fi
  done < <(git -C "$DOTFILES" ls-files -z | tr '\0' '\n' | grep / | cut -d/ -f1 | sort -u)
  # Untracked but repo-produced: `--deps` installs the plugin dependencies
  # into <repo>/opencode/node_modules (the plugins resolve imports from their
  # real path, so that copy is the one that counts); mirrored for anything
  # that looks them up through the config directory.
  [ -d "$DOTFILES/opencode/node_modules" ] && link "$DOTFILES/opencode/node_modules" "$XDG_CONFIG/opencode/node_modules"
fi

# Shared skill root: ~/.agents/skills is the cross-agent convention honored by
# codex, opencode, copilot, grok and gemini (claude reads ~/.claude/skills, so
# each shared skill is linked into it below). It stays a REAL machine-local
# directory — third-party installers write into it — and repo-curated skills
# are linked in one by one from agents/skills/. The installer's
# ~/.agents/.skill-lock.json is per-machine update state and stays out of the
# repo, same split as hermes/.
echo "[agents]"
link_skills_into "$DOTFILES/agents/skills" "$HOME/.agents/skills"

echo "[claude]"
link "$DOTFILES/claude/CLAUDE.md"        "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/claude/settings.json"    "$HOME/.claude/settings.json"
link "$DOTFILES/claude/keybindings.json" "$HOME/.claude/keybindings.json"
# Claude Code is the one CLI that does not read ~/.agents/skills, so each
# shared skill is linked into its skill dir — pointing at the shared MUTABLE
# root, never into the repo: installers (`hyperframes skills`) treat
# ~/.claude/skills as a write target, and their cross-CLI symlinks resolve
# through this path.
bridge_claude_skills "$HOME/.agents/skills" "$HOME/.claude/skills"
# ~/.claude/agents is machine-local, NOT linked: app installers (e.g. tldraw
# Desktop) replace the symlink with a real dir and drop subagent files into
# it, so a repo link only produces recurring drift warnings.
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
# ~/.hermes and every profile home are Hermes' own directories: real,
# machine-local, holding its runtime state (auth, sessions, memories, cron)
# beside one link per tracked file of hermes/. The same invariant as
# "[config]", with the same exceptions:
#
#   * Entry roots. Hermes writes into its skill roots (learned skills, usage
#     and hub bookkeeping, seeded categories) and bytecode beside its plugins,
#     so skills/, plugins/ and each plugin group are real directories of
#     links. Plugins are addressed as <group>/<name>, so a group is a
#     directory of links to plugins; a top-level entry that is not a group
#     (_shared/ code, a flat plugin) is linked whole.
#   * Copied, not linked: a profile's scripts/ (cron's real-path rule; see
#     copy_entries). The wrappers the overlay generates and the adhoc/ scripts
#     a profile writes for itself land beside the copies.
#   * Owned at HOME, never linked through the repo: config.yaml and SOUL.md
#     (the private overlay links its own straight into ~/.hermes; without it
#     they are seeded from the tracked examples). Hermes rewrites config.yaml
#     on load, so these must never be a path inside the repository.
#
# Bundled-skill seeding stays off (.no-bundled-skills): the first `hermes` run
# would otherwise seed ~73 skills into every skill root. Bundled skills are
# read in place via config.yaml skills.external_dirs instead.
ENTRY_ROOTS+=(hermes/skills hermes/plugins)
while IFS= read -r g; do
  [ -d "$DOTFILES/hermes/plugins/$g" ] || continue
  case "$g" in _*) continue ;; esac
  [ -f "$DOTFILES/hermes/plugins/$g/plugin.yaml" ] || ENTRY_ROOTS+=("hermes/plugins/$g")
done < <(git -C "$DOTFILES" ls-files -z -- hermes/plugins | tr '\0' '\n' | cut -d/ -f3 | sort -u)
for p in "$DOTFILES"/hermes/profiles/*/; do
  [ -d "$p/skills" ] && ENTRY_ROOTS+=("hermes/profiles/$(basename "$p")/skills")
done

seed_or_adopt "$HOME/.hermes/config.yaml" hermes/config.yaml hermes/config.example.yaml
seed_or_adopt "$HOME/.hermes/SOUL.md"     hermes/SOUL.md     hermes/SOUL.example.md
link "$DOTFILES/hermes/mcp.json" "$HOME/.hermes/mcp.json"
adopt_dir "$HOME/.hermes/cron"
link_entries hermes/skills  "$HOME/.hermes/skills"
link_entries hermes/plugins "$HOME/.hermes/plugins"
link "$DOTFILES/hermes/.no-bundled-skills" "$HOME/.hermes/.no-bundled-skills"
# Named profiles: the same pieces per profile home. Plugin discovery is
# HERMES_HOME-scoped, so each profile links the one plugin tree above.
for p in "$DOTFILES"/hermes/profiles/*/; do
  [ -d "$p" ] || continue
  p="${p%/}"
  n="$(basename "$p")"
  h="$HOME/.hermes/profiles/$n"
  seed_or_adopt "$h/config.yaml" "hermes/profiles/$n/config.yaml" "hermes/profiles/$n/config.example.yaml"
  seed_or_adopt "$h/SOUL.md"     "hermes/profiles/$n/SOUL.md"     "hermes/profiles/$n/SOUL.example.md"
  [ -f "$p/profile.yaml" ] && link "$p/profile.yaml" "$h/profile.yaml"
  [ -f "$p/mcp.json" ]     && link "$p/mcp.json"     "$h/mcp.json"
  adopt_dir "$h/cron"
  [ -d "$p/scripts" ] && copy_entries "hermes/profiles/$n/scripts" "$h/scripts"
  [ -d "$p/skills" ]  && link_entries "hermes/profiles/$n/skills" "$h/skills"
  [ -f "$p/.no-bundled-skills" ] && link "$p/.no-bundled-skills" "$h/.no-bundled-skills"
  link "$HOME/.hermes/plugins" "$h/plugins"
done

# (no [workspaces] section: the ~/Workspaces AGENTS.md doctrine is personal
# and lives in the private overlay, whose install.sh links it into place.)

echo "[zsh]"
link "$DOTFILES/zsh/env.zsh"    "$HOME/.zshenv"
link "$DOTFILES/zsh/config.zsh" "$HOME/.zshrc"

# Private overlay (craftsamo/private-dotconfig): a sibling ghq checkout with
# an install.sh of its own that links its files straight into ~/.hermes and
# ~/.config beside the links above — never into this tree. Run after this
# one when present; absent on clones without access, and skipping is the
# supported path. The link ./private earlier layouts kept here is dropped.
if [ -L "$DOTFILES/private" ]; then
  rm "$DOTFILES/private"
  echo "  dropped: $DOTFILES/private (the overlay is no longer reached through this tree)"
fi
PRIVATE_DOTCONFIG="${PRIVATE_DOTCONFIG:-$(dirname "$DOTFILES")/private-dotconfig}"
if [ -x "$PRIVATE_DOTCONFIG/install.sh" ]; then
  echo "[private overlay]"
  DOTCONFIG="$DOTFILES" "$PRIVATE_DOTCONFIG/install.sh" || status=1
fi

exit $status
