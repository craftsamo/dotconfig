#!/bin/sh
# Telegram-only gateway launcher for the `assistant` profile (keychain-pure).
#
# Workaround for the Discord-triggered handoff-watcher hang (upstream issue
# #40695): the gateway's `_handoff_watcher` blocks the event loop on a
# `list_pending_handoffs` SQLite query when Discord is connected. Until that's
# fixed upstream, run Telegram only.
#
# Mechanism: inject the `global` + `hermes` Keychain layers the same way the
# bin/hermes shim does, drop the Discord vars, then exec the REAL hermes binary
# (not the shim, which would re-inject Discord). No plaintext .env.
#
# Re-enable Discord once #40695 is fixed: delete the `unset` line below (or
# point the LaunchAgent back at `~/.config/bin/hermes` directly).
set -e

eval "$(secret env -p global)"
eval "$(secret env -p hermes)"

# Drop Discord so the gateway connects Telegram only.
unset DISCORD_BOT_TOKEN DISCORD_ALLOWED_USERS DISCORD_HOME_CHANNEL

exec "$HOME/.local/bin/hermes" -p assistant gateway run --replace --accept-hooks
