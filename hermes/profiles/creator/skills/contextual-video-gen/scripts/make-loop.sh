#!/usr/bin/env bash
#
# make-loop.sh — turn a generated clip into a seamless loop.
#
# Generated clips rarely loop cleanly. Two strategies:
#   crossfade  — blend the tail back into the head over --xfade seconds
#                (output length = duration - xfade; needs xfade <= duration/2).
#                General-purpose; best for ambient motion.
#   palindrome — forward then reversed, so the ends always meet (output length
#                = 2x). Great for short ambient motion; wrong for directional moves.
#
# Output is muted (loops autoplay muted). Container/codec from OUTPUT extension.
#
# Usage:
#   make-loop.sh INPUT OUTPUT [options]
#     INPUT          local video path (run video-postprocess.sh first to localize)
#     OUTPUT         output file path (.mp4 -> H.264 | .webm -> VP9)
#   Options:
#     --mode MODE    crossfade (default) | palindrome
#     --xfade SEC    crossfade seconds (default 0.5)
#     -h, --help
#
# Tooling: ffmpeg + ffprobe. Install via the repo Brewfile: ./install.sh --deps

set -euo pipefail

die() { echo "make-loop: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found — run ./install.sh --deps to install ffmpeg"; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

INPUT="$1"; OUTPUT="$2"; shift 2
MODE="crossfade"; XFADE="0.5"
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --xfade) XFADE="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

need ffmpeg; need ffprobe
[ -f "$INPUT" ] || die "input not found: $INPUT"

case "${OUTPUT##*.}" in
  webm|WEBM) VCODEC=(-c:v libvpx-vp9 -pix_fmt yuv420p -crf 32 -b:v 0) ;;
  *)         VCODEC=(-c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium -movflags +faststart) ;;
esac

mkdir -p "$(dirname "$OUTPUT")"

case "$MODE" in
  palindrome)
    ffmpeg -y -hide_banner -loglevel error -i "$INPUT" \
      -filter_complex "[0:v]split[f][r];[r]reverse[rv];[f][rv]concat=n=2:v=1:a=0[out]" \
      -map "[out]" -an "${VCODEC[@]}" "$OUTPUT"
    ;;
  crossfade)
    DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT" 2>/dev/null || echo 0)"
    # Validate xfade <= duration/2 (need a non-empty straight body) using awk (floats).
    awk -v d="$DUR" -v x="$XFADE" 'BEGIN{ if (d+0<=0) exit 2; if (x+0<=0) exit 3; if (x+0 > d/2) exit 4; exit 0 }' \
      || die "xfade ($XFADE s) must be > 0 and <= half the clip duration ($DUR s); lower --xfade or use --mode palindrome"
    DMX="$(awk -v d="$DUR" -v x="$XFADE" 'BEGIN{ printf "%.3f", d - x }')"
    # head=[0,x]  tail=[D-x,D]  rest=[x,D-x]; blend tail->head over x, then rest.
    FC="[0:v]trim=0:${XFADE},setpts=PTS-STARTPTS[head];"
    FC="${FC}[0:v]trim=${DMX}:${DUR},setpts=PTS-STARTPTS[tail];"
    FC="${FC}[tail][head]blend=all_expr='A*(1-T/${XFADE})+B*(T/${XFADE})'[bh];"
    FC="${FC}[0:v]trim=${XFADE}:${DMX},setpts=PTS-STARTPTS[rest];"
    FC="${FC}[bh][rest]concat=n=2:v=1:a=0[out]"
    ffmpeg -y -hide_banner -loglevel error -i "$INPUT" \
      -filter_complex "$FC" -map "[out]" -an "${VCODEC[@]}" "$OUTPUT"
    ;;
  *) die "unknown --mode: $MODE (use crossfade|palindrome)" ;;
esac

FINAL_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
DUR2="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT" 2>/dev/null || echo '?')"
echo "ok: $OUTPUT  (loop=$MODE, ${DUR2}s, ${FINAL_BYTES} bytes)"
