#!/bin/sh
# Install / uninstall the dedicated automation-browser LaunchAgent on THIS host.
#
# `install` renders the template (substituting __HOME__ -> $HOME, since launchd
# can't expand ~) into ~/Library/LaunchAgents/ and loads it. The rendered plist
# is host-local and never committed; only the template lives in git.
#
# The instance this manages is what Hermes' browser tool drives, via the Keychain
# `hermes` entry BU_CDP_URL=http://127.0.0.1:9333. See hermes-chrome-agent for why
# a dedicated instance on a separate app bundle is used (it removes the
# per-connection "Allow remote debugging?" popup AND keeps the everyday browser
# launchable).
#
#   install    load the headless agent (idempotent; re-run to apply edits)
#   uninstall  stop it — a plain `kill` would just respawn (KeepAlive)
#   status     is it loaded?
#   check      is the CDP endpoint actually answering?
#   login      run the SAME profile headful so you can sign in to sites; the
#              headless agent is restored when you quit the browser
set -e

LABEL=local.hermes.chrome-agent
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LAUNCHER="$HOME/.config/hermes/launchd/hermes-chrome-agent"
PORT=9333
DATA_DIR="$HOME/.hermes/chrome-agent"

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
  check)
    if curl -fsS --max-time 5 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
      echo "ok: CDP endpoint answering on 127.0.0.1:$PORT"
    else
      echo "DOWN: nothing answering on 127.0.0.1:$PORT — run '$0 install'" >&2
      exit 1
    fi
    ;;
  login)
    # Only one process may hold a user-data-dir, so the headless agent has to
    # step aside. The port is kept identical, so Hermes keeps working against
    # this headful window while you sign in.
    BROWSER=""
    for candidate in $(ls -d "$HOME"/.agent-browser/browsers/chrome-*/ 2>/dev/null | sort -V -r); do
      bin="${candidate}Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
      if [ -x "$bin" ]; then BROWSER="$bin"; break; fi
    done
    [ -n "$BROWSER" ] || BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    [ -x "$BROWSER" ] || { echo "no Chrome binary found" >&2; exit 1; }

    was_loaded=no
    if launchctl list | grep -q "$LABEL"; then
      was_loaded=yes
      launchctl unload "$DEST" 2>/dev/null || true
      sleep 2
    fi

    # --use-mock-keychain must match hermes-chrome-agent: switching between the mock
    # and the real login keychain makes cookies stored under the other one unreadable.
    echo "opening the agent profile headful — sign in, then QUIT the browser to hand it back"
    "$BROWSER" \
      --remote-debugging-port="$PORT" \
      --user-data-dir="$DATA_DIR" \
      --use-mock-keychain \
      --no-first-run \
      --no-default-browser-check || true

    if [ "$was_loaded" = yes ]; then
      launchctl load -w "$DEST"
      echo "headless agent restored"
    fi
    ;;
  *)
    echo "usage: $0 [install|uninstall|status|check|login]" >&2
    exit 1
    ;;
esac
