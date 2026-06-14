#!/usr/bin/env bash
#
# video-postprocess.sh — localize a generated clip and normalize it to an exact target.
#
# Accepts a URL or a local path (video_generate returns either; hosted URLs
# expire, so localize immediately), then optionally trims, scales+crops to exact
# dimensions, converts container/codec, strips audio, and caps file size.
#
# Usage:
#   video-postprocess.sh INPUT OUTPUT [options]
#     INPUT            http(s) URL or local video path
#     OUTPUT           output file path (extension implies --format if omitted)
#   Options:
#     --trim SS[:DUR]  start at SS seconds; optional duration DUR seconds
#     --size WxH       scale+crop to exact pixels (e.g. 1080x1920)
#     --fit MODE       cover (default, crops) | contain (pads black)
#     --format F       mp4 (H.264) | webm (VP9)   (default: from OUTPUT ext, else mp4)
#     --fps N          set output frame rate
#     --mute           strip the audio track
#     --max-bytes N    cap size via two-pass bitrate; N accepts K/M/KB/MB
#     -h, --help
#
# Tooling: ffmpeg + ffprobe. Install via the repo Brewfile: ./install.sh --deps

set -euo pipefail

die() { echo "video-postprocess: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found — run ./install.sh --deps to install ffmpeg"; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

INPUT="$1"; OUTPUT="$2"; shift 2
TRIM_SS=""; TRIM_DUR=""; SIZE=""; FIT="cover"; FORMAT=""; FPS=""; MUTE=0; MAXBYTES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --trim) case "$2" in *:*) TRIM_SS="${2%%:*}"; TRIM_DUR="${2#*:}" ;; *) TRIM_SS="$2" ;; esac; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --fit) FIT="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --fps) FPS="$2"; shift 2 ;;
    --mute) MUTE=1; shift ;;
    --max-bytes) MAXBYTES="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

need ffmpeg; need ffprobe

# Resolve container/codec from OUTPUT extension if not given.
if [ -z "$FORMAT" ]; then
  case "${OUTPUT##*.}" in
    webm|WEBM) FORMAT=webm ;;
    mp4|MP4|m4v|M4V|mov|MOV) FORMAT=mp4 ;;
    *) FORMAT=mp4 ;;
  esac
fi

bytes() {
  local v="$1" n="${1%%[KkMmBb]*}"
  case "$v" in
    *[Mm]*) echo $(( ${n%.*} * 1024 * 1024 )) ;;
    *[Kk]*) echo $(( ${n%.*} * 1024 )) ;;
    *) echo "${n%.*}" ;;
  esac
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/vidpp.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# 1) Localize the source (URLs expire — always pull a local copy first).
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) need curl; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac

# 2) Build the video filter (scale/crop/pad, fps, then force even dims for yuv420p).
VF=""
if [ -n "$SIZE" ]; then
  W="${SIZE%x*}"; H="${SIZE#*x}"
  case "$FIT" in
    cover)   VF="scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}" ;;
    contain) VF="scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:black" ;;
    *) die "unknown --fit: $FIT (use cover|contain)" ;;
  esac
fi
[ -n "$FPS" ] && VF="${VF:+$VF,}fps=${FPS}"
VF="${VF:+$VF,}scale=trunc(iw/2)*2:trunc(ih/2)*2"

# 3) Codecs.
case "$FORMAT" in
  mp4)  VCODEC=(-c:v libx264 -pix_fmt yuv420p -movflags +faststart) ;;
  webm) VCODEC=(-c:v libvpx-vp9 -pix_fmt yuv420p) ;;
  *) die "unknown --format: $FORMAT (use mp4|webm)" ;;
esac
if [ "$MUTE" -eq 1 ]; then
  ACODEC=(-an)
elif [ "$FORMAT" = "mp4" ]; then
  ACODEC=(-c:a aac -b:a 128k)
else
  ACODEC=(-c:a libopus -b:a 128k)
fi

# 4) Common input args (always non-empty — bash 3.2 safe).
COMMON=(-y -hide_banner -loglevel error)
[ -n "$TRIM_SS" ] && COMMON+=(-ss "$TRIM_SS")
COMMON+=(-i "$SRC")
[ -n "$TRIM_DUR" ] && COMMON+=(-t "$TRIM_DUR")
COMMON+=(-vf "$VF")

mkdir -p "$(dirname "$OUTPUT")"

# 5) Encode: CRF single-pass, or two-pass when a hard size cap is requested.
if [ -n "$MAXBYTES" ]; then
  cap="$(bytes "$MAXBYTES")"
  if [ -n "$TRIM_DUR" ]; then dur="$TRIM_DUR"; else
    dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC" 2>/dev/null || echo 0)"
  fi
  dur="${dur%.*}"; case "$dur" in ''|*[!0-9]*) dur=1 ;; esac; [ "$dur" -lt 1 ] && dur=1
  audio_k=128; [ "$MUTE" -eq 1 ] && audio_k=0
  total_k=$(( cap * 8 / 1000 / dur * 95 / 100 ))
  vbit_k=$(( total_k - audio_k )); [ "$vbit_k" -lt 64 ] && vbit_k=64
  PLOG="$WORK/pass"
  ffmpeg "${COMMON[@]}" "${VCODEC[@]}" -b:v "${vbit_k}k" -pass 1 -passlogfile "$PLOG" -an -f null /dev/null
  ffmpeg "${COMMON[@]}" "${VCODEC[@]}" -b:v "${vbit_k}k" -pass 2 -passlogfile "$PLOG" "${ACODEC[@]}" "$OUTPUT"
else
  if [ "$FORMAT" = "mp4" ]; then QUALITY=(-crf 23 -preset medium); else QUALITY=(-crf 32 -b:v 0); fi
  ffmpeg "${COMMON[@]}" "${VCODEC[@]}" "${QUALITY[@]}" "${ACODEC[@]}" "$OUTPUT"
fi

FINAL_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
DIMS="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$OUTPUT" 2>/dev/null || echo '?')"
echo "ok: $OUTPUT  ($FORMAT, $DIMS, ${FINAL_BYTES} bytes)"
