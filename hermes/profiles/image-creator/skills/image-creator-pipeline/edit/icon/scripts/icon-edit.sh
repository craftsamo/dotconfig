#!/usr/bin/env bash
#
# icon-edit.sh — the `edit-icon` leaf: deterministic edits on an existing
# icon (PNG / WebP / JPG / SVG): recolour, background swap, cut-out, resize.
#
# Usage:
#   icon-edit.sh SOURCE OUTDIR [--color '#rrggbb'] [--background transparent|tile|'#rrggbb']
#                [--tile '#rrggbb'] [--sizes 512,256,64] [--cutout] [--pad F]
#                [--fuzz PCT] [--slug NAME]
#   --color      recolour: a raster's every opaque pixel takes this colour,
#                alpha kept (monochrome icons only); an SVG only gets its
#                currentColor substituted, other fills stay as drawn
#   --background transparent (default) | tile | '#rrggbb' — composed by
#                icon-finish.sh; a raster without alpha needs --cutout first
#   --cutout     remove the source's flat background (corner flood fill,
#                tolerance --fuzz, default 10%)
#   --sizes      comma list of square output edges (default: the source's
#                shorter edge, or 512 for an SVG)
#   --pad        fraction of the edge kept clear (default 0 — keep the
#                source's own framing; icon-finish trims only after --cutout)
#
# Writes OUTDIR/icon_<slug>_<size>.png per size (+ icon_<slug>.svg when the
# source is an SVG) and prints one RESULT: line per output.
# Tooling: ImageMagick (magick), librsvg (rsvg-convert) for SVG sources.

set -euo pipefail
die() { echo "icon-edit: $*" >&2; exit 1; }
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'
HERE="$(cd "$(dirname "$0")" && pwd)"
FINISH="$HERE/../../../scripts/icon-finish.sh"

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SRC="$1"; OUT="$2"; shift 2
COLOR=""; BG="transparent"; TILE="#22d3ee"; SIZES=""; CUTOUT=0; PAD="0"; FUZZ="10%"; SLUG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --color) COLOR="$2"; shift 2 ;;
    --background) BG="$2"; shift 2 ;;
    --tile) TILE="$2"; shift 2 ;;
    --sizes) SIZES="$2"; shift 2 ;;
    --cutout) CUTOUT=1; shift ;;
    --pad) PAD="$2"; shift 2 ;;
    --fuzz) FUZZ="$2"; shift 2 ;;
    --slug) SLUG="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -f "$SRC" ] || die "source not found: $SRC"
[ -x "$FINISH" ] || die "icon-finish.sh not found at $FINISH"
[ -z "$COLOR" ] || case "$COLOR" in $HEX) ;; *) die "--color must be #rrggbb" ;; esac
case "$BG" in transparent|tile|$HEX) ;; *) die "--background must be transparent | tile | #rrggbb" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
[ -n "$SLUG" ] || { SLUG="$(basename "$SRC")"; SLUG="${SLUG%.*}"; SLUG="${SLUG#icon_}"; SLUG="$(printf '%s' "$SLUG" | sed -E 's/_[0-9]+$//')"; }
WORK="$(mktemp -d "${TMPDIR:-/tmp}/iconedit.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT

# 1) A raster master to edit: rasterize an SVG large, else copy.
MASTER="$WORK/master.png"
RASTER_RECOLOR="$COLOR"   # an SVG is recoloured through currentColor only
case "$(printf '%s' "$SRC" | tr '[:upper:]' '[:lower:]')" in
  *.svg)
    command -v rsvg-convert >/dev/null 2>&1 || die "rsvg-convert (librsvg) not found — report as a gap"
    SVG_SRC="$SRC"
    if [ -n "$COLOR" ]; then
      SVG_SRC="$WORK/src.svg"; sed "s/currentColor/$COLOR/g" "$SRC" > "$SVG_SRC"
      grep -q "$COLOR" "$SVG_SRC" || echo "icon-edit: warning: the SVG has no currentColor; its fills are left as drawn" >&2
      RASTER_RECOLOR=""
    fi
    cp "$SVG_SRC" "$OUT/icon_${SLUG}.svg"
    rsvg-convert -w 2048 -h 2048 --keep-aspect-ratio "$SVG_SRC" -o "$MASTER" || die "rsvg-convert failed"
    [ -n "$SIZES" ] || SIZES=512 ;;
  *)
    magick "$SRC" -alpha set "$MASTER"
    if [ -z "$SIZES" ]; then
      read -r W H < <(magick identify -format '%w %h\n' "$MASTER"); SIZES=$(( W < H ? W : H ))
    fi ;;
esac

# 2) Cut-out first when asked, so recolour/background see a real alpha.
if [ "$CUTOUT" = 1 ]; then
  "$FINISH" "$MASTER" "$WORK/cut.png" --size "$(magick identify -format '%[fx:max(w,h)]' "$MASTER")" \
    --background transparent --pad 0 --fuzz "$FUZZ" >/dev/null
  MASTER="$WORK/cut.png"
fi

# 3) Recolour: paint every pixel the colour, keep the alpha as the mask.
if [ -n "$RASTER_RECOLOR" ]; then
  magick "$MASTER" -alpha extract "$WORK/mask.png"
  magick "$WORK/mask.png" -background "$COLOR" -alpha shape "$WORK/recolored.png"
  MASTER="$WORK/recolored.png"
fi

# 4) One output per size, composed on the asked background.
IFS=',' read -ra SZ <<< "$SIZES"
for s in "${SZ[@]}"; do
  s="$(printf '%s' "$s" | tr -d ' ')"
  "$FINISH" "$MASTER" "$OUT/icon_${SLUG}_${s}.png" --size "$s" --background "$BG" --tile "$TILE" --pad "$PAD" --keep-bg
done
