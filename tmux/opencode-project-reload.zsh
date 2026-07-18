#!/bin/zsh -f

emulate -L zsh
setopt pipefail

readonly server=http://127.0.0.1:4096

notify() {
  print -r -- "$1"
  [[ -n ${TMUX:-} ]] && tmux display-message -d 5000 "$1"
}

fail() {
  notify "OpenCode project reload failed: $1"
  exit 1
}

uri_encode() {
  emulate -L zsh
  local LC_ALL=C value=$1 encoded="" char byte
  integer i

  for (( i = 1; i <= ${#value}; i++ )); do
    char=$value[i]
    if [[ $char == [A-Za-z0-9._~-] ]]; then
      encoded+=$char
    else
      printf -v byte '%%%02X' "'$char"
      encoded+=$byte
    fi
  done
  print -rn -- "$encoded"
}

[[ $# == 1 && -d $1 ]] || fail "project directory not found"
readonly directory=${1:A}
[[ $directory != *$'\r'* && $directory != *$'\n'* ]] ||
  fail "project directory contains an unsupported newline"
# The v1.18.1 workspace router decodes header values once.
readonly routed_directory=$(uri_encode "$directory") ||
  fail "could not encode project directory"

"$HOME/.config/tmux/opencode-web.zsh" || fail "shared server is unavailable"

# Match the opencode secret shim's global -> tool-specific precedence while
# preserving credentials explicitly inherited by this process.
typeset inherited_username=${OPENCODE_SERVER_USERNAME-}
typeset inherited_password=${OPENCODE_SERVER_PASSWORD-}
typeset had_username=${+OPENCODE_SERVER_USERNAME}
typeset had_password=${+OPENCODE_SERVER_PASSWORD}

for layer in global opencode; do
  exports=$("$HOME/.config/bin/secret" env -p "$layer" 2>/dev/null) ||
    fail "could not load Keychain credentials"
  eval "$exports"
done

(( had_username )) && OPENCODE_SERVER_USERNAME=$inherited_username
(( had_password )) && OPENCODE_SERVER_PASSWORD=$inherited_password

[[ -n ${OPENCODE_SERVER_PASSWORD:-} ]] || fail "server password is unavailable"
readonly username=${OPENCODE_SERVER_USERNAME-opencode}
readonly authorization=$(print -rn -- "$username:$OPENCODE_SERVER_PASSWORD" | /usr/bin/base64) ||
  fail "could not prepare server credentials"

request() {
  local method=$1
  local endpoint=$2

  print -r -- "header = \"Authorization: Basic $authorization\"" |
    /usr/bin/curl --config - --silent --show-error --fail \
      --request "$method" --header "x-opencode-directory: $routed_directory" "$server$endpoint"
}

session_status=$(request GET /session/status) || fail "could not check project activity"
readonly active_status='"type"[[:space:]]*:[[:space:]]*"(busy|retry)"'
[[ $session_status =~ $active_status ]] && fail "project has a running session"

response=$(request POST /instance/dispose) || fail "server rejected the reload request"

[[ $response == true ]] || fail "unexpected server response"
notify "Reloaded OpenCode project: $directory"
