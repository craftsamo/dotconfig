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
