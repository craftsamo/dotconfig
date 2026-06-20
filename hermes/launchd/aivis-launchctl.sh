#!/bin/sh
# Install / uninstall the headless AivisSpeech Engine LaunchAgent on THIS host.
#
# Runs the engine binary bundled in AivisSpeech.app directly (no Electron GUI),
# so Hermes' `aivis` TTS provider has a backend on 127.0.0.1:10101 without
# keeping the desktop app open.
#
# `install` renders the template (__HOME__ -> $HOME, since launchd can't expand
# ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist is host-local
# and never committed; only the template lives in git.
#
# NOTE: do not run the GUI app and this agent at the same time — both bind
# :10101. Stop this agent (`uninstall`) before opening the GUI to manage voices.
set -e

LABEL=local.aivisspeech.engine
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
ENGINE="/Applications/AivisSpeech.app/Contents/Resources/AivisSpeech-Engine/run"

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    [ -x "$ENGINE" ] || { echo "engine binary not found: $ENGINE (is AivisSpeech installed?)" >&2; exit 1; }
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
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
    echo "--- engine health ---"
    curl -s -m 3 -o /dev/null -w "engine http %{http_code}\n" http://127.0.0.1:10101/version \
      || echo "engine not reachable on :10101"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
