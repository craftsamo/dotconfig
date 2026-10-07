#!/usr/bin/env bash
#
# poster-frame.sh — extract a poster / preview still from a clip.
#
# For an <video poster="…"> image or a feed thumbnail. Pick a frame that looks
# good static — for autoplay heroes, the first frame (--time 0) avoids a jump
# from poster to video.
#
# Usage:
#   poster-frame.sh INPUT OUTPUT [options]
#     INPUT          local video path (or http(s) URL)
#     OUTPUT         image path (.jpg | .png | .webp — encoder from extension)
#   Options:
#     --time SEC     timestamp to grab (default 0.0)
#     -h, --help
#
# Tooling: ffmpeg (+ cwebp for .webp output). Install via the repo Brewfile:
#   ./install.sh --deps

set -euo pipefail

die() { echo "poster-frame: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found — run ./install.sh --deps to install ffmpeg"; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

INPUT="$1"; OUTPUT="$2"; shift 2
TIME="0.0"
while [ $# -gt 0 ]; do
  case "$1" in
    --time) TIME="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

need ffmpeg
case "$INPUT" in
  http://*|https://*) : ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT" ;;
esac

mkdir -p "$(dirname "$OUTPUT")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/poster.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# -ss before -i = fast seek; one frame; -update 1 lets a single image path work.
# Some ffmpeg builds ship without libwebp, so encode .webp via cwebp instead.
case "${OUTPUT##*.}" in
  jpg|jpeg|JPG|JPEG)
    ffmpeg -y -hide_banner -loglevel error -ss "$TIME" -i "$INPUT" -frames:v 1 -update 1 -q:v 2 "$OUTPUT" ;;
  png|PNG)
    ffmpeg -y -hide_banner -loglevel error -ss "$TIME" -i "$INPUT" -frames:v 1 -update 1 "$OUTPUT" ;;
  webp|WEBP)
    need cwebp
    ffmpeg -y -hide_banner -loglevel error -ss "$TIME" -i "$INPUT" -frames:v 1 -update 1 "$WORK/frame.png"
    cwebp -quiet -q 80 "$WORK/frame.png" -o "$OUTPUT" || die "cwebp failed" ;;
  *) die "unknown output type: ${OUTPUT##*.} (use jpg|png|webp)" ;;
esac

FINAL_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
echo "ok: $OUTPUT  (@${TIME}s, ${FINAL_BYTES} bytes)"
