#!/usr/bin/env bash
#
# logo-to-icons.sh — render a logo SVG into a favicon + PNG icon set.
#
# Icons are DERIVED from the logo (not AI-generated). Uses rsvg-convert for a
# clean SVG raster and ImageMagick for the multi-resolution .ico + compositing.
#
# Usage:
#   logo-to-icons.sh LOGO.svg OUTDIR [options]
#   Options:
#     --bg COLOR      background for apple-icon + maskable (default #FFFFFF; "none" = transparent for PWA)
#     --color COLOR   substitute SVG `currentColor` (e.g. #E26E54)
#     --sizes LIST    extra square PNG sizes (default 16,32,48,180,192,512)
#     -h, --help
#
# Outputs in OUTDIR: favicon.ico, icon-<size>.png, apple-icon.png (flattened),
#   icon-maskable-512.png (80% safe zone), and a copy of icon.svg.
#
# Tooling: librsvg (rsvg-convert) + ImageMagick. Install: ./install.sh --deps

set -euo pipefail

die() { echo "logo-to-icons: $*" >&2; exit 1; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SVG="$1"; OUTDIR="$2"; shift 2
BG="#FFFFFF"; COLOR=""; SIZES="16,32,48,180,192,512"
while [ $# -gt 0 ]; do
  case "$1" in
    --bg) BG="$2"; shift 2 ;;
    --color) COLOR="$2"; shift 2 ;;
    --sizes) SIZES="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -f "$SVG" ] || die "logo SVG not found: $SVG"
command -v magick >/dev/null 2>&1 || die "'magick' (ImageMagick) not found — run ./install.sh --deps"
RSVG=""; command -v rsvg-convert >/dev/null 2>&1 && RSVG="rsvg-convert"
[ -z "$RSVG" ] && echo "logo-to-icons: warning: rsvg-convert absent; falling back to ImageMagick SVG (lower fidelity). Run ./install.sh --deps for librsvg." >&2

mkdir -p "$OUTDIR"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/icons.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT

# Substitute currentColor if requested (so the mark isn't rendered black).
SRC="$SVG"
if [ -n "$COLOR" ]; then
  SRC="$WORK/logo.svg"; sed "s/currentColor/$COLOR/g" "$SVG" > "$SRC"
fi
cp "$SRC" "$OUTDIR/icon.svg"

# Render a high-res transparent master PNG.
MASTER="$WORK/master.png"
if [ -n "$RSVG" ]; then
  rsvg-convert -w 1024 -h 1024 "$SRC" -o "$MASTER" || die "rsvg-convert failed"
else
  magick -background none "$SRC" -resize 1024x1024 "$MASTER" || die "magick SVG raster failed"
fi

# Square PNGs at each requested size (transparent).
IFS=',' read -ra SZ <<< "$SIZES"
for s in "${SZ[@]}"; do
  magick "$MASTER" -resize "${s}x${s}" "$OUTDIR/icon-${s}.png"
done

# favicon.ico (multi-resolution 16/32/48).
magick "$MASTER" -define icon:auto-resize=16,32,48 "$OUTDIR/favicon.ico"

# apple-icon: 180x180 flattened on the brand bg (iOS ignores transparency).
magick "$MASTER" -resize 180x180 -background "$BG" -flatten "$OUTDIR/apple-icon.png"

# Maskable 512: mark within the central ~80% safe zone on the brand bg.
magick -size 512x512 "canvas:${BG}" \
  \( "$MASTER" -resize 410x410 \) -gravity center -composite \
  "$OUTDIR/icon-maskable-512.png"

echo "ok: wrote icon set to $OUTDIR"
ls -1 "$OUTDIR"
