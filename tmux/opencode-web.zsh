#!/bin/zsh -f

emulate -L zsh

readonly session=opencode-web
readonly url=http://127.0.0.1:4096/
readonly log=$HOME/Library/Logs/opencode-web.log

if ! tmux has-session -t "$session" 2>/dev/null; then
  mkdir -p "${log:h}"
  # Private opencode-claude-auth log: the plugin truncates its log file on every
  # process init, so sharing the default path with ad-hoc `opencode` runs would
  # erase this long-lived server's record of a silent account borrow. Exported
  # inside the command string because tmux does not forward the client env.
  readonly auth_log=$HOME/.local/share/opencode/claude-auth-serve.log
  command="export CLAUDE_AUTH_DEBUG=\"$auth_log\"; exec \"$HOME/.config/bin/opencode\" serve --hostname 127.0.0.1 --port 4096 >\"$log\" 2>&1"
  tmux new-session -d -s "$session" -c "$HOME" "$command" 2>/dev/null ||
    tmux has-session -t "$session" 2>/dev/null || exit 1
fi

for attempt in {1..20}; do
  if tmux has-session -t "$session" 2>/dev/null; then
    http_status=$(curl -sS -o /dev/null -w '%{http_code}' \
      --connect-timeout 0.2 --max-time 0.5 "$url" 2>/dev/null)
    [[ $http_status == 401 ]] && exit 0
  fi
  sleep 0.1
done

tmux display-message -d 5000 \
  "OpenCode web failed; check $log"
exit 1
