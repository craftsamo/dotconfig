#!/bin/sh
# Run the Cloudflare Tunnel connector in the foreground (the LaunchAgent
# local.hermes.cloudflared.tunnel keeps it alive). The tunnel is managed in the
# Cloudflare dashboard: which public hostname reaches which local port is set
# there (or through the cloudflare-access plugin's tunnel_route), never here,
# so this script and the plist name no hostname.
#
# The connector's token is the Keychain item CLOUDFLARE_TUNNEL_TOKEN of
# project hermes, scope cloudflare-access (the scope the plugin's own tokens
# use). It is read here, at start, and handed to cloudflared through the
# environment it documents (TUNNEL_TOKEN), never on a command line.
# Updates are left to Homebrew (--no-autoupdate): a self-restarting binary
# under launchd would race its supervisor.
set -eu

SECRET="${SECRET_CLI:-$HOME/.config/bin/secret}"
[ -x "$SECRET" ] || { echo "cloudflared-run: the secret CLI is missing at $SECRET" >&2; exit 78; }
command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared-run: cloudflared not on PATH (brew install cloudflared)" >&2; exit 78; }

TUNNEL_TOKEN="$("$SECRET" get CLOUDFLARE_TUNNEL_TOKEN -p hermes --scope cloudflare-access --no-stage)" || {
  echo "cloudflared-run: no CLOUDFLARE_TUNNEL_TOKEN in the Keychain; store the dashboard tunnel's token with:" >&2
  echo "  secret set CLOUDFLARE_TUNNEL_TOKEN -p hermes --scope cloudflare-access --no-stage -D TOKEN" >&2
  exit 78
}
export TUNNEL_TOKEN

exec cloudflared tunnel --no-autoupdate run
