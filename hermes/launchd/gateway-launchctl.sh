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
# The legacy single-profile agent (local.hermes.gateway.assistant) is unloaded
# on install so the two pollers never run at once (Telegram getUpdates 409).
set -e

LABEL=local.hermes.gateway.multiplex
LEGACY_LABEL=local.hermes.gateway.assistant
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LEGACY_DEST="$HOME/Library/LaunchAgents/$LEGACY_LABEL.plist"

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents"
    if [ -f "$LEGACY_DEST" ]; then
      launchctl unload -w "$LEGACY_DEST" 2>/dev/null || true
      rm -f "$LEGACY_DEST"
      echo "unloaded + removed legacy $LEGACY_LABEL"
    fi
    sed "s|__HOME__|$HOME|g" "$TMPL" > "$DEST"
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    echo "loaded $LABEL ($DEST)"
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    echo "unloaded + removed $LABEL"
    ;;
  status)
    launchctl list | grep -e "$LABEL" -e "$LEGACY_LABEL" || echo "$LABEL not loaded"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
