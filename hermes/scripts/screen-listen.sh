#!/usr/bin/env bash
# Engine manager for the screen-listen plugin (an allowed app's audio, recorded through a
# Core Audio process tap and transcribed; one of its windows, recorded through
# ScreenCaptureKit when a video is asked for).
#
# The plugin runs the helper app built from engines/screen-listen/ (main.swift + Info.plist)
# into the ignored hermes/local/screen-listen/. It is launched through `open` so macOS
# attributes the consents ("System Audio Recording"; "Screen Recording" for video) to the
# helper itself ("Hermes Screen Listen"), not to the gateway.
#
#   install       build the helper app with the system Swift toolchain (Xcode or its
#                 Command Line Tools) and sign it ad hoc
#   status        whether the helper is built and current, and which processes Core Audio
#                 sees playing audio right now
#   grant         record one second of a speech synthesizer so macOS asks for System Audio
#                 Recording once (answer the dialog); reports whether audio was delivered
#   grant-screen  list windows so macOS asks for Screen Recording (only needed for video);
#                 drops a grant left stale by a rebuild, which macOS refuses silently
set -euo pipefail

HERMES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERMES_DIR/engines/screen-listen"
APP="$HERMES_DIR/local/screen-listen/ScreenListen.app"
BIN="$APP/Contents/MacOS/screen-listen"
BUNDLE_ID="local.hermes.screen-listen"   # CFBundleIdentifier in Info.plist; what tccutil keys on
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
    echo "next: $0 grant (answer the dialog); $0 grant-screen if video is used"
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
      open -W -n -g --stdout "$log" --stderr "$tmp/grant.err" -a "$APP" --args record --pid "$pid" --seconds 1 --out "$out" 2>/dev/null \
        || sleep 2   # `open -W` can fail to attach to a helper that already exited; the answer on disk counts
      wait
      [ -s "$log" ] || die "the helper could not be launched: $(cat "$tmp/grant.err" 2>/dev/null)"
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
  grant-screen)
    current || die "helper not built or stale (run: $0 install)"
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    log="$tmp/windows.json"
    allowed() {
      rm -f "$log"
      # `open -W` sometimes fails to attach to a helper that already exited (kevent: No such
      # process); the answer on disk is what counts.
      open -W -n -g --stdout "$log" --stderr "$tmp/windows.err" -a "$APP" --args windows 2>/dev/null \
        || sleep 1
      [ -s "$log" ] || die "the helper could not be launched: $(cat "$tmp/windows.err" 2>/dev/null)"
      /usr/bin/python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("ok") else 1)' "$log"
    }
    echo "listing windows through the helper; answer the macOS dialog if it appears..."
    if ! allowed; then
      # A rebuilt helper no longer matches the code requirement macOS stored with the earlier
      # grant, and Screen Recording does not ask again: it refuses silently while System
      # Settings still shows the switch on. Dropping the stale grant makes the next request a
      # fresh one (a dialog the first time on this Mac, a notification afterwards).
      echo "refused; dropping the stale grant and asking again..."
      tccutil reset ScreenCapture "$BUNDLE_ID" >/dev/null 2>&1 || true
      sleep 1
      if ! allowed; then
        open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
        echo "consent: Screen Recording is refused for the helper. In the System Settings pane that"
        echo "         just opened, switch \"Hermes Screen Listen\" off and on, then run: $0 grant-screen"
        exit 1
      fi
    fi
    /usr/bin/python3 -c '
import json, sys
data = json.load(open(sys.argv[1]))
print("consent: Screen Recording allowed; %d windows visible to the helper" % len(data["data"]))
' "$log"
    ;;
  *)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
