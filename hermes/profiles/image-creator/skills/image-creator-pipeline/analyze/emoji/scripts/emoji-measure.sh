#!/usr/bin/env bash
#
# emoji-measure.sh — the `analyze-emoji` leaf's instrument: measure one
# emoji file or a whole pack against a platform's spec and lay out the
# sheets vision needs. Writes nothing but the sheets.
#
# Usage:
#   emoji-measure.sh SOURCE --platform PLATFORM [--sheet-dir DIR] [--against ANCHOR]
#     SOURCE      one image, or a directory (every png/webp/jpg/gif inside,
#                 sheets excluded)
#   --platform    the spec to judge against (read from emoji-fit.sh --spec)
#   --sheet-dir   where to write pack.png (128 px on grey), pack32.png (the
#                 32 px read, point-magnified 4x), light.png / dark.png
#                 (64 px on a light and a dark chat background) and, with
#                 --against, anchor.png (the anchor at 128 beside item 1)
#   --against     the character anchor the pack must match
#
# Prints:
#   SPEC:     the platform row
#   MEASURE:  per file — file, width, height, format, bytes, cap,
#             size_ok, format_ok, bytes_ok, alpha (yes|no), corner_alpha,
#             coverage, key_px (pixels still pure chroma green / magenta)
#   SUMMARY:  files, pass (every *_ok yes and alpha yes), fail
#   SHEET:    one line per sheet written

set -euo pipefail
die() { echo "emoji-measure: $*" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
FIT_SH="$HERE/../../../scripts/emoji-fit.sh"

[ $# -lt 3 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SRC="$1"; shift
PLATFORM=""; SHEET_DIR=""; AGAINST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) PLATFORM="$2"; shift 2 ;;
    --sheet-dir) SHEET_DIR="$2"; shift 2 ;;
    --against) AGAINST="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$PLATFORM" ] || die "--platform is required"
[ -e "$SRC" ] || die "source not found: $SRC"
[ -x "$FIT_SH" ] || die "emoji-fit.sh not found at $FIT_SH"
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

SPEC="$("$FIT_SH" --spec "$PLATFORM")"; echo "$SPEC"
SIZE="$(printf '%s' "$SPEC" | sed 's/.* size=\([0-9]*\).*/\1/')"
FMT="$(printf '%s' "$SPEC" | sed 's/.* format=\([a-z]*\).*/\1/')"
CAP="$(printf '%s' "$SPEC" | sed 's/.* cap=\([0-9]*\).*/\1/')"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/emojimeasure.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
FILES=(); PASS=0; FAIL=0

measure_one() { # $1 = file
  local F="$1" W H FORMAT BYTES CH ALPHA CORNER COVERAGE KEY SOK FOK BOK OK
  read -r W H FORMAT BYTES < <(magick identify -format '%w %h %m %B\n' "${F}[0]")
  FORMAT="$(printf '%s' "$FORMAT" | tr '[:upper:]' '[:lower:]')"
  CH="$(magick "${F}[0]" -format '%[channels]' info:)"
  case "$CH" in *a*) ALPHA=yes ;; *) ALPHA=no ;; esac
  CORNER="$(magick "${F}[0]" -alpha set -alpha extract -format '%[fx:p{0,0}]' info:)"
  COVERAGE="$(magick "${F}[0]" -alpha set -alpha extract -format '%[fx:mean]' info:)"
  KEY="$(magick "${F}[0]" -alpha off -fuzz 20% -fill white +opaque '#00ff00' -fill black -opaque '#00ff00' -negate -format '%[fx:round(mean*w*h)]' info:)"
  [ "$W" = "$SIZE" ] && [ "$H" = "$SIZE" ] && SOK=yes || SOK=no
  [ "$FORMAT" = "$FMT" ] && FOK=yes || FOK=no
  if [ "$CAP" -gt 0 ] && [ "$BYTES" -ge "$CAP" ]; then BOK=no; else BOK=yes; fi
  if [ "$SOK$FOK$BOK$ALPHA" = "yesyesyesyes" ]; then OK=1; PASS=$((PASS+1)); else OK=0; FAIL=$((FAIL+1)); fi
  echo "MEASURE: file=$F width=$W height=$H format=$FORMAT bytes=$BYTES cap=$CAP size_ok=$SOK format_ok=$FOK bytes_ok=$BOK alpha=$ALPHA corner_alpha=$CORNER coverage=$COVERAGE key_px=$KEY"
  FILES+=("$F")
}

if [ -d "$SRC" ]; then
  for f in "$SRC"/*.png "$SRC"/*.webp "$SRC"/*.jpg "$SRC"/*.jpeg "$SRC"/*.gif; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in sheet*|pack*|light.png|dark.png|anchor.png) continue ;; esac
    measure_one "$f"
  done
else
  measure_one "$SRC"
fi
[ "${#FILES[@]}" -gt 0 ] || die "no images found"
echo "SUMMARY: files=${#FILES[@]} pass=$PASS fail=$FAIL"

if [ -n "$SHEET_DIR" ]; then
  mkdir -p "$SHEET_DIR"
  row() { # $1 size, $2 bg, $3 out, $4 pad
    local TILES=() f
    for f in "${FILES[@]}"; do
      local t="$WORK/$(basename "$f").$1.$2.png"
      magick "${f}[0]" -alpha set -resize "${1}x${1}" -background "$2" -gravity center -extent "$(( $1 + $4 ))x$(( $1 + $4 ))" -flatten "$t"
      TILES+=("$t")
    done
    magick "${TILES[@]}" -background "$2" +append "$3"
  }
  row 128 '#888888' "$SHEET_DIR/pack.png" 8
  row 32 '#888888' "$WORK/pack32.png" 2
  magick "$WORK/pack32.png" -filter point -resize 400% "$SHEET_DIR/pack32.png"
  row 64 '#ffffff' "$SHEET_DIR/light.png" 6
  row 64 '#1e1f22' "$SHEET_DIR/dark.png" 6
  echo "SHEET: $SHEET_DIR/pack.png (128 on grey) | pack32.png (32 px read, 4x point) | light.png / dark.png (64 on light / dark chat)"
  if [ -n "$AGAINST" ]; then
    [ -f "$AGAINST" ] || die "against not found: $AGAINST"
    magick "${AGAINST}[0]" -alpha set -resize 128x128 -background '#888888' -gravity center -extent 136x136 -flatten "$WORK/a.png"
    magick "${FILES[0]}[0]" -alpha set -resize 128x128 -background '#888888' -gravity center -extent 136x136 -flatten "$WORK/i.png"
    magick "$WORK/a.png" "$WORK/i.png" -background '#888888' +append "$SHEET_DIR/anchor.png"
    echo "SHEET: $SHEET_DIR/anchor.png (anchor at 128 | item 1 at 128)"
  fi
fi
