#!/bin/sh
# profile-secrets.sh <profile> — Hermes `secrets.command` helper.
#
# Emits KEY=VALUE lines (dotenv shape) for one profile's secret scope. Under
# `gateway.multiplex_profiles: true` a profile's scope is its `.env` plus its
# external secret sources ONLY — scoped reads never fall back to the process
# environment — so this helper is how every served profile gets its keys from
# the macOS Keychain (repo policy: no `.env` files, Keychain via `secret`).
#
# Layering (later lines win in Hermes' dotenv map):
#   1. `secret env -p global`               — shared web-search / tool keys
#   2. `secret env -p hermes`               — shared model/provider keys.
#      The messaging keys (TELEGRAM_*/DISCORD_*) parked there are the
#      ASSISTANT's: assistant gets them unfiltered; the other bot profiles
#      (engineer/creator/marketer) keep only TELEGRAM_ALLOWED_USERS (the
#      owner allowlist is shared) and drop the rest; non-bot profiles drop
#      every messaging key
#   3. `secret env -p hermes-<profile>`     — this bot's own TELEGRAM_BOT_TOKEN
#      etc. (layer may not exist for non-bot profiles; that is fine)
#
# assistant only: TELEGRAM_CRON_THREAD_ID is derived from the persisted Inbox
# topic id in the assistant config (same awk as the old gateway launcher) so
# bare `deliver: telegram` cron jobs land in the Inbox topic. A missing id
# yields the literal `disabled`, which fails fast instead of misrouting.
#
# Notes:
#   - `secret env` prints `export KEY='value'` lines; Hermes' parser accepts
#     only `KEY=VALUE`, so the `export ` prefix is stripped. The single-quote
#     layer is removed by Hermes (unquote_dotenv_value). Values containing a
#     literal single quote would survive zsh (qq) quoting but not this parse —
#     don't store such values for Hermes keys.
#   - Must be fast and non-interactive (Hermes kills the helper after
#     `secrets.command.helper_timeout_seconds`); three `secret env` calls
#     measure ~2.5s, so configs set the timeout to 15.
#   - stderr is discarded by Hermes on purpose; keep diagnostics off stdout.
set -u

SECRET="$HOME/.config/bin/secret"
PROFILE="${1:-}"

[ -x "$SECRET" ] || exit 1
[ -n "$PROFILE" ] || exit 1

emit_layer() { # $1 = project layer; missing layer is not an error
  "$SECRET" env -p "$1" 2>/dev/null | sed -n 's/^export //p' || true
}

emit_layer global
case "$PROFILE" in
  assistant)
    emit_layer hermes
    ;;
  engineer|creator|marketer)
    emit_layer hermes | grep -v -E '^(TELEGRAM_|DISCORD_)' || true
    emit_layer hermes | grep -E '^TELEGRAM_ALLOWED_USERS=' || true
    ;;
  *)
    emit_layer hermes | grep -v -E '^(TELEGRAM_|DISCORD_)' || true
    ;;
esac
emit_layer "hermes-$PROFILE"

# A2A-serving profiles: the gateway authz gate reads A2A_ALLOWED_USERS from
# the profile scope, and a localhost peer (no bearer token configured)
# authenticates as the identity `ip:127.0.0.1`. Without this line every
# inbound peer call is dropped as "Unauthorized user: ip:127.0.0.1 on a2a".
case "$PROFILE" in
  engineer|creator|marketer|writer|researcher)
    echo "A2A_ALLOWED_USERS=ip:127.0.0.1"
    ;;
esac

if [ "$PROFILE" = "assistant" ]; then
  ASSISTANT_CONFIG="$HOME/.hermes/profiles/assistant/config.yaml"
  INBOX_THREAD_ID=""
  if [ -f "$ASSISTANT_CONFIG" ]; then
    INBOX_THREAD_ID="$({
      awk '
        /^[[:space:]]*- name: Inbox[[:space:]]*$/ { inbox = 1; next }
        inbox && /^[[:space:]]+thread_id:/ { print $2; exit }
        inbox && /^[[:space:]]*- name:/ { exit }
      ' "$ASSISTANT_CONFIG"
    } || true)"
  fi
  case "${INBOX_THREAD_ID:-}" in
    ''|*[!0-9]*) echo "TELEGRAM_CRON_THREAD_ID=disabled" ;;
    *) echo "TELEGRAM_CRON_THREAD_ID=$INBOX_THREAD_ID" ;;
  esac
fi

exit 0
