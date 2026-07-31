#!/usr/bin/env bash
#
# to-gif.sh — convert a clip (or a still, via --ken-burns) to a high-quality GIF.
#
# Uses a two-pass palettegen/paletteuse pipeline for clean colours. GIFs are
# large, capped at 256 colours, and carry no audio — prefer mp4/webm for the
# web; use GIF for chat, README demos, stickers, or anywhere a GIF is required.
#
# Modes:
#   default      INPUT is a video (URL or local) -> GIF.
#   --ken-burns  INPUT is a still image -> synthesize a slow zoom/pan -> GIF
#                (no AI, no cost; good for logos/photos).
#
# Usage:
#   to-gif.sh INPUT OUTPUT [options]
#     INPUT            http(s) URL or local path (video; or image with --ken-burns)
#     OUTPUT           output .gif path
#   Options:
#     --fps N          frame rate (default 12)
#     --width W        scale width in px, aspect preserved (default 480)
#     --max-colors N   palette size, 2-256 (default 256)
#     --loop N         loop count; 0 = infinite (default 0)
#     --trim SS[:DUR]  start at SS seconds; optional duration DUR (video mode)
#     --max-bytes N    best-effort size cap (K/M/KB/MB); steps colours then width down
#     --ken-burns      treat INPUT as a still; synthesize motion
#     --kb-seconds S   Ken Burns duration in seconds (default 4)
#     -h, --help
#
# Tooling: ffmpeg + ffprobe. Install via the repo Brewfile: ./install.sh --deps

set -euo pipefail

die() { echo "to-gif: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found — run ./install.sh --deps to install ffmpeg"; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

INPUT="$1"; OUTPUT="$2"; shift 2
FPS=12; WIDTH=480; COLORS=256; LOOP=0; TRIM_SS=""; TRIM_DUR=""; MAXBYTES=""; KENBURNS=0; KB_SECONDS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --fps) FPS="$2"; shift 2 ;;
    --width) WIDTH="$2"; shift 2 ;;
    --max-colors) COLORS="$2"; shift 2 ;;
    --loop) LOOP="$2"; shift 2 ;;
    --trim) case "$2" in *:*) TRIM_SS="${2%%:*}"; TRIM_DUR="${2#*:}" ;; *) TRIM_SS="$2" ;; esac; shift 2 ;;
    --max-bytes) MAXBYTES="$2"; shift 2 ;;
    --ken-burns) KENBURNS=1; shift ;;
    --kb-seconds) KB_SECONDS="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

need ffmpeg
case "${OUTPUT##*.}" in gif|GIF) : ;; *) die "OUTPUT must be a .gif file" ;; esac

bytes() {
  local v="$1" n="${1%%[KkMmBb]*}"
  case "$v" in
    *[Mm]*) echo $(( ${n%.*} * 1024 * 1024 )) ;;
    *[Kk]*) echo $(( ${n%.*} * 1024 )) ;;
    *) echo "${n%.*}" ;;
  esac
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/togif.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Localize the source (URLs from video_generate expire).
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) need curl; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac

# Input args (always non-empty — bash 3.2 safe). Trim (video mode) is set as
# input options so it applies to SRC consistently across both palette passes.
IN=()
if [ "$KENBURNS" -eq 0 ]; then
  [ -n "$TRIM_SS" ] && IN+=(-ss "$TRIM_SS")
  [ -n "$TRIM_DUR" ] && IN+=(-t "$TRIM_DUR")
fi
IN+=(-i "$SRC")

# For Ken Burns we need the still's aspect to derive an even output height.
if [ "$KENBURNS" -eq 1 ]; then
  need ffprobe
  IW="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$SRC" 2>/dev/null || echo 0)"
  IH="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$SRC" 2>/dev/null || echo 0)"
  { [ "$IW" -gt 0 ] && [ "$IH" -gt 0 ]; } 2>/dev/null || die "could not read image dimensions: $INPUT"
fi

# Build the base (pre-palette) filter from the current WIDTH (rebuilt on resize).
build_base_filter() {
  if [ "$KENBURNS" -eq 1 ]; then
    H="$(awk -v w="$WIDTH" -v iw="$IW" -v ih="$IH" 'BEGIN{h=int(w*ih/iw); if (h%2) h++; print h}')"
    UP=$(( WIDTH * 4 ))
    FRAMES=$(( KB_SECONDS * FPS ))
    BASE_FILTER="scale=${UP}:-2,zoompan=z='min(zoom+0.0015,1.15)':d=${FRAMES}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=${WIDTH}x${H}:fps=${FPS}"
  else
    BASE_FILTER="fps=${FPS},scale=${WIDTH}:-2:flags=lanczos"
  fi
}

encode_gif() {
  local pal="$WORK/palette.png"
  ffmpeg -y -hide_banner -loglevel error "${IN[@]}" \
    -vf "${BASE_FILTER},palettegen=max_colors=${COLORS}:stats_mode=diff" "$pal"
  ffmpeg -y -hide_banner -loglevel error "${IN[@]}" -i "$pal" \
    -lavfi "${BASE_FILTER}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    -loop "$LOOP" "$OUTPUT"
}

mkdir -p "$(dirname "$OUTPUT")"
build_base_filter
encode_gif

# Best-effort size cap: step palette down, then width, and re-encode.
if [ -n "$MAXBYTES" ]; then
  cap="$(bytes "$MAXBYTES")"; tries=0
  while [ "$(wc -c < "$OUTPUT" | tr -d ' ')" -gt "$cap" ] && [ "$tries" -lt 6 ]; do
    if [ "$COLORS" -gt 32 ]; then
      COLORS=$(( COLORS / 2 ))
    else
      WIDTH=$(( WIDTH * 8 / 10 )); [ "$WIDTH" -lt 120 ] && break
    fi
    build_base_filter
    encode_gif
    tries=$(( tries + 1 ))
  done
  got="$(wc -c < "$OUTPUT" | tr -d ' ')"
  [ "$got" -gt "$cap" ] && echo "to-gif: warning: ${got}B still over cap ${cap}B — lower --fps/--width or shorten the clip" >&2
fi

FINAL_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
DIMS="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$OUTPUT" 2>/dev/null || echo '?')"
echo "ok: $OUTPUT  (gif, $DIMS, ${COLORS} colors, ${FPS}fps, ${FINAL_BYTES} bytes)"
