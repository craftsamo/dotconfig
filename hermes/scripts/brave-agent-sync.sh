#!/bin/sh
# brave-agent-sync.sh [sync|check|path|remove] — keep the real-profile browser
# CLONE in step with the installed Brave.
#
# Hermes' real-profile browsing (`browser.use_real_profile`) launches the
# user's real browser binary headless on a snapshot of one Brave profile. On
# macOS every process running out of ONE app bundle is ONE application to
# LaunchServices, so while that headless instance is alive a Dock / Spotlight
# launch of /Applications/Brave Browser.app only activates it and the everyday
# browser cannot be opened (reproduced 2026-09-06, same defect as the resident
# Brave of 2026-08-17). An APFS clone of the bundle at another path has no
# shared identity, and because its code signature is untouched the Keychain
# `Brave Safe Storage` ACL (bundle id + team, not path) still lets it decrypt
# the profile's cookies. `browser.real_profile_binary` in the consenting
# profiles' config.yaml points at the clone's binary (the local fix branch
# fix/real-profile-binary-override in the hermes-agent checkout adds the key).
#
# The clone is a snapshot of the binary, not a link: Brave auto-updates, so
# the gateway launcher runs `sync` before every start and this script can be
# run by hand after an update. A stale clone keeps working until then (the
# profile's cookie format does not change across releases). Never edit the
# clone's contents — any change breaks the signature and with it cookie
# decryption; re-clone instead.
#
#   sync    (default) re-clone when the installed version differs or the clone
#           binary is missing; terminates a running clone first (it is ours —
#           a Hermes real-profile session that survived a gateway crash)
#   check   exit 0 when the clone exists and matches the installed version
#   path    print the clone's binary path (the value for real_profile_binary)
#   remove  delete the clone (and any running instance)
set -e

SRC="/Applications/Brave Browser.app"
DEST_DIR="$HOME/.config/hermes/local/brave-agent"   # gitignored: hermes/**/local/
DEST="$DEST_DIR/Brave Agent.app"
BIN="$DEST/Contents/MacOS/Brave Browser"

version() { defaults read "$1/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || true; }

stop_clone() {
  # Only OUR clone's processes: match on the clone's binary path, never the
  # everyday /Applications binary. Helpers die with their browser process.
  if pgrep -f "^$BIN" >/dev/null 2>&1; then
    pkill -f "^$BIN" || true
    sleep 2
  fi
}

case "${1:-sync}" in
  path)
    printf '%s\n' "$BIN"
    ;;
  check)
    [ -x "$BIN" ] || { echo "MISSING: $BIN" >&2; exit 1; }
    have="$(version "$DEST")"; want="$(version "$SRC")"
    if [ "$have" = "$want" ] && [ -n "$have" ]; then
      echo "ok: clone $have matches installed Brave"
    else
      echo "STALE: clone $have, installed $want — run '$0 sync'" >&2
      exit 1
    fi
    ;;
  sync)
    [ -d "$SRC" ] || { echo "Brave is not installed at $SRC; nothing to clone" >&2; exit 1; }
    want="$(version "$SRC")"
    if [ -x "$BIN" ] && [ "$(version "$DEST")" = "$want" ]; then
      echo "brave-agent clone up to date ($want)"
      exit 0
    fi
    stop_clone
    mkdir -p "$DEST_DIR"
    rm -rf "$DEST.new" "$DEST"
    # -c = APFS clonefile: instant and shares blocks with the original.
    cp -Rc "$SRC" "$DEST.new"
    # Finder/resource-fork detritus copied along makes `codesign --verify
    # --strict` complain; it is not part of the signature, so strip it.
    xattr -cr "$DEST.new" 2>/dev/null || true
    mv "$DEST.new" "$DEST"
    codesign --verify --deep --strict "$DEST" >/dev/null 2>&1 \
      || { echo "WARN: clone signature did not verify — cookie decryption may prompt or fail" >&2; }
    echo "brave-agent clone refreshed to $want: $BIN"
    ;;
  remove)
    stop_clone
    rm -rf "$DEST" "$DEST.new"
    echo "removed $DEST"
    ;;
  *)
    echo "usage: $0 {sync|check|path|remove}" >&2
    exit 2
    ;;
esac
