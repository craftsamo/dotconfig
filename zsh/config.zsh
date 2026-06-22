setopt interactivecomments

export TERM=screen-256color

# Aliases
alias ls="ls -p --color=auto"
alias la="ls -A"
alias ll="ls -l"
alias lla="ll -A"
alias g="git"

# Neovim
command -v nvim >/dev/null && alias vim=nvim

export EDITOR=nvim

# Homebrew — prefix-agnostic: prefer per-user ~/.homebrew, else global /opt/homebrew
if [ -x "$HOME/.homebrew/bin/brew" ]; then
  eval "$("$HOME/.homebrew/bin/brew" shellenv)"
elif [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# mise — language runtimes (node, python, ...) declared in mise/config.toml
command -v mise >/dev/null && eval "$(mise activate zsh)"

# PATH (user bins, secret-shim launchers, mise shims, brew prefix) is built
# in env.zsh — wired as ~/.zshenv so non-interactive shells get it too.

setopt magic_equal_subst

# Load all .zsh files from a specified directory
load_files_in_directory() {
  local directory="$1"
  local extension="$2"

  if [ -d "$directory" ]; then
    for file in "$directory"/*.$extension; do
      if [ -f "$file" ] && [ "$file" != "$HOME/.config/zsh/config.zsh" ]; then
        source "$file"
      fi
    done
  fi
}

load_files_in_directory "$HOME/.config/zsh/conf.d" "zsh"
load_files_in_directory "$HOME/.config/zsh/functions" "zsh"
load_files_in_directory "$HOME/.config/zsh" "zsh"

# Keep ~/.config/bin (secret-shim launchers) ahead of mise/brew install dirs.
# `mise activate` (and `brew shellenv`) prepend their own bin dirs to PATH on
# startup and again via mise's precmd/chpwd hooks, which would otherwise
# shadow the secret-shim launchers in ~/.config/bin and bypass Keychain env
# injection for node/npx/pnpm/... in interactive shells. Re-assert the user
# bins after mise's hooks — on precmd (every prompt) and chpwd (so a compound
# `cd sub && node ...` still hits the shim) — so the shims win (env.zsh
# documents that ~/.config/bin "must come first"). `path` is `typeset -U`, so
# this just moves them to the front and dedupes.
_prioritize_user_bins() {
  path=($HOME/.config/bin $HOME/.local/bin $HOME/bin $HOME/.docker/bin $path)
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _prioritize_user_bins
add-zsh-hook chpwd _prioritize_user_bins
