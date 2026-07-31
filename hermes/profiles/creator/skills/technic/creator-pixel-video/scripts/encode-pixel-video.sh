#!/usr/bin/env bash
# Encode native-grid PNG frames without interpolation.
#
# Usage:
#   encode-pixel-video.sh 'frames/frame_%04d.png' master.mp4 \
#     --scale 24 --effective-fps 12 --container-fps 24 \
#     [--compat compat.mp4] [--gif loop.gif]

set -euo pipefail

die() { echo "encode-pixel-video: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found"; }

[ "$#" -ge 2 ] || die "expected FRAME_PATTERN OUTPUT.mp4"
PATTERN="$1"; OUTPUT="$2"; shift 2
SCALE=16; EFFECTIVE_FPS=12; CONTAINER_FPS=24; COMPAT=""; GIF=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --scale) SCALE="$2"; shift 2 ;;
    --effective-fps) EFFECTIVE_FPS="$2"; shift 2 ;;
    --container-fps) CONTAINER_FPS="$2"; shift 2 ;;
    --compat) COMPAT="$2"; shift 2 ;;
    --gif) GIF="$2"; shift 2 ;;
    *) die "unknown option: $1" ;;
  esac
done
case "$SCALE:$EFFECTIVE_FPS:$CONTAINER_FPS" in *[!0-9:]*|0:*|*:0:*|*:0) die "scale and fps values must be positive integers" ;; esac
[ "$CONTAINER_FPS" -ge "$EFFECTIVE_FPS" ] || die "container fps must be >= effective fps"
[ $((CONTAINER_FPS % EFFECTIVE_FPS)) -eq 0 ] || die "container fps must be an integer multiple of effective fps"
[ -z "$COMPAT" ] || [ $((SCALE % 2)) -eq 0 ] || die "yuv420p compatibility output requires an even integer scale"
need ffmpeg
need ffprobe
mkdir -p "$(dirname "$OUTPUT")"

FILTER="format=rgb24,scale=iw*${SCALE}:ih*${SCALE}:flags=neighbor"
ffmpeg -v error -y -framerate "$EFFECTIVE_FPS" -i "$PATTERN" \
  -vf "$FILTER" -r "$CONTAINER_FPS" -an -c:v libx264rgb -qp 0 -pix_fmt rgb24 \
  -movflags +faststart "$OUTPUT"

if [ -n "$COMPAT" ]; then
  mkdir -p "$(dirname "$COMPAT")"
  ffmpeg -v error -y -framerate "$EFFECTIVE_FPS" -i "$PATTERN" \
    -sws_flags neighbor+full_chroma_int -vf "$FILTER" -r "$CONTAINER_FPS" -an \
    -c:v libx264 -qp 0 -pix_fmt yuv420p -movflags +faststart "$COMPAT"
fi

if [ -n "$GIF" ]; then
  mkdir -p "$(dirname "$GIF")"
  ffmpeg -v error -y -framerate "$EFFECTIVE_FPS" -i "$PATTERN" \
    -filter_complex "format=rgb24,scale=iw*${SCALE}:ih*${SCALE}:flags=neighbor,split[a][b];[a]palettegen=max_colors=256[p];[b][p]paletteuse=dither=none" \
    -loop 0 "$GIF"
fi

ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,pix_fmt:format=duration,size \
  -of default=noprint_wrappers=1 "$OUTPUT"
