# env.zsh — environment for *every* zsh, including non-interactive `zsh -c`
# (opencode's bash tool, tmux launchers, scripts, CI). install.sh wires it
# up as ~/.zshenv. Keep it fast and side-effect free: PATH and essential
# variables only — prompts, aliases, completions and `mise activate` belong
# in config.zsh (interactive).
#
# -g: this file is also re-sourced from inside a function (config.zsh's
# loader); a plain `typeset` would create a function-local path/PATH there.
typeset -gU path PATH

# Homebrew — prefix-agnostic: prefer per-user ~/.homebrew, else global /opt/homebrew
if [[ -x $HOME/.homebrew/bin/brew ]]; then
  path=($HOME/.homebrew/bin $HOME/.homebrew/sbin $path)
elif [[ -x /opt/homebrew/bin/brew ]]; then
  path=(/opt/homebrew/bin /opt/homebrew/sbin $path)
fi

# mise shims — node/pnpm/python/... for non-interactive shells. Interactive
# shells layer `mise activate` on top (config.zsh), which takes precedence.
path=($HOME/.local/share/mise/shims $path)

# User binaries — ~/.config/bin holds the secret-shim launchers and must
# come first so they wrap the real commands (see functions/secret.md).
path=($HOME/.config/bin $HOME/.local/bin $HOME/bin $HOME/.docker/bin $path)

export PATH

# opencode-claude-auth diagnostics — always on. OpenCode must run on the SUB
# Claude account (craftsamo), but the plugin silently BORROWS another account's
# credentials when the sub cannot be refreshed; on 2026-08-06 that put a
# long-lived `opencode serve` on the Hermes account for two days, undetected.
# The debug log is the only record of it. Tokens are redacted by the plugin's
# own logger, and every process TRUNCATES its log file at init — so the
# long-lived `serve` gets a private path (see tmux/opencode-web.zsh) that
# ad-hoc `opencode` runs on this default path cannot clobber. Audit with:
#   grep refresh_fallback_account ~/.local/share/opencode/claude-auth-*.log
export CLAUDE_AUTH_DEBUG=1

# opencode-claude-auth spoofs the Claude Code client identity on every Anthropic
# request (user-agent "claude-cli/<v> (external, sdk-cli)" plus the cc_version in
# the billing system header). The version is HARDCODED as config.ccVersion in the
# plugin's dist/model-config.js — 2.1.6 pins 2.1.217 — and Anthropic gates newer
# models on a minimum client version, so a stale value fails the request outright:
#   "Claude Code 2.1.217 does not support this model; version 2.1.251 or newer is
#    required" — while `claude --version` here is already well past that floor.
# ANTHROPIC_CLI_VERSION is the plugin's own override and wins over ccVersion in
# BOTH places, so the two stay consistent. Derived from the real Claude Code
# install (~/.local/bin/claude symlinks to versions/<v>, so :A:t IS the version)
# to track updates automatically — pure parameter expansion, no subprocess.
# Upstream 2.2.0 ships ccVersion 2.1.257, but bumping the pinned plugin still
# needs the OAuth-refresh patch re-applied (see opencode.jsonc), so override here.
_cc_bin=$HOME/.local/bin/claude
if [[ -e $_cc_bin ]]; then
  _cc_ver=${_cc_bin:A:t}
  [[ $_cc_ver == <->.<->.<-> ]] && export ANTHROPIC_CLI_VERSION=$_cc_ver
fi
unset _cc_bin _cc_ver
