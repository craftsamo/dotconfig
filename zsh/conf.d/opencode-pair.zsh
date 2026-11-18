# `opencode pair` prints one-time links that point at 127.0.0.1, which other
# tailnet devices cannot reach. This wrapper adds `--url` with this machine's
# Tailscale Serve URL when Serve proxies to the OpenCode server; otherwise the
# plain local links are printed.

# Prints the Tailscale Serve URL that proxies to the OpenCode server and
# returns 0, or returns 1 printing nothing.
_opencode_pair_tailscale_url() {
  (( $+commands[tailscale] && $+commands[jq] )) || return 1
  local server json url
  server=$(command opencode service status 2>/dev/null) || return 1
  server=${server%%$'\n'*}
  [[ $server == http://* ]] || return 1
  server=${server%/}
  json=$(command tailscale serve status --json 2>/dev/null) || return 1
  url=$(print -r -- "$json" | jq -r --arg server "$server" '
    def norm: sub("/$"; "") | sub("//localhost:"; "//127.0.0.1:");
    (.TCP // {}) as $tcp
    | [ (.Web // {}) | to_entries[]
        | (.key | capture("^(?<host>.+):(?<port>[0-9]+)$"))? as $hp
        | select(((.value.Handlers["/"].Proxy // "") | norm) == ($server | norm))
        | ($tcp[$hp.port] // {}) as $t
        | (if $t.HTTPS == true then "https" elif $t.HTTP == true then "http" else empty end) as $scheme
        | $scheme + "://" + $hp.host
          + (if ($scheme == "https" and $hp.port == "443") or ($scheme == "http" and $hp.port == "80")
             then "" else ":" + $hp.port end)
      ]
    | first // empty' 2>/dev/null) || return 1
  [[ -n $url ]] || return 1
  print -r -- "$url"
}

opencode() {
  if [[ ${1:-} == pair ]]; then
    local a url
    for a in "${@:2}"; do
      case $a in
        --url|--url=*|--remote|-h|--help) command opencode "$@"; return ;;
      esac
    done
    if url=$(_opencode_pair_tailscale_url); then
      command opencode pair --url "$url" "${@:2}"
    else
      print -ru2 -- "opencode pair: no Tailscale Serve route to the OpenCode server; printing local links"
      command opencode "$@"
    fi
    return
  fi
  command opencode "$@"
}
