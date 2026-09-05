#!/usr/bin/env bash
#
# icon-finish.sh — the `generate-icon` leaf's finish: turn one generated
# image (drawn on a flat single-colour background) into an icon PNG at an
# exact size with the asked background.
#
# Usage:
#   icon-finish.sh INPUT OUTPUT [--size PX] [--background transparent|tile|'#rrggbb']
#                  [--tile '#rrggbb'] [--pad FRACTION] [--fuzz PCT] [--keep-bg]
#     INPUT   local path or http(s) URL (what image_generate returned)
#     OUTPUT  the PNG to write (parent dir is created)
#   --size        canvas edge, square (default 1024)
#   --background  transparent (default): the flat generated background is
#                 removed by flood-filling from the four corners;
#                 tile: the cut-out subject at 76% on a rounded square tile of
#                 --tile colour (22% radius);
#                 '#rrggbb': the cut-out subject on a flat fill
#   --pad         transparent/fill: fraction of the edge kept clear around the
#                 subject (default 0.08)
#   --fuzz        flood-fill tolerance for the background removal (default 10%)
#   --keep-bg     skip the cut-out (the model was asked to draw the background
#                 itself, e.g. a full app tile); only fit + resize
#
# Prints one RESULT: line: path, width, height, bytes, channels, coverage
# (opaque fraction), corner_alpha (0 = corners transparent). Deterministic
# for a given input + options; re-running is free.
#
# Tooling: ImageMagick (magick), curl for URLs.

set -euo pipefail
die() { echo "icon-finish: $*" >&2; exit 1; }
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
INPUT="$1"; OUTPUT="$2"; shift 2
SIZE=1024; BG="transparent"; TILE="#22d3ee"; PAD="0.08"; FUZZ="10%"; KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --size) SIZE="$2"; shift 2 ;;
    --background) BG="$2"; shift 2 ;;
    --tile) TILE="$2"; shift 2 ;;
    --pad) PAD="$2"; shift 2 ;;
    --fuzz) FUZZ="$2"; shift 2 ;;
    --keep-bg) KEEP=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
case "$BG" in transparent|tile|$HEX) ;; *) die "--background must be transparent | tile | #rrggbb" ;; esac
case "$TILE" in $HEX) ;; *) die "--tile must be #rrggbb" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/iconfin.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) command -v curl >/dev/null 2>&1 || die "curl not found"; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac
mkdir -p "$(dirname "$OUTPUT")"

# 1) Cut the subject out of the flat generated background (unless kept):
#    flood-fill transparent from each corner with tolerance, then trim.
CUT="$WORK/cut.png"
if [ "$KEEP" = 1 ]; then
  magick "$SRC" -alpha set "$CUT"
else
  read -r W H < <(magick identify -format '%w %h\n' "$SRC")
  # A 1px border in the top-left corner's colour joins the four corners into
  # one region, so a subject touching an edge cannot wall a corner off.
  CORNER_COLOR="$(magick "$SRC" -format '%[pixel:p{0,0}]' info:)"
  magick "$SRC" -alpha set -bordercolor "$CORNER_COLOR" -border 1 \
    -fuzz "$FUZZ" -fill none \
    -draw "color 0,0 floodfill" -draw "color $((W+1)),0 floodfill" \
    -draw "color 0,$((H+1)) floodfill" -draw "color $((W+1)),$((H+1)) floodfill" \
    -shave 1x1 -trim +repage "$CUT" || die "cut-out failed"
fi

# 2) Fit onto the asked canvas.
case "$BG" in
  transparent)
    INNER="$(python3 -c 'import sys; s=int(sys.argv[1]); p=float(sys.argv[2]); print(int(round(s*(1-2*p))))' "$SIZE" "$PAD")"
    magick "$CUT" -resize "${INNER}x${INNER}" -background none -gravity center -extent "${SIZE}x${SIZE}" "$OUTPUT" ;;
  tile)
    R=$(( SIZE * 22 / 100 )); INNER=$(( SIZE * 76 / 100 ))
    magick -size "${SIZE}x${SIZE}" xc:none -fill "$TILE" -draw "roundrectangle 0,0 $((SIZE-1)),$((SIZE-1)) $R,$R" \
      \( "$CUT" -resize "${INNER}x${INNER}" \) -gravity center -composite "$OUTPUT" ;;
  *)
    INNER="$(python3 -c 'import sys; s=int(sys.argv[1]); p=float(sys.argv[2]); print(int(round(s*(1-2*p))))' "$SIZE" "$PAD")"
    magick -size "${SIZE}x${SIZE}" "xc:${BG}" \( "$CUT" -resize "${INNER}x${INNER}" \) -gravity center -composite "$OUTPUT" ;;
esac
magick "$OUTPUT" -strip -define png:compression-level=9 "$OUTPUT"

read -r RW RH BYTES < <(magick identify -format '%w %h %B\n' "$OUTPUT")
[ "$RW" = "$SIZE" ] && [ "$RH" = "$SIZE" ] || die "rendered ${RW}x${RH}, expected ${SIZE}x${SIZE}"
CH="$(magick "$OUTPUT" -format '%[channels]' info: | tr -s ' ')"
COVERAGE="$(magick "$OUTPUT" -alpha extract -format '%[fx:mean]' info:)"
CORNER="$(magick "$OUTPUT" -alpha extract -format '%[fx:p{0,0}]' info:)"
echo "RESULT: png=$OUTPUT width=$RW height=$RH bytes=$BYTES channels=$CH coverage=$COVERAGE corner_alpha=$CORNER background=$BG"
