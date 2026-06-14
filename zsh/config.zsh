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

# Homebrew — prefix-agnostic: prefer global /opt/homebrew, else per-user ~/.homebrew
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x "$HOME/.homebrew/bin/brew" ]; then
  eval "$("$HOME/.homebrew/bin/brew" shellenv)"
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
