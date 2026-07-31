#!/usr/bin/env bash
#
# text-card.sh — compose a title card (OG / Twitter) = background + crisp text.
#
# Keeps text OUT of AI generation (renders it with a real font instead).
#
# Usage:
#   text-card.sh (BG_IMAGE | --solid COLOR) --title "Title" --out OUT [options]
#   Options:
#     --solid COLOR    use a solid background color instead of an image
#     --title TEXT     headline (required)
#     --subtitle TEXT  optional second line
#     --font NAME      font name or .ttf path (default: Geist, from Brewfile cask)
#     --color COLOR    text color (default #FFFFFF)
#     --size WxH       canvas size (default 1200x630 — OG/Twitter)
#     --out FILE       output path (required)
#     -h, --help
#
# Tooling: ImageMagick. Install: ./install.sh --deps
# Higher fidelity (web typography/layout): use Satori (npx @vercel/og) instead.

set -euo pipefail
die() { echo "text-card: $*" >&2; exit 1; }

[ $# -lt 1 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

BG=""; SOLID=""; TITLE=""; SUBTITLE=""; FONT="Geist"; COLOR="#FFFFFF"; SIZE="1200x630"; OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --solid) SOLID="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --subtitle) SUBTITLE="$2"; shift 2 ;;
    --font) FONT="$2"; shift 2 ;;
    --color) COLOR="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *) BG="$1"; shift ;;
  esac
done

[ -n "$TITLE" ] || die "--title is required"
[ -n "$OUT" ] || die "--out is required"
command -v magick >/dev/null 2>&1 || die "'magick' (ImageMagick) not found — run ./install.sh --deps"

W="${SIZE%x*}"; H="${SIZE#*x}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/textcard.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT

# Resolve the font to a concrete file path (most reliable for ImageMagick, which
# doesn't always enumerate user-installed fonts by family name).
FONTFILE=""
if [ -n "$FONT" ]; then
  if [ -f "$FONT" ]; then
    FONTFILE="$FONT"
  else
    for dir in "$HOME/Library/Fonts" "/Library/Fonts" "/System/Library/Fonts"; do
      [ -d "$dir" ] || continue
      hits="$(find "$dir" -type f \( -iname "*${FONT}*.otf" -o -iname "*${FONT}*.ttf" \) 2>/dev/null)"
      [ -z "$hits" ] && continue
      # Prefer sans over Mono unless the user asked for Mono.
      case "$FONT" in
        *[Mm]ono*) : ;;
        *) nomono="$(printf '%s\n' "$hits" | grep -vi mono)"; [ -n "$nomono" ] && hits="$nomono" ;;
      esac
      case "$FONT" in
        *[Ii]talic*) : ;;
        *) noital="$(printf '%s\n' "$hits" | grep -vi italic)"; [ -n "$noital" ] && hits="$noital" ;;
      esac
      # Prefer a Regular / variable-weight file; else first match.
      FONTFILE="$(printf '%s\n' "$hits" | grep -iE 'regular|wght' | head -1)"
      [ -z "$FONTFILE" ] && FONTFILE="$(printf '%s\n' "$hits" | head -1)"
      break
    done
    # Last resort: let ImageMagick try the name (works if registered with magick).
    if [ -z "$FONTFILE" ] && magick -list font 2>/dev/null | grep -qi "$FONT"; then
      FONTFILE="$FONT"
    fi
  fi
  [ -z "$FONTFILE" ] && echo "text-card: warning: font '$FONT' not found (install font-geist via ./install.sh --deps); using ImageMagick default" >&2
fi

# Build the optional -font arg as an array (guarded for empty expansion under set -u / bash 3.2).
FONTARG=()
[ -n "$FONTFILE" ] && FONTARG=(-font "$FONTFILE")

# 1) Base canvas.
BASE="$WORK/base.png"
if [ -n "$SOLID" ]; then
  magick -size "$SIZE" "canvas:${SOLID}" "$BASE"
elif [ -n "$BG" ]; then
  [ -f "$BG" ] || die "background image not found: $BG"
  magick "$BG" -resize "${SIZE}^" -gravity center -extent "$SIZE" "$BASE"
else
  die "provide a BG_IMAGE or --solid COLOR"
fi

# 2) Title (auto-fit into a centered safe box ~80% wide).
TW=$(( W * 80 / 100 )); TTH=$(( H * 38 / 100 ))
magick -background none -fill "$COLOR" ${FONTARG[@]+"${FONTARG[@]}"} -gravity center \
  -size "${TW}x${TTH}" "caption:${TITLE}" "$WORK/title.png"

# 3) Compose (shift up if a subtitle follows).
if [ -n "$SUBTITLE" ]; then
  magick "$BASE" "$WORK/title.png" -gravity center -geometry "+0-$(( H * 8 / 100 ))" -composite "$WORK/step.png"
  STH=$(( H * 16 / 100 ))
  magick -background none -fill "$COLOR" ${FONTARG[@]+"${FONTARG[@]}"} -gravity center \
    -size "${TW}x${STH}" "caption:${SUBTITLE}" "$WORK/sub.png"
  magick "$WORK/step.png" "$WORK/sub.png" -gravity center -geometry "+0+$(( H * 22 / 100 ))" -composite "$OUT"
else
  magick "$BASE" "$WORK/title.png" -gravity center -composite "$OUT"
fi

echo "ok: $OUT  ($(magick identify -format '%wx%h' "$OUT"), $(wc -c < "$OUT" | tr -d ' ') bytes)"
