#!/bin/sh
# Install / uninstall the Hermes multiplex gateway LaunchAgent on THIS host.
#
# Run on the GATEWAY HOST ONLY — one bot token = one live connection per bot,
# so don't load this where another machine already runs these gateways.
#
# `install` renders the template (substituting __HOME__ -> $HOME, since launchd
# can't expand ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist
# is host-local and never committed; only the template lives in git.
#
# Older agents (ai.hermes.keychain-multiplex, local.hermes.gateway.multiplex,
# local.hermes.gateway.assistant)
# are unloaded and removed on install so two pollers never run at once
# (Telegram getUpdates 409).
set -e

LABEL=ai.hermes.multiplex
LEGACY_LABELS="ai.hermes.keychain-multiplex local.hermes.gateway.multiplex local.hermes.gateway.assistant"
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

remove_legacy() {
  for legacy in $LEGACY_LABELS; do
    legacy_dest="$HOME/Library/LaunchAgents/$legacy.plist"
    if [ -f "$legacy_dest" ]; then
      launchctl unload -w "$legacy_dest" 2>/dev/null || true
      rm -f "$legacy_dest"
      echo "unloaded + removed legacy $legacy"
    fi
  done
}

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents"
    remove_legacy
    sed "s|__HOME__|$HOME|g" "$TMPL" > "$DEST"
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    echo "loaded $LABEL ($DEST)"
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    remove_legacy
    echo "unloaded + removed $LABEL"
    ;;
  status)
    launchctl list | grep -e "$LABEL" -e ai.hermes.keychain-multiplex -e local.hermes.gateway || echo "$LABEL not loaded"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
