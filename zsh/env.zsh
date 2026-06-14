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
