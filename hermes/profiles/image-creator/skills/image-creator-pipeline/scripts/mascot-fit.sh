#!/usr/bin/env bash
#
# mascot-fit.sh — the mascot family's finish: turn one image (a generated
# character on a flat background, or an already transparent PNG) into a
# mascot PNG at an exact square size, cut out, optionally cropped to the
# bust or the head, on a transparent, chroma-key or flat background.
#
# Usage:
#   mascot-fit.sh INPUT OUTPUT [--size PX] [--background transparent|chromakey|'#rrggbb']
#                 [--key '#rrggbb'] [--cutout auto|yes|no|key] [--fuzz PCT]
#                 [--crop full|bust|head] [--crop-frac F] [--pad FRACTION]
#                 [--stroke PX] [--stroke-color '#rrggbb']
#     INPUT   local path or http(s) URL (what image_generate returned)
#     OUTPUT  the PNG to write (parent dir is created)
#   --size        canvas edge, square (default 1024)
#   --background  transparent (default): the cut-out subject on alpha;
#                 chromakey: the cut-out subject RE-COMPOSITED on a flat
#                 --key colour (default #00ff00) — never the model's own
#                 green, which carries shading and does not key cleanly;
#                 '#rrggbb': the cut-out subject on a flat fill
#   --key         the chroma-key colour (default #00ff00; use #0000ff when
#                 the palette contains green)
#   --cutout      auto (default): flood-fill the flat background away unless
#                 the input already has transparent corners; yes: always;
#                 no: never; key: remove the corner colour EVERYWHERE (global
#                 chroma key + 1 px alpha erode) — for background trapped in
#                 pockets the corner flood cannot reach (between an arm and
#                 the body, under a tail)
#   --fuzz        flood-fill / key tolerance (default 10%)
#   --crop        full (default): the whole subject; bust: the top part of
#                 the subject's height (--crop-frac, default 0.55); head:
#                 the top part (--crop-frac, default 0.40). Fractions are of
#                 the trimmed subject, measured from the top.
#   --pad         fraction of the edge kept clear around the subject
#                 (default 0.06)
#   --stroke      outline width in px around the cut-out subject (default 0)
#   --stroke-color  outline colour (default #ffffff)
#
# Prints one RESULT: line: png, width, height, bytes, channels, coverage
# (opaque fraction), corner_alpha (0 = corners transparent), key_px (opaque
# pixels still near the removed background colour — 0 is clean), plus the
# options used. Deterministic for a given input + options; re-running is free.
#
# Tooling: ImageMagick (magick), curl for URLs.

set -euo pipefail
die() { echo "mascot-fit: $*" >&2; exit 1; }
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
INPUT="$1"; OUTPUT="$2"; shift 2
SIZE=1024; BG="transparent"; KEY="#00ff00"; CUTOUT="auto"; FUZZ="10%"
CROP="full"; CROP_FRAC=""; PAD="0.06"; STROKE=0; STROKE_COLOR="#ffffff"
while [ $# -gt 0 ]; do
  case "$1" in
    --size) SIZE="$2"; shift 2 ;;
    --background) BG="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --cutout) CUTOUT="$2"; shift 2 ;;
    --fuzz) FUZZ="$2"; shift 2 ;;
    --crop) CROP="$2"; shift 2 ;;
    --crop-frac) CROP_FRAC="$2"; shift 2 ;;
    --pad) PAD="$2"; shift 2 ;;
    --stroke) STROKE="$2"; shift 2 ;;
    --stroke-color) STROKE_COLOR="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
case "$BG" in transparent|chromakey|$HEX) ;; *) die "--background must be transparent | chromakey | #rrggbb" ;; esac
case "$KEY" in $HEX) ;; *) die "--key must be #rrggbb" ;; esac
case "$CUTOUT" in auto|yes|no|key) ;; *) die "--cutout must be auto | yes | no | key" ;; esac
case "$CROP" in full|bust|head) ;; *) die "--crop must be full | bust | head" ;; esac
case "$STROKE_COLOR" in $HEX) ;; *) die "--stroke-color must be #rrggbb" ;; esac
if [ -z "$CROP_FRAC" ]; then
  case "$CROP" in bust) CROP_FRAC="0.55" ;; head) CROP_FRAC="0.40" ;; *) CROP_FRAC="1" ;; esac
fi
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/mascotfit.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) command -v curl >/dev/null 2>&1 || die "curl not found"; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac
mkdir -p "$(dirname "$OUTPUT")"

# 1) Decide whether to cut the background away. `auto` keeps an input whose
#    four corners are already transparent (a finished mascot PNG).
if [ "$CUTOUT" = auto ]; then
  CHANNELS="$(magick "$SRC" -format '%[channels]' info:)"
  if [[ "$CHANNELS" == *a* ]]; then
    CORNERS="$(magick "$SRC" -alpha extract -format '%[fx:p{0,0}+p{w-1,0}+p{0,h-1}+p{w-1,h-1}]' info:)"
    if python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) < 0.02 else 1)' "$CORNERS"; then CUTOUT=no; else CUTOUT=yes; fi
  else
    CUTOUT=yes
  fi
fi

# 2) Cut out (flood fill from the four corners, joined by a 1px border so a
#    subject touching an edge cannot wall a corner off; or a global key) and
#    trim. Remember the removed colour so the RESULT can count what is left.
CUT="$WORK/cut.png"; BGCOLOR=""
if [ "$CUTOUT" = yes ]; then
  read -r W H < <(magick identify -format '%w %h\n' "$SRC")
  BGCOLOR="#$(magick "$SRC" -alpha off -depth 8 -format '%[hex:p{0,0}]' info:)"
  magick "$SRC" -alpha set -bordercolor "$BGCOLOR" -border 1 \
    -fuzz "$FUZZ" -fill none \
    -draw "color 0,0 floodfill" -draw "color $((W+1)),0 floodfill" \
    -draw "color 0,$((H+1)) floodfill" -draw "color $((W+1)),$((H+1)) floodfill" \
    -shave 1x1 -trim +repage "$CUT" || die "cut-out failed"
elif [ "$CUTOUT" = key ]; then
  BGCOLOR="#$(magick "$SRC" -alpha off -depth 8 -format '%[hex:p{0,0}]' info:)"
  magick "$SRC" -alpha set -fuzz "$FUZZ" -transparent "$BGCOLOR" \
    \( +clone -alpha extract -morphology Erode Diamond:1 \) \
    -alpha off -compose CopyOpacity -composite -trim +repage "$CUT" || die "key failed"
else
  magick "$SRC" -alpha set -trim +repage "$CUT"
fi

# 3) Optional crop to the bust / head: keep the top fraction of the trimmed
#    subject, then trim again so the fit is tight on what remains.
if [ "$CROP" != full ]; then
  read -r CW CH0 < <(magick identify -format '%w %h\n' "$CUT")
  KEEP_H="$(python3 -c 'import sys; h=int(sys.argv[1]); f=float(sys.argv[2]); print(max(1, int(round(h*f))))' "$CH0" "$CROP_FRAC")"
  magick "$CUT" -crop "${CW}x${KEEP_H}+0+0" +repage -trim +repage "$WORK/cropped.png"
  CUT="$WORK/cropped.png"
fi

# 4) Optional outline: grow the alpha by STROKE px, fill with the colour,
#    put the subject back on top — at the working resolution, before the fit.
if [ "$STROKE" -gt 0 ] 2>/dev/null; then
  magick "$CUT" -bordercolor none -border "$STROKE" \
    \( +clone -alpha extract -morphology Dilate "Disk:${STROKE}" -background "$STROKE_COLOR" -alpha shape \) \
    +swap -composite +repage "$WORK/stroked.png"
  CUT="$WORK/stroked.png"
fi

# 5) Fit on the square canvas with the asked background.
INNER="$(python3 -c 'import sys; s=int(sys.argv[1]); p=float(sys.argv[2]); print(int(round(s*(1-2*p))))' "$SIZE" "$PAD")"
FIT="$WORK/fit.png"
magick "$CUT" -resize "${INNER}x${INNER}" -background none -gravity center -extent "${SIZE}x${SIZE}" "$FIT"
case "$BG" in
  transparent) magick "$FIT" -strip -define png:compression-level=9 "$OUTPUT" ;;
  chromakey)   magick -size "${SIZE}x${SIZE}" "xc:${KEY}" "$FIT" -gravity center -composite -alpha off -strip -define png:compression-level=9 "$OUTPUT" ;;
  *)           magick -size "${SIZE}x${SIZE}" "xc:${BG}" "$FIT" -gravity center -composite -alpha off -strip -define png:compression-level=9 "$OUTPUT" ;;
esac

read -r RW RH BYTES < <(magick identify -format '%w %h %B\n' "$OUTPUT")
[ "$RW" = "$SIZE" ] && [ "$RH" = "$SIZE" ] || die "rendered ${RW}x${RH}, expected ${SIZE}x${SIZE}"
CH="$(magick "$OUTPUT" -format '%[channels]' info: | tr -s ' ')"
# Coverage and corner alpha are read from the transparent fit, so they
# describe the subject even when the delivery is on a flat / key colour.
COVERAGE="$(magick "$FIT" -alpha extract -format '%[fx:mean]' info:)"
CORNER="$(magick "$OUTPUT" -alpha extract -format '%[fx:p{0,0}]' info:)"
KEY_PX=0
if [ -n "$BGCOLOR" ]; then
  # Opaque pixels of the fit still within 25% of the removed colour.
  KEY_PX="$(magick "$FIT" \( +clone -alpha off -fuzz 25% -fill black +opaque "$BGCOLOR" -fill white -opaque "$BGCOLOR" \) \
    \( -clone 0 -alpha extract -threshold 50% \) -delete 0 -compose Multiply -composite -format '%[fx:round(mean*w*h)]' info:)"
fi
BGOUT="$BG"; [ "$BG" = chromakey ] && BGOUT="chromakey($KEY)"
echo "RESULT: png=$OUTPUT width=$RW height=$RH bytes=$BYTES channels=$CH coverage=$COVERAGE corner_alpha=$CORNER key_px=$KEY_PX background=$BGOUT cutout=$CUTOUT crop=$CROP stroke=$STROKE"
