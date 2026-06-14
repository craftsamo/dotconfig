#!/bin/sh
# Install / uninstall the assistant gateway LaunchAgent on THIS host.
#
# Run on the GATEWAY HOST ONLY — one bot token = one live connection, so don't
# load this where another machine already runs the gateway.
#
# `install` renders the template (substituting __HOME__ -> $HOME, since launchd
# can't expand ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist
# is host-local and never committed; only the template lives in git.
set -e

LABEL=local.hermes.gateway.assistant
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents"
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
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
