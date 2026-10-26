#!/usr/bin/env bash
#
# icon-fetch.sh — the `source-icon` leaf's renderer: one icon from the
# Iconify API (Lucide, Tabler, Phosphor, Material Symbols, Simple Icons, …
# 200k+ glyphs, no key) as SVG + transparent PNG, with its license recorded.
#
# Usage:
#   icon-fetch.sh --icon SET:NAME --out DIR [--color '#rrggbb'] [--size PX]
#                 [--background transparent|tile|'#rrggbb'] [--tile '#rrggbb']
#                 [--pad FRACTION] [--slug NAME]
#   icon-fetch.sh --search WORD [--limit N]        # candidates only, no files
#
# Backgrounds:
#   transparent (default)  the glyph alone in --color on transparency
#   tile                   a white glyph (60% of the edge) centred on a rounded
#                          square tile of --tile colour (22% radius)
#   '#rrggbb'              the glyph in --color on a flat square fill
#
# Writes into DIR:  icon_<slug>.svg (the fetched source, colour applied) and
#                   icon_<slug>_<size>.png (exactly size x size)
# and prints one `RESULT:` line (paths, size, set, coverage) plus a
# `LICENSE:` line to copy into the report verbatim.
#
# Tooling: curl, librsvg (rsvg-convert — ImageMagick's own SVG path silently
# drops stroked glyphs), ImageMagick (magick), python3. Deterministic for a
# given icon id + options as long as the icon set does not change upstream —
# the fetched SVG is kept beside the PNG for that reason.

set -euo pipefail
die() { echo "icon-fetch: $*" >&2; exit 1; }
API="https://api.iconify.design"
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'

ICON=""; SEARCH=""; LIMIT=8; OUT=""; BG="transparent"; SLUG=""; COLOR="#000000"; SIZE=512; TILE="#22d3ee"; PAD=""
while [ $# -gt 0 ]; do
  case "$1" in
    --icon) ICON="$2"; shift 2 ;;
    --search) SEARCH="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --background) BG="$2"; shift 2 ;;
    --slug) SLUG="$2"; shift 2 ;;
    --color) COLOR="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --tile) TILE="$2"; shift 2 ;;
    --pad) PAD="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

if [ -n "$SEARCH" ]; then
  curl -sf -m 15 "$API/search?query=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$SEARCH")&limit=$LIMIT" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print("CANDIDATES: " + ", ".join(d.get("icons", [])) if d.get("icons") else "CANDIDATES: none")'
  exit 0
fi

[ -n "$ICON" ] || die "--icon SET:NAME is required (or --search WORD)"
[ -n "$OUT" ] || die "--out is required"
case "$ICON" in *:*) ;; *) die "--icon must be SET:NAME (e.g. lucide:rocket); use --search WORD to find one" ;; esac
case "$BG" in transparent|tile|$HEX) ;; *) die "--background must be transparent | tile | #rrggbb" ;; esac
case "$COLOR" in $HEX) ;; *) die "--color must be #rrggbb" ;; esac
case "$TILE" in $HEX) ;; *) die "--tile must be #rrggbb" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"
command -v rsvg-convert >/dev/null 2>&1 || die "rsvg-convert (librsvg) not found — ImageMagick's own SVG renderer drops stroked glyphs; report as a gap"
command -v curl >/dev/null 2>&1 || die "curl not found"

SET="${ICON%%:*}"; NAME="${ICON#*:}"
[ -n "$SLUG" ] || SLUG="$(printf '%s' "$ICON" | tr ':/' '--' | tr -c 'a-zA-Z0-9-\n' '-' | sed 's/--*/-/g; s/^-//; s/-$//')"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
SVG="$OUT/icon_${SLUG}.svg"; PNG="$OUT/icon_${SLUG}_${SIZE}.png"

# The glyph colour: tile = white glyph, otherwise --color.
GLYPH="$COLOR"; [ "$BG" = "tile" ] && GLYPH="#ffffff"
ENC_GLYPH="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$GLYPH")"

# Glyph render size inside the canvas.
if [ "$BG" = "tile" ]; then
  GSIZE=$(( SIZE * 60 / 100 ))
else
  [ -n "$PAD" ] || PAD="0"
  GSIZE="$(python3 -c 'import sys; s=int(sys.argv[1]); p=float(sys.argv[2]); print(int(round(s*(1-2*p))))' "$SIZE" "$PAD")"
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -sf -m 20 "$API/${SET}/${NAME}.svg?color=${ENC_GLYPH}&height=${GSIZE}" -o "$SVG" \
  || die "icon not found on the Iconify API: $ICON (try --search)"
grep -q '<svg' "$SVG" || die "the API did not return an SVG for $ICON"

# Rasterize the glyph on transparency, then compose the background.
rsvg-convert -w "$GSIZE" -h "$GSIZE" "$SVG" -o "$TMP/glyph.png"
case "$BG" in
  tile)
    R=$(( SIZE * 22 / 100 ))
    magick -size "${SIZE}x${SIZE}" xc:none -fill "$TILE" -draw "roundrectangle 0,0 $((SIZE-1)),$((SIZE-1)) $R,$R" \
      "$TMP/glyph.png" -gravity center -composite "$PNG" ;;
  transparent)
    magick -size "${SIZE}x${SIZE}" xc:none "$TMP/glyph.png" -gravity center -composite "$PNG" ;;
  *)
    magick -size "${SIZE}x${SIZE}" "xc:${BG}" "$TMP/glyph.png" -gravity center -composite "$PNG" ;;
esac
magick "$PNG" -strip -define png:compression-level=9 "$PNG"

read -r RW RH BYTES < <(magick identify -format '%w %h %B\n' "$PNG")
[ "$RW" = "$SIZE" ] && [ "$RH" = "$SIZE" ] || die "rendered ${RW}x${RH}, expected ${SIZE}x${SIZE}"
ALPHA="$(magick "$PNG" -format '%[channels]' info:)"
COVERAGE="$(magick "$PNG" -alpha extract -format '%[fx:mean]' info:)"

LIC="$(curl -sf -m 15 "$API/collections?prefixes=${SET}" | python3 "$(dirname "$0")/iconify-license.py" "$SET" 2>/dev/null \
  || echo "license lookup failed (record the set's license by hand)")"

echo "RESULT: png=$PNG svg=$SVG width=$RW height=$RH bytes=$BYTES channels=$ALPHA coverage=$COVERAGE set=$SET icon=$ICON background=$BG"
echo "LICENSE: $ICON — $LIC (via api.iconify.design)"
