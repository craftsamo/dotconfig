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

# mise directories, pinned to absolute paths (mise's own defaults) and
# exported. A child that swaps HOME for a temp dir (pytest homes, sandboxes)
# keeps PATH, so it still runs these shims, and its cwd's ancestor walk still
# finds ~/.config/mise/config.toml; left to derive its data dir from the new
# HOME, mise sees no installed tool and resolves (and installs) every
# `latest` tool from the network on each shim call. Inherited values win, so
# the pin survives into such children.
: ${MISE_DATA_DIR:=$HOME/.local/share/mise}
: ${MISE_CONFIG_DIR:=$HOME/.config/mise}
: ${MISE_STATE_DIR:=$HOME/.local/state/mise}
if [[ $OSTYPE == darwin* ]]; then
  : ${MISE_CACHE_DIR:=$HOME/Library/Caches/mise}
else
  : ${MISE_CACHE_DIR:=$HOME/.cache/mise}
fi
export MISE_DATA_DIR MISE_CONFIG_DIR MISE_STATE_DIR MISE_CACHE_DIR

# mise shims — node/pnpm/python/... for non-interactive shells. Interactive
# shells layer `mise activate` on top (config.zsh), which takes precedence.
path=($MISE_DATA_DIR/shims $path)

# User binaries — ~/.config/bin holds the secret-shim launchers and must
# come first so they wrap the real commands (see functions/secret.md).
path=($HOME/.config/bin $HOME/.local/bin $HOME/bin $HOME/.docker/bin $path)

export PATH
