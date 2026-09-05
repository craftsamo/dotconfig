#!/usr/bin/env bash
#
# mascot-measure.sh — the `analyze-mascot` leaf's instrument: measure one
# mascot file or a whole concept / pack directory and lay out the sheets
# vision needs. Writes nothing but the sheets.
#
# Usage:
#   mascot-measure.sh SOURCE [--sheet-dir DIR] [--against ANCHOR] [--palette 'hex,hex,…']
#     SOURCE      one image, or a directory (every png/webp/jpg inside,
#                 sheets, raws and prompt files excluded)
#   --sheet-dir   where to write pack.png (256 px on grey), pack64.png (the
#                 64 px read, point-magnified 4x), silhouette.png (alpha as
#                 black on white, 160 px), light.png / dark.png (128 px on a
#                 light and a dark page) and, with --against, anchor.png
#                 (the anchor at 256 beside item 1)
#   --against     the concept anchor the files must match
#   --palette     the palette the form asked for, as comma-separated #rrggbb;
#                 each measured top colour is matched to its nearest asked
#                 colour (distance in RGB, 0-441) so drift is a number
#
# Prints:
#   MEASURE:  per file — file, width, height, square, format, bytes, alpha,
#             corner_alpha, background (transparent | chromakey | flat, from
#             the corner), coverage, key_px (opaque pixels pure chroma green
#             or blue — on a transparent file a key that leaked; on a
#             chromakey file the background itself), bbox (the subject's
#             bounding box as WxH+X+Y), fill (bbox area / canvas area)
#   PALETTE:  per file — the top 8 opaque colours with their share, and
#             with --palette the nearest asked colour + distance for each
#   SUMMARY:  files, square (count), alpha (count), leaked (transparent files
#             with key_px > 50)
#   SHEET:    one line per sheet written

set -euo pipefail
die() { echo "mascot-measure: $*" >&2; exit 1; }

[ $# -lt 1 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SRC="$1"; shift
SHEET_DIR=""; AGAINST=""; PALETTE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sheet-dir) SHEET_DIR="$2"; shift 2 ;;
    --against) AGAINST="$2"; shift 2 ;;
    --palette) PALETTE="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -e "$SRC" ] || die "source not found: $SRC"
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/mascotmeasure.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
FILES=(); SQUARE=0; WITH_ALPHA=0; LEAKED=0

palette_line() { # $1 = file → PALETTE: line (top 8 opaque colours)
  local F="$1"
  magick "${F}[0]" -alpha set -channel A -threshold 50% +channel -depth 8 +dither -colors 8 -format %c histogram:info:- 2>/dev/null \
    | python3 -c '
import re, sys
asked = [c for c in sys.argv[1].split(",") if c.strip()] if len(sys.argv) > 1 else []
def rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
rows = []
for line in sys.stdin:
    m = re.match(r"\s*(\d+):\s*\(([^)]*)\)\s*(#[0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", line)
    if not m: continue
    n, _, hx, a = m.groups()
    if a is not None and int(a, 16) < 128: continue
    rows.append((int(n), hx.lower()))
total = sum(n for n, _ in rows) or 1
rows.sort(reverse=True)
out = []
for i, (n, hx) in enumerate(rows[:8], 1):
    share = f"{100*n/total:.0f}%"
    if asked:
        r, g, b = rgb(hx)
        best = min(asked, key=lambda c: sum((x-y)**2 for x, y in zip(rgb(c.strip()), (r, g, b))))
        d = int(sum((x-y)**2 for x, y in zip(rgb(best.strip()), (r, g, b))) ** 0.5)
        out.append(f"c{i}={hx}:{share}~{best.strip().lower()}:d{d}")
    else:
        out.append(f"c{i}={hx}:{share}")
print(" ".join(out))
' "$PALETTE"
}

measure_one() { # $1 = file
  local F="$1" W H FORMAT BYTES CH ALPHA CORNER COVERAGE KEY BBOX SQ FILL
  read -r W H FORMAT BYTES < <(magick identify -format '%w %h %m %B\n' "${F}[0]")
  FORMAT="$(printf '%s' "$FORMAT" | tr '[:upper:]' '[:lower:]')"
  CH="$(magick "${F}[0]" -format '%[channels]' info:)"
  case "$CH" in *a*) ALPHA=yes; WITH_ALPHA=$((WITH_ALPHA+1)) ;; *) ALPHA=no ;; esac
  [ "$W" = "$H" ] && { SQ=yes; SQUARE=$((SQUARE+1)); } || SQ=no
  CORNER="$(magick "${F}[0]" -alpha set -alpha extract -format '%[fx:p{0,0}]' info:)"
  COVERAGE="$(magick "${F}[0]" -alpha set -alpha extract -format '%[fx:mean]' info:)"
  # Opaque pixels within 20% of pure chroma green or blue: a leaked key.
  KEY="$(magick "${F}[0]" -alpha set \( +clone -alpha off -fuzz 20% -fill black +opaque '#00ff00' -fill white -opaque '#00ff00' \) \
    \( -clone 0 -alpha off -fuzz 20% -fill black +opaque '#0000ff' -fill white -opaque '#0000ff' \) \
    \( -clone 1 -clone 2 -compose Lighten -composite \) -delete 1,2 \
    \( -clone 0 -alpha extract -threshold 50% \) -delete 0 -compose Multiply -composite -format '%[fx:round(mean*w*h)]' info:)"
  # A flat delivery whose corner is pure green / blue is a chroma-key file
  # by design: its key pixels are the background, not a leak.
  local BGKIND=transparent CORNER_HEX
  if [ "$ALPHA" = no ] || [ "$CORNER" != 0 ]; then
    CORNER_HEX="$(magick "${F}[0]" -alpha off -depth 8 -format '%[hex:p{0,0}]' info: | tr '[:upper:]' '[:lower:]')"
    case "$CORNER_HEX" in 00ff00|0000ff) BGKIND=chromakey ;; *) BGKIND=flat ;; esac
  fi
  [ "$BGKIND" = transparent ] && [ "$KEY" -gt 50 ] && LEAKED=$((LEAKED+1))
  BBOX="$(magick "${F}[0]" -alpha set -trim -format '%wx%h%X%Y' info: 2>/dev/null || echo "0x0+0+0")"
  FILL="$(python3 -c 'import sys,re; m=re.match(r"(\d+)x(\d+)",sys.argv[1]); w,h=int(sys.argv[2]),int(sys.argv[3]); print(f"{int(m.group(1))*int(m.group(2))/(w*h):.2f}" if m else "0")' "$BBOX" "$W" "$H")"
  echo "MEASURE: file=$F width=$W height=$H square=$SQ format=$FORMAT bytes=$BYTES alpha=$ALPHA corner_alpha=$CORNER background=$BGKIND coverage=$COVERAGE key_px=$KEY bbox=$BBOX fill=$FILL"
  echo "PALETTE: file=$F $(palette_line "$F")"
  FILES+=("$F")
}

if [ -d "$SRC" ]; then
  for f in "$SRC"/*.png "$SRC"/*.webp "$SRC"/*.jpg "$SRC"/*.jpeg; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in sheet*|pack*|silhouette*|light.png|dark.png|anchor.png) continue ;; esac
    measure_one "$f"
  done
else
  measure_one "$SRC"
fi
[ "${#FILES[@]}" -gt 0 ] || die "no images found"
echo "SUMMARY: files=${#FILES[@]} square=$SQUARE alpha=$WITH_ALPHA leaked=$LEAKED"

if [ -n "$SHEET_DIR" ]; then
  mkdir -p "$SHEET_DIR"
  row() { # $1 size, $2 bg, $3 out, $4 pad, $5 mode (plain|silhouette)
    local TILES=() f
    for f in "${FILES[@]}"; do
      local t="$WORK/$(basename "$f").$1.$5.png"
      if [ "$5" = silhouette ]; then
        magick "${f}[0]" -alpha set -alpha extract -negate -resize "${1}x${1}" -background "$2" -gravity center -extent "$(( $1 + $4 ))x$(( $1 + $4 ))" "$t"
      else
        magick "${f}[0]" -alpha set -resize "${1}x${1}" -background "$2" -gravity center -extent "$(( $1 + $4 ))x$(( $1 + $4 ))" -flatten "$t"
      fi
      TILES+=("$t")
    done
    magick "${TILES[@]}" -background "$2" +append "$3"
  }
  row 256 '#888888' "$SHEET_DIR/pack.png" 16 plain
  row 64 '#888888' "$WORK/pack64.png" 4 plain
  magick "$WORK/pack64.png" -filter point -resize 400% "$SHEET_DIR/pack64.png"
  row 160 '#ffffff' "$SHEET_DIR/silhouette.png" 16 silhouette
  row 128 '#ffffff' "$SHEET_DIR/light.png" 12 plain
  row 128 '#1e1f22' "$SHEET_DIR/dark.png" 12 plain
  echo "SHEET: $SHEET_DIR/pack.png (256 on grey) | pack64.png (64 px read, 4x point) | silhouette.png (alpha as black on white, 160) | light.png / dark.png (128 on light / dark page)"
  if [ -n "$AGAINST" ]; then
    [ -f "$AGAINST" ] || die "against not found: $AGAINST"
    magick "${AGAINST}[0]" -alpha set -resize 256x256 -background '#888888' -gravity center -extent 272x272 -flatten "$WORK/a.png"
    magick "${FILES[0]}[0]" -alpha set -resize 256x256 -background '#888888' -gravity center -extent 272x272 -flatten "$WORK/i.png"
    magick "$WORK/a.png" "$WORK/i.png" -background '#888888' +append "$SHEET_DIR/anchor.png"
    echo "SHEET: $SHEET_DIR/anchor.png (anchor at 256 | item 1 at 256)"
  fi
fi
