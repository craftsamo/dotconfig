source ~/.config/zsh/functions/fzf_change_directory.zsh

# Use emacs keymap regardless of $EDITOR (nvim makes zsh default to viins)
bindkey -e

# fzf
zle -N fzf_change_directory
bindkey -M emacs '^F' fzf_change_directory

# Free C-s from terminal flow control (XON/XOFF) so it never freezes the
# terminal (general safety; C-s is otherwise unbound now).
[[ -t 0 ]] && stty -ixon 2>/dev/null

# manage — unified launcher (C-x C-x): pick a tool, then run it as a normal
# command. The choice is pushed to BUFFER + accept-line so secret/wslink run in
# normal command context — their read prompts, secret's keychain (_kc*) setup,
# and wslink's tty guard all behave correctly (calling them inline in a widget
# does not). secret/wslink (functions in secret.zsh / wslink.zsh) are loaded by
# config.zsh before this file.
#
# Bound to a C-x C-x double-tap: C-x alone is undefined in the emacs keymap, so
# using it as the prefix adds no keytimeout penalty to any useful single key.
manage_widget() {
  local choice
  choice=$(printf '%s\n' 'Manage Secret' 'Manage SymbolicLink' \
    | fzf --height=40% --reverse --prompt='manage> ' --header='manage › choose a tool') \
    || { zle reset-prompt; return 0; }
  case "$choice" in
    'Manage Secret')       BUFFER='secret' ;;
    'Manage SymbolicLink') BUFFER='wslink' ;;
    *) zle reset-prompt; return 0 ;;
  esac
  zle accept-line
}
zle -N manage_widget
bindkey -M emacs '^X^X' manage_widget

# vim-like
# bindkey -M emacs '^l' forward-char

# prevent iTerm2 from closing when typing Ctrl-D (EOF)
bindkey -M emacs '^D' delete-char
