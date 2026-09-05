#!/usr/bin/env bash
#
# emoji-fit.sh — the emoji family's finish: turn one image (a generated
# frame on a flat background, a drawn tile, a photo cut-out, or an already
# transparent PNG) into a file that a platform's custom-emoji / sticker
# upload accepts. The platform table lives HERE and nowhere else.
#
# Usage:
#   emoji-fit.sh INPUT OUTPUT_STEM --platform PLATFORM
#                [--cutout auto|yes|no] [--fuzz PCT] [--pad FRACTION]
#                [--stroke PX] [--stroke-color '#rrggbb']
#     INPUT        local path or http(s) URL
#     OUTPUT_STEM  path WITHOUT extension; the platform picks the extension
#   --platform  slack          128x128 PNG,  < 128 KB   (shown ~22-32 px)
#               discord        128x128 PNG,  < 256 KB   (shown 32 px)
#               telegram       512x512 WebP, < 512 KB, alpha required (sticker)
#               telegram-emoji 100x100 WebP, < 256 KB   (Premium custom emoji)
#               line           180x180 PNG,  < 1 MB     (LINE emoji)
#               generic        512x512 PNG,  no cap
#   --cutout    auto (default): flood-fill the flat background away unless the
#               input already has transparent corners; yes: always; no: never;
#               key: remove the corner colour EVERYWHERE (global chroma key +
#               1 px alpha erode) — for subjects with enclosed pockets the
#               corner flood cannot reach (long hair against the shoulders)
#   --fuzz      flood-fill tolerance (default 10%)
#   --pad       fraction of the edge kept clear (default 0.04; emoji fill
#               the canvas — they are shown tiny)
#   --stroke    outline width in px around the cut-out subject (default 0;
#               Telegram recommends a white stroke, ~12 px at 512)
#   --stroke-color  outline colour (default #ffffff)
#
# Prints one RESULT: line: file, platform, width, height, bytes, cap,
# within_cap, channels, coverage (opaque fraction), corner_alpha.
# Byte cap misses are retried with stronger quantisation before failing.
# Deterministic for a given input + options; re-running is free.
#
# Tooling: ImageMagick (magick) with WebP, curl for URLs.

set -euo pipefail
die() { echo "emoji-fit: $*" >&2; exit 1; }
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'

[ $# -lt 3 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
INPUT="$1"; STEM="$2"; shift 2
PLATFORM=""; CUTOUT="auto"; FUZZ="10%"; PAD="0.04"; STROKE=0; STROKE_COLOR="#ffffff"
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) PLATFORM="$2"; shift 2 ;;
    --cutout) CUTOUT="$2"; shift 2 ;;
    --fuzz) FUZZ="$2"; shift 2 ;;
    --pad) PAD="$2"; shift 2 ;;
    --stroke) STROKE="$2"; shift 2 ;;
    --stroke-color) STROKE_COLOR="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

# The platform table.
case "$PLATFORM" in
  slack)          SIZE=128; FMT=png;  CAP=131072 ;;
  discord)        SIZE=128; FMT=png;  CAP=262144 ;;
  telegram)       SIZE=512; FMT=webp; CAP=524288 ;;
  telegram-emoji) SIZE=100; FMT=webp; CAP=262144 ;;
  line)           SIZE=180; FMT=png;  CAP=1048576 ;;
  generic)        SIZE=512; FMT=png;  CAP=0 ;;
  "") die "--platform is required (slack | discord | telegram | telegram-emoji | line | generic)" ;;
  *) die "unknown platform: $PLATFORM" ;;
esac
case "$CUTOUT" in auto|yes|no|key) ;; *) die "--cutout must be auto | yes | no | key" ;; esac
case "$STROKE_COLOR" in $HEX) ;; *) die "--stroke-color must be #rrggbb" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"
OUTPUT="${STEM}.${FMT}"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/emojifit.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) command -v curl >/dev/null 2>&1 || die "curl not found"; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac
mkdir -p "$(dirname "$OUTPUT")"

# 1) Decide whether to cut the background away. `auto` keeps an input whose
#    four corners are already transparent (a finished PNG, a drawn tile).
if [ "$CUTOUT" = auto ]; then
  read -r W H < <(magick identify -format '%w %h\n' "$SRC")
  CHANNELS="$(magick "$SRC" -format '%[channels]' info:)"
  if [[ "$CHANNELS" == *a* ]]; then
    CORNERS="$(magick "$SRC" -alpha extract -format '%[fx:p{0,0}+p{w-1,0}+p{0,h-1}+p{w-1,h-1}]' info:)"
    if python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) < 0.02 else 1)' "$CORNERS"; then CUTOUT=no; else CUTOUT=yes; fi
  else
    CUTOUT=yes
  fi
fi

# 2) Cut out (flood fill from the four corners, joined by a 1px border so a
#    subject touching an edge cannot wall a corner off) and trim.
CUT="$WORK/cut.png"
if [ "$CUTOUT" = yes ]; then
  read -r W H < <(magick identify -format '%w %h\n' "$SRC")
  CORNER_COLOR="$(magick "$SRC" -format '%[pixel:p{0,0}]' info:)"
  magick "$SRC" -alpha set -bordercolor "$CORNER_COLOR" -border 1 \
    -fuzz "$FUZZ" -fill none \
    -draw "color 0,0 floodfill" -draw "color $((W+1)),0 floodfill" \
    -draw "color 0,$((H+1)) floodfill" -draw "color $((W+1)),$((H+1)) floodfill" \
    -shave 1x1 -trim +repage "$CUT" || die "cut-out failed"
elif [ "$CUTOUT" = key ]; then
  CORNER_COLOR="$(magick "$SRC" -format '%[pixel:p{0,0}]' info:)"
  magick "$SRC" -alpha set -fuzz "$FUZZ" -transparent "$CORNER_COLOR" \
    \( +clone -alpha extract -morphology Erode Diamond:1 \) \
    -alpha off -compose CopyOpacity -composite -trim +repage "$CUT" || die "key failed"
else
  magick "$SRC" -alpha set -trim +repage "$CUT"
fi

# 3) Optional outline: grow the alpha by STROKE px, fill with the colour,
#    put the subject back on top. Done at the working resolution before the
#    fit so the stroke scales with the subject.
if [ "$STROKE" -gt 0 ] 2>/dev/null; then
  magick "$CUT" -bordercolor none -border "$STROKE" \
    \( +clone -alpha extract -morphology Dilate "Disk:${STROKE}" -background "$STROKE_COLOR" -alpha shape \) \
    +swap -composite +repage "$WORK/stroked.png"
  CUT="$WORK/stroked.png"
fi

# 4) Fit on the platform canvas, transparent.
INNER="$(python3 -c 'import sys; s=int(sys.argv[1]); p=float(sys.argv[2]); print(int(round(s*(1-2*p))))' "$SIZE" "$PAD")"
FIT="$WORK/fit.png"
magick "$CUT" -resize "${INNER}x${INNER}" -background none -gravity center -extent "${SIZE}x${SIZE}" "$FIT"

# 5) Encode for the platform; squeeze under the byte cap if needed.
encode() { # $1 = quality tier 0..3
  case "$FMT" in
    png)
      case "$1" in
        0) magick "$FIT" -strip -define png:compression-level=9 "$OUTPUT" ;;
        1) magick "$FIT" -strip -colors 256 -define png:compression-level=9 "$OUTPUT" ;;
        2) magick "$FIT" -strip -colors 128 -dither FloydSteinberg -define png:compression-level=9 "$OUTPUT" ;;
        *) magick "$FIT" -strip -colors 64 -dither FloydSteinberg -define png:compression-level=9 "$OUTPUT" ;;
      esac ;;
    webp)
      case "$1" in
        0) magick "$FIT" -strip -define webp:lossless=true "$OUTPUT" ;;
        1) magick "$FIT" -strip -quality 90 -define webp:alpha-quality=100 "$OUTPUT" ;;
        2) magick "$FIT" -strip -quality 75 -define webp:alpha-quality=90 "$OUTPUT" ;;
        *) magick "$FIT" -strip -quality 55 -define webp:alpha-quality=80 "$OUTPUT" ;;
      esac ;;
  esac
}
TIER=0; encode $TIER
BYTES="$(magick identify -format '%B' "$OUTPUT")"
while [ "$CAP" -gt 0 ] && [ "$BYTES" -ge "$CAP" ] && [ "$TIER" -lt 3 ]; do
  TIER=$((TIER+1)); encode $TIER
  BYTES="$(magick identify -format '%B' "$OUTPUT")"
done

read -r RW RH BYTES < <(magick identify -format '%w %h %B\n' "$OUTPUT")
[ "$RW" = "$SIZE" ] && [ "$RH" = "$SIZE" ] || die "rendered ${RW}x${RH}, expected ${SIZE}x${SIZE}"
CH="$(magick "$OUTPUT" -format '%[channels]' info: | tr -s ' ')"
COVERAGE="$(magick "$OUTPUT" -alpha extract -format '%[fx:mean]' info:)"
CORNER="$(magick "$OUTPUT" -alpha extract -format '%[fx:p{0,0}]' info:)"
if [ "$CAP" -gt 0 ]; then WITHIN=$([ "$BYTES" -lt "$CAP" ] && echo yes || echo no); else WITHIN=yes; fi
echo "RESULT: file=$OUTPUT platform=$PLATFORM width=$RW height=$RH bytes=$BYTES cap=$CAP within_cap=$WITHIN channels=$CH coverage=$COVERAGE corner_alpha=$CORNER cutout=$CUTOUT stroke=$STROKE"
[ "$WITHIN" = yes ] || die "over the $PLATFORM byte cap ($BYTES >= $CAP) after quantisation — report as a gap"
