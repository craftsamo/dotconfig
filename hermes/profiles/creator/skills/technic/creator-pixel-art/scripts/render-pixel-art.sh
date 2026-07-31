#!/usr/bin/env bash
# Render a source image to a native pixel grid plus an integer-scale preview.
#
# Usage:
#   render-pixel-art.sh INPUT NATIVE.png PREVIEW.png \
#     --grid 48x48 --preset pico8 [--palette PICO_8] [--preview-scale 16] \
#     [--fit cover|contain] [--gravity center] [--background none] \
#     [--alpha preserve|flatten|reject]

set -euo pipefail

die() { echo "render-pixel-art: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found"; }

[ "$#" -ge 3 ] || die "expected INPUT NATIVE.png PREVIEW.png"
INPUT="$1"; NATIVE="$2"; PREVIEW="$3"; shift 3
GRID=""; PRESET="arcade"; PALETTE=""; PREVIEW_SCALE=16
FIT="cover"; GRAVITY="center"; BACKGROUND="none"; ALPHA="preserve"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --grid) GRID="$2"; shift 2 ;;
    --preset) PRESET="$2"; shift 2 ;;
    --palette) PALETTE="$2"; shift 2 ;;
    --preview-scale) PREVIEW_SCALE="$2"; shift 2 ;;
    --fit) FIT="$2"; shift 2 ;;
    --gravity) GRAVITY="$2"; shift 2 ;;
    --background) BACKGROUND="$2"; shift 2 ;;
    --alpha) ALPHA="$2"; shift 2 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -f "$INPUT" ] || die "input not found: $INPUT"
case "$GRID" in *x*) : ;; *) die "--grid must be WxH" ;; esac
W="${GRID%x*}"; H="${GRID#*x}"
case "$W:$H:$PREVIEW_SCALE" in *[!0-9:]*|0:*|*:0:*|*:0) die "grid and scale must be positive integers" ;; esac
need magick
need uv

case "$FIT" in cover|contain) : ;; *) die "--fit must be cover or contain" ;; esac
case "$ALPHA" in preserve|flatten|reject) : ;; *) die "--alpha must be preserve, flatten, or reject" ;; esac
[ "$ALPHA" != "flatten" ] || [ "$BACKGROUND" != "none" ] || die "--alpha flatten requires an opaque --background"
OPAQUE="$(magick identify -format '%[opaque]' "$INPUT")"
[ "$ALPHA" != "reject" ] || [ "$OPAQUE" = "True" ] || die "input has alpha; choose preserve or flatten explicitly"

BACKEND=""
for candidate in \
  "$HOME/.agents/skills/pixel-art" \
  "$HOME/ghq/github.com/NousResearch/hermes-agent/optional-skills/creative/pixel-art"; do
  if [ -f "$candidate/scripts/pixel_art.py" ]; then
    BACKEND="$candidate/scripts/pixel_art.py"
    break
  fi
done
[ -n "$BACKEND" ] || die "no opted-in pixel_art.py backend found"
HELP="$(uv run --no-project --with Pillow python "$BACKEND" --help 2>&1)"
for flag in --preset --palette --block; do
  case "$HELP" in *"$flag"*) : ;; *) die "backend lacks required CLI flag: $flag ($BACKEND)" ;; esac
done

mkdir -p "$(dirname "$NATIVE")" "$(dirname "$PREVIEW")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/creator-pixel-art.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Establish the native canvas before quantization. block=1 keeps that grid.
if [ "$FIT" = "cover" ]; then
  magick "$INPUT" -resize "${W}x${H}^" -gravity "$GRAVITY" -extent "${W}x${H}" "$WORK/source.png"
else
  magick "$INPUT" -resize "${W}x${H}" -background "$BACKGROUND" -gravity "$GRAVITY" -extent "${W}x${H}" "$WORK/source.png"
fi
if [ "$ALPHA" = "flatten" ]; then
  magick "$WORK/source.png" -background "$BACKGROUND" -alpha remove -alpha off "$WORK/flattened.png"
  mv "$WORK/flattened.png" "$WORK/source.png"
elif [ "$ALPHA" = "preserve" ]; then
  FITTED_OPAQUE="$(magick identify -format '%[opaque]' "$WORK/source.png")"
  if [ "$FITTED_OPAQUE" != "True" ]; then
    magick "$WORK/source.png" -alpha extract -threshold 50% "$WORK/alpha.png"
  fi
fi
BACKEND_SOURCE="$WORK/source.png"
if [ -f "$WORK/alpha.png" ]; then
  magick "$WORK/source.png" -background black -alpha remove -alpha off "$WORK/backend-source.png"
  BACKEND_SOURCE="$WORK/backend-source.png"
fi
ARGS=("$BACKEND_SOURCE" "$NATIVE" --preset "$PRESET" --block 1)
[ -n "$PALETTE" ] && ARGS+=(--palette "$PALETTE")
uv run --no-project --with Pillow python "$BACKEND" "${ARGS[@]}"
if [ -f "$WORK/alpha.png" ]; then
  magick "$NATIVE" "$WORK/alpha.png" -alpha off -compose CopyOpacity -composite "$WORK/native-alpha.png"
  mv "$WORK/native-alpha.png" "$NATIVE"
fi

PW=$((W * PREVIEW_SCALE)); PH=$((H * PREVIEW_SCALE))
magick "$NATIVE" -filter point -resize "${PW}x${PH}!" "$PREVIEW"
echo "backend: $BACKEND"
echo "native:  $NATIVE (${W}x${H})"
echo "preview: $PREVIEW (${PW}x${PH}, ${PREVIEW_SCALE}x integer scale)"
