#!/usr/bin/env bash
#
# icon-measure.sh — the `analyze-icon` leaf's instrument: measure one icon
# file (PNG / WebP / JPG / SVG) and lay out a contact sheet for vision.
#
# Usage:
#   icon-measure.sh SOURCE [--sheet OUT.png] [--against OTHER]
#
# Prints:
#   MEASURE: file, width, height, channels, opaque, coverage (opaque
#            fraction), corner_alpha, mark_bbox (WxH+X+Y of the opaque
#            mark), mark_extent (longest bbox side / canvas edge — an icon
#            meant to be maskable wants <= 0.80), colors (distinct colours
#            after quantising to 16, over the opaque area), dominant (the
#            most frequent opaque colour), contrast_white / contrast_black
#            (WCAG ratio of the dominant colour against white / black)
#   SHEET:   the contact sheet path when --sheet was given: the icon at
#            16 (x4), 32 (x2), 64, 128 on mid-grey, then on white, then on
#            black; with --against, the other icon at 128 beside it
#
# Nothing is written except the sheet. Tooling: ImageMagick (magick),
# librsvg for SVG, python3 for the contrast arithmetic.

set -euo pipefail
die() { echo "icon-measure: $*" >&2; exit 1; }
[ $# -lt 1 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SRC="$1"; shift
SHEET=""; AGAINST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sheet) SHEET="$2"; shift 2 ;;
    --against) AGAINST="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -f "$SRC" ] || die "source not found: $SRC"
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/iconmeasure.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT

raster() { # $1 = source, $2 = out png
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    *.svg) command -v rsvg-convert >/dev/null 2>&1 || die "rsvg-convert not found"; rsvg-convert -w 512 -h 512 --keep-aspect-ratio "$1" -o "$2" ;;
    *) magick "$1" -alpha set "$2" ;;
  esac
}
raster "$SRC" "$WORK/src.png"

read -r W H < <(magick identify -format '%w %h\n' "$WORK/src.png")
CH="$(magick "$WORK/src.png" -format '%[channels]' info: | tr -s ' ')"
OPAQUE="$(magick "$WORK/src.png" -format '%[opaque]' info:)"
COVERAGE="$(magick "$WORK/src.png" -alpha extract -format '%[fx:mean]' info:)"
CORNER="$(magick "$WORK/src.png" -alpha extract -format '%[fx:p{0,0}]' info:)"
if [ "$OPAQUE" = "True" ]; then
  # No alpha: the mark is whatever differs from the corner colour.
  BBOX="$(magick "$WORK/src.png" -fuzz 4% -format '%@' info: 2>/dev/null || echo "${W}x${H}+0+0")"
else
  BBOX="$(magick "$WORK/src.png" -alpha extract -threshold 50% -format '%@' info: 2>/dev/null || echo "${W}x${H}+0+0")"
fi
EXTENT="$(python3 -c '
import re,sys
m=re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", sys.argv[1]); w,h=int(sys.argv[2]),int(sys.argv[3])
bw,bh=(int(m.group(1)),int(m.group(2))) if m else (w,h)
print(f"{max(bw,bh)/max(w,h):.3f}")' "$BBOX" "$W" "$H")"

# Colours over the opaque area: hard-threshold the alpha, quantise to 12
# with alpha, drop the transparent bucket, keep colours >= 1% of the rest.
STATS="$(magick "$WORK/src.png" -channel A -threshold 50% +channel -colors 12 -depth 8 -format '%c' histogram:info:- 2>/dev/null \
  | python3 -c '
import re,sys
rows=[]
for line in sys.stdin:
    m=re.match(r"\s*(\d+):\s*\((\d+),(\d+),(\d+)(?:,(\d+))?\)\s*(#[0-9A-Fa-f]{6})", line)
    if not m: continue
    count=int(m.group(1)); alpha=int(m.group(5)) if m.group(5) is not None else 255
    if alpha<128: continue
    rows.append((count, m.group(6).upper()))
total=sum(c for c,_ in rows) or 1
kept=sorted([(c,h) for c,h in rows if c/total>=0.01], reverse=True)
print(len(kept), kept[0][1] if kept else "?")')"
read -r COLORS DOMINANT <<< "$STATS"
CONTRAST="$(python3 -c '
import sys
h=sys.argv[1].lstrip("#")
if len(h)<6: print("? ?"); sys.exit()
r,g,b=(int(h[i:i+2],16)/255 for i in (0,2,4))
def lin(c): return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
L=0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
print(f"{(1.05)/(L+0.05):.2f} {(L+0.05)/0.05:.2f}")' "$DOMINANT")"
read -r CW CB <<< "$CONTRAST"

echo "MEASURE: file=$SRC width=$W height=$H channels=$CH opaque=$OPAQUE coverage=$COVERAGE corner_alpha=$CORNER mark_bbox=$BBOX mark_extent=$EXTENT colors=$COLORS dominant=$DOMINANT contrast_white=$CW contrast_black=$CB"

if [ -n "$SHEET" ]; then
  mkdir -p "$(dirname "$SHEET")"
  tile() { # $1 size, $2 scale, $3 bg, $4 out
    magick "$WORK/src.png" -resize "${1}x${1}" -scale "$(( $2 * 100 ))%" -background "$3" -gravity center -extent "$(( $1 * $2 + 16 ))x$(( $1 * $2 + 16 ))" -flatten "$4"
  }
  tile 16 4 '#888888' "$WORK/t16.png"; tile 32 2 '#888888' "$WORK/t32.png"; tile 64 1 '#888888' "$WORK/t64.png"; tile 128 1 '#888888' "$WORK/t128.png"
  tile 64 1 '#ffffff' "$WORK/w64.png"; tile 64 1 '#000000' "$WORK/b64.png"
  PARTS=("$WORK/t16.png" "$WORK/t32.png" "$WORK/t64.png" "$WORK/t128.png" "$WORK/w64.png" "$WORK/b64.png")
  if [ -n "$AGAINST" ]; then
    [ -f "$AGAINST" ] || die "against not found: $AGAINST"
    raster "$AGAINST" "$WORK/against.png"
    magick "$WORK/against.png" -resize 128x128 -background '#888888' -gravity center -extent 144x144 -flatten "$WORK/a128.png"
    PARTS+=("$WORK/a128.png")
  fi
  magick "${PARTS[@]}" -background '#888888' -gravity center +append "$SHEET"
  echo "SHEET: $SHEET (16x4, 32x2, 64, 128 on grey; 64 on white; 64 on black${AGAINST:+; against at 128})"
fi
