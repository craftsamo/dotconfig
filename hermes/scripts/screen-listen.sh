#!/usr/bin/env bash
# Engine manager for the screen-listen plugin (an allowed app's audio, recorded through a
# Core Audio process tap and transcribed).
#
# The plugin runs the helper app built from engines/screen-listen/ (main.swift + Info.plist)
# into the ignored hermes/local/screen-listen/. It is launched through `open` so macOS
# attributes the one-time "System Audio Recording" consent to the helper itself
# ("Hermes Screen Listen"), not to the gateway.
#
#   install   build the helper app with the system Swift toolchain (Xcode or its
#             Command Line Tools) and sign it ad hoc
#   status    whether the helper is built and current, and which processes Core Audio
#             sees playing audio right now
#   grant     record one second from any running process so macOS asks for the consent
#             once (answer the dialog); reports whether audio was delivered
set -euo pipefail

HERMES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERMES_DIR/engines/screen-listen"
APP="$HERMES_DIR/local/screen-listen/ScreenListen.app"
BIN="$APP/Contents/MacOS/screen-listen"
TARGET="$(uname -m)-apple-macosx14.2"   # LaunchServices refuses a binary whose minimum OS is newer than the host

die() { echo "error: $*" >&2; exit 1; }

current() {
  [ -x "$BIN" ] && [ "$BIN" -nt "$SRC/main.swift" ] && [ "$APP/Contents/Info.plist" -nt "$SRC/Info.plist" ]
}

case "${1:-}" in
  install)
    command -v swiftc >/dev/null 2>&1 || die "swiftc not found (install Xcode or its Command Line Tools)"
    [ -f "$SRC/main.swift" ] && [ -f "$SRC/Info.plist" ] || die "missing sources in $SRC"
    mkdir -p "$APP/Contents/MacOS"
    cp "$SRC/Info.plist" "$APP/Contents/Info.plist"
    swiftc -O -target "$TARGET" -o "$BIN" "$SRC/main.swift"
    codesign --force --sign - "$APP" 2>&1 | grep -v "replacing existing signature" || true
    codesign --verify "$APP" || die "ad-hoc signing failed"
    echo "installed the screen-listen helper in $APP"
    echo "the ad-hoc signature is new, so macOS asks for System Audio Recording once more"
    echo "next: $0 grant (answer the dialog)"
    ;;
  status)
    if current; then
      echo "helper:  built ($APP)"
    elif [ -x "$BIN" ]; then
      echo "helper:  stale (sources changed; run: $0 install)"
    else
      echo "helper:  not built (run: $0 install)"
      exit 0
    fi
    "$BIN" processes | /usr/bin/python3 -c '
import json, sys
data = json.load(sys.stdin)
if not data.get("ok"):
    print("audio:   %s" % data.get("error"))
    sys.exit(0)
playing = [p for p in data["data"] if p["running_output"]]
print("audio:   %d processes registered, %d playing" % (len(data["data"]), len(playing)))
for p in playing:
    print("         pid %s %s" % (p["pid"], p["bundle"] or "(no bundle id)"))
'
    ;;
  grant)
    current || die "helper not built or stale (run: $0 install)"
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    out="$tmp/grant.wav"
    log="$tmp/grant.json"
    echo "recording one second through the helper; answer the macOS dialog if it appears..."
    # A tap delivers nothing from a process that outputs nothing, so the take listens to a
    # speech synthesizer this script starts. The take that raises the dialog gets no audio even
    # when the answer is yes; a second take does.
    for attempt in 1 2; do
      rm -f "$out" "$log"
      /usr/bin/say -r 160 "Hermes screen listen consent check, one two three four five six seven" &
      sleep 0.7
      pid=$(pgrep -n -x say || true)
      [ -n "$pid" ] || die "could not start the speech synthesizer for the check"
      open -W -n -g --stdout "$log" --stderr "$tmp/grant.err" -a "$APP" --args record --pid "$pid" --seconds 1 --out "$out" \
        || die "the helper could not be launched: $(cat "$tmp/grant.err" 2>/dev/null)"
      wait
      /usr/bin/python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("ok") and d["data"]["frames"] else 1)' "$log" \
        && break
      [ "$attempt" = 1 ] && sleep 2
    done
    /usr/bin/python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit("consent: the helper printed no result")
if data.get("ok"):
    d = data["data"]
    print("consent: audio delivered (%d frames); the helper is allowed" % d["frames"] if d["frames"]
          else "consent: no audio delivered; check System Settings > Privacy & Security > Screen & System Audio Recording")
else:
    print("consent: %s: %s" % (data.get("kind"), data.get("error")))
' "$log"
    ;;
  *)
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
