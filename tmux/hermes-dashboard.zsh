#!/bin/zsh -f
#
# hermes-dashboard — lazily start (or reuse) the shared Hermes Agent web
# dashboard, bound to this machine's Tailscale IPv4 so only the tailnet can
# reach it. Mirrors tmux/opencode-web.zsh's "one detached machine-level
# server" pattern: the first `prefix H` starts it, later launches reuse it,
# and it survives closing every directory's Hermes TUI.
#
#   ~/.config/tmux/hermes-dashboard.zsh
#
# The dashboard is authenticated (Basic provider). bin/hermes injects
# HERMES_DASHBOARD_BASIC_AUTH_{PASSWORD,SECRET} from the Keychain; config.yaml
# supplies the username. Tailscale encrypts the transport, so the
# plaintext-HTTP bind to the tailnet IP is safe within the VPN — nothing is
# exposed on 0.0.0.0 or the LAN.
#
# Non-fatal: if the dashboard can't start (Tailscale down, auth unset, port in
# use, first-run web build missing npm), this appends to
# ~/Library/Logs/hermes-dashboard.log, posts a tmux message, and exits 0 so the
# directory TUI still opens.

emulate -L zsh

readonly session=hermes-dashboard
readonly port=9119
readonly log=$HOME/Library/Logs/hermes-dashboard.log

mkdir -p "${log:h}"

fail() {
  print -ru2 -- "[hermes-dashboard] $*"
  print -r -- "[hermes-dashboard] $*" >> "$log"
  tmux display-message -d 5000 "Hermes dashboard unavailable; see $log"
  exit 0
}

# 1. Resolve the tailnet IPv4. Tailscale down → no mobile access anyway.
local -a ts_ips
ts_ips=("${(f)$(command tailscale ip -4 2>/dev/null)}")
ts_ip=${ts_ips[1]:-}
[[ -n $ts_ip ]] || fail "no Tailscale IPv4 (is Tailscale running?)"

readonly url=http://$ts_ip:$port

# /api/status is public even under the auth gate and reports auth_required +
# auth_providers, so it doubles as a liveness + config probe. The Tailscale IP
# routes through userspace tailscaled, so allow a generous connect timeout.
healthy() {
  local body
  body=$(curl -fsS --connect-timeout 2 --max-time 4 "$url/api/status" 2>/dev/null) &&
    print -r -- "$body" |
      jq -e '.auth_required == true and ((.auth_providers // []) | index("basic") != null)' >/dev/null 2>&1
}

# 2. Healthy dashboard already up? Reuse it.
healthy && exit 0

# Replace only a session bound to an old Tailscale address. An existing session
# with the expected command may merely be busy, so preserve it rather than
# interrupting active web chats because one health probe timed out.
if tmux has-session -t "$session" 2>/dev/null; then
  start_command=$(tmux display-message -p -t "$session" '#{pane_start_command}' 2>/dev/null)
  expected="dashboard --host $ts_ip --port $port"
  if [[ $start_command != *"$expected"* ]]; then
    tmux kill-session -t "$session" 2>/dev/null || fail "could not replace dashboard bound to an old address"
  else
    fail "existing dashboard is not responding; preserving its active session"
  fi
fi

# 3. Start a fresh machine-level dashboard in a detached tmux session. First
#    run builds the web UI (npm), so the warm-up poll below is generous.
started=0
if ! tmux has-session -t "$session" 2>/dev/null; then
  command="exec \"$HOME/.config/bin/hermes\" dashboard --host $ts_ip --port $port --no-open >\"$log\" 2>&1"
  if tmux new-session -d -s "$session" -c "$HOME" "$command" 2>/dev/null; then
    started=1
  else
    tmux has-session -t "$session" 2>/dev/null || fail "could not create tmux session"
  fi
fi

# 4. Wait for the dashboard to come up (up to ~120s for a first-run web build).
for attempt in {1..240}; do
  tmux has-session -t "$session" 2>/dev/null || fail "dashboard session exited (see $log)"
  healthy && exit 0
  sleep 0.5
done

(( started )) && tmux kill-session -t "$session" 2>/dev/null
fail "dashboard did not become healthy within 120s (see $log)"
