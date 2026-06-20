#!/bin/sh
# Install / uninstall the headless AivisSpeech Engine LaunchAgent on THIS host.
#
# Runs the engine bundled in AivisSpeech.app (no Electron GUI) so Hermes' `aivis`
# TTS provider has a backend on 127.0.0.1:10101 without keeping the desktop app
# open.
#
# The engine binary is named `run`, which is unhelpful in ps/lsof/Activity
# Monitor. To make it identifiable, `install` builds a small "shim" dir:
#   ~/.local/libexec/aivisspeech/
#     hermes-aivis-engine        # HARD link to .../AivisSpeech-Engine/run
#     engine_internal -> ...     # symlinks to the engine's sibling resources
#     resources -> ...
#     engine_manifest.json -> ...
# The agent execs the hardlink, so the process shows up as `hermes-aivis-engine`
# (macOS truncates the short name to `hermes-aivis-eng`). The engine resolves its
# root dir from the executable location, hence the sibling symlinks. The shim is
# rebuilt on every `install`, so re-run `install` after updating AivisSpeech to
# repoint the hardlink at the new binary.
#
# `install` renders the template (__HOME__ -> $HOME, since launchd can't expand
# ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist and the shim
# dir are host-local and never committed; only the template lives in git.
#
# NOTE: do not run the GUI app and this agent at the same time — both bind
# :10101. Stop this agent (`uninstall`) before opening the GUI to manage voices.
set -e

LABEL=local.aivisspeech.engine
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
SRC="/Applications/AivisSpeech.app/Contents/Resources/AivisSpeech-Engine"
SHIM_DIR="$HOME/.local/libexec/aivisspeech"
SHIM="$SHIM_DIR/hermes-aivis-engine"

case "${1:-install}" in
  install)
    [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
    [ -x "$SRC/run" ] || { echo "engine binary not found: $SRC/run (is AivisSpeech installed?)" >&2; exit 1; }
    # Named shim: hardlink the engine binary as `hermes-aivis-engine` and symlink
    # its sibling resources next to it (the engine locates its root from the
    # executable's directory). ln -f repoints a stale hardlink after app updates.
    mkdir -p "$SHIM_DIR"
    ln -f "$SRC/run" "$SHIM"
    for s in engine_internal resources engine_manifest.json; do
      ln -sfn "$SRC/$s" "$SHIM_DIR/$s"
    done
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    sed "s|__HOME__|$HOME|g" "$TMPL" > "$DEST"
    launchctl unload "$DEST" 2>/dev/null || true
    launchctl load -w "$DEST"
    echo "loaded $LABEL ($DEST)"
    echo "engine shim: $SHIM"
    ;;
  uninstall)
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    rm -rf "$SHIM_DIR"
    echo "unloaded + removed $LABEL (and shim dir)"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    echo "--- engine health ---"
    curl -s -m 3 -o /dev/null -w "engine http %{http_code}\n" http://127.0.0.1:10101/version \
      || echo "engine not reachable on :10101"
    lsof -nP -iTCP:10101 -sTCP:LISTEN +c 0 2>/dev/null | grep LISTEN || true
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
