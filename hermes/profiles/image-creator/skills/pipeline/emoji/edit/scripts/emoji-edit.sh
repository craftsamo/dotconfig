#!/usr/bin/env bash
#
# emoji-edit.sh — the `edit-emoji` leaf's runner: deterministic edits on an
# existing image or a delivered pack, finished for a platform through
# emoji-fit.sh. Nothing is redrawn.
#
# Usage:
#   emoji-edit.sh SOURCE OUT_DIR --platform PLATFORM
#                 [--crop WxH+X+Y|square] [--shape none|circle|rounded]
#                 [--cutout auto|yes|no|key] [--fuzz PCT] [--pad FRACTION]
#                 [--stroke PX] [--stroke-color '#rrggbb'] [--slug STEM]
#     SOURCE   one image (png/webp/jpg/gif first frame) or a directory —
#              every png/webp/jpg directly inside it is edited (a delivered
#              <platform>/ dir re-platforms as a whole)
#     OUT_DIR  receives <platform>/<name>.<ext>, sheet.png, manifest.json
#   --platform  slack | discord | telegram | telegram-emoji | line | generic
#   --crop      a geometry applied before anything else (a face out of a
#               photo); `square` = centre square of the shorter edge
#   --shape     mask after the crop: circle | rounded (22 % radius) — the
#               photo-emoji look, no cut-out needed; none (default)
#   --cutout    passed to emoji-fit (default auto; `no` is forced by --shape)
#   --fuzz / --pad / --stroke / --stroke-color   passed to emoji-fit
#   --slug      file name prefix `<slug>_<name>` (default: keep the source
#               name, minus a previous platform extension)
#
# Prints one RESULT: line per file (emoji-fit's, prefixed by the name) and
# SHEET: / MANIFEST: lines. Deterministic.

set -euo pipefail
die() { echo "emoji-edit: $*" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
FIT_SH="$HERE/../../../scripts/emoji-fit.sh"

[ $# -lt 3 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
SRC="$1"; OUT="$2"; shift 2
PLATFORM=""; CROP=""; SHAPE="none"; CUTOUT="auto"; FUZZ=""; PAD=""; STROKE=""; STROKE_COLOR=""; SLUG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) PLATFORM="$2"; shift 2 ;;
    --crop) CROP="$2"; shift 2 ;;
    --shape) SHAPE="$2"; shift 2 ;;
    --cutout) CUTOUT="$2"; shift 2 ;;
    --fuzz) FUZZ="$2"; shift 2 ;;
    --pad) PAD="$2"; shift 2 ;;
    --stroke) STROKE="$2"; shift 2 ;;
    --stroke-color) STROKE_COLOR="$2"; shift 2 ;;
    --slug) SLUG="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$PLATFORM" ] || die "--platform is required"
[ -e "$SRC" ] || die "source not found: $SRC"
[ -x "$FIT_SH" ] || die "emoji-fit.sh not found at $FIT_SH"
case "$SHAPE" in none|circle|rounded) ;; *) die "--shape must be none | circle | rounded" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"
[ "$SHAPE" = none ] || CUTOUT=no

WORK="$(mktemp -d "${TMPDIR:-/tmp}/emojiedit.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
PLATFORM_DIR="$OUT/$PLATFORM"; mkdir -p "$PLATFORM_DIR"
ROWS="$WORK/rows.tsv"; : > "$ROWS"
FILES=()

FIT_ARGS=(--platform "$PLATFORM" --cutout "$CUTOUT")
[ -z "$FUZZ" ] || FIT_ARGS+=(--fuzz "$FUZZ")
[ -z "$PAD" ] || FIT_ARGS+=(--pad "$PAD")
[ -z "$STROKE" ] || FIT_ARGS+=(--stroke "$STROKE")
[ -z "$STROKE_COLOR" ] || FIT_ARGS+=(--stroke-color "$STROKE_COLOR")

edit_one() { # $1 = input file
  local IN="$1" NAME STEM PRE
  STEM="$(basename "$IN")"; STEM="${STEM%.*}"
  NAME="$STEM"; [ -z "$SLUG" ] || NAME="${SLUG}_${STEM#*_}"
  PRE="$WORK/${NAME}_pre.png"
  # First frame only (a GIF or animated WebP); keep alpha if any.
  magick "${IN}[0]" -alpha set PNG32:"$PRE"
  if [ -n "$CROP" ]; then
    if [ "$CROP" = square ]; then
      local W H E
      read -r W H < <(magick identify -format '%w %h\n' "$PRE")
      E=$(( W < H ? W : H ))
      magick "$PRE" -gravity center -crop "${E}x${E}+0+0" +repage "$PRE"
    else
      magick "$PRE" -crop "$CROP" +repage "$PRE"
    fi
  fi
  if [ "$SHAPE" != none ]; then
    local W H E R
    read -r W H < <(magick identify -format '%w %h\n' "$PRE")
    E=$(( W < H ? W : H ))
    magick "$PRE" -gravity center -crop "${E}x${E}+0+0" +repage "$PRE"
    if [ "$SHAPE" = circle ]; then
      magick "$PRE" \( +clone -alpha transparent -fill white -draw "circle $((E/2)),$((E/2)) $((E/2)),0" \) \
        -alpha off -compose CopyOpacity -composite "$PRE"
    else
      R=$(( E * 22 / 100 ))
      magick "$PRE" \( +clone -alpha transparent -fill white -draw "roundrectangle 0,0 $((E-1)),$((E-1)) $R,$R" \) \
        -alpha off -compose CopyOpacity -composite "$PRE"
    fi
  fi
  local RES
  RES="$("$FIT_SH" "$PRE" "$PLATFORM_DIR/$NAME" "${FIT_ARGS[@]}")"
  echo "$NAME $RES"
  local FILE BYTES WITHIN
  FILE="$(printf '%s\n' "$RES" | sed -n 's/^RESULT: file=\([^ ]*\).*/\1/p')"
  BYTES="$(printf '%s\n' "$RES" | sed -n 's/.* bytes=\([0-9]*\).*/\1/p')"
  WITHIN="$(printf '%s\n' "$RES" | sed -n 's/.* within_cap=\([a-z]*\).*/\1/p')"
  printf '%s\t%s\t%s\t%s\t%s\n' "$NAME" "$IN" "$(basename "$FILE")" "$BYTES" "$WITHIN" >> "$ROWS"
  FILES+=("$FILE")
}

if [ -d "$SRC" ]; then
  for f in "$SRC"/*.png "$SRC"/*.webp "$SRC"/*.jpg "$SRC"/*.jpeg "$SRC"/*.gif; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in sheet*|sheet32*) continue ;; esac
    edit_one "$f"
  done
else
  edit_one "$SRC"
fi
[ "${#FILES[@]}" -gt 0 ] || die "no images edited"

magick "${FILES[@]}" -resize 128x128 -background '#888888' -gravity center -extent 136x136 +append "$OUT/sheet.png"
python3 - "$ROWS" "$OUT/manifest.json" "$PLATFORM" <<'EOF'
import json, sys
rows, out, platform = sys.argv[1], sys.argv[2], sys.argv[3]
items = []
for line in open(rows, encoding="utf-8"):
    name, source, file, size, within = line.rstrip("\n").split("\t")
    code = name.split("_", 1)[1] if "_" in name else name
    items.append({"item": code, "code": f":{name}:", "file": file, "source": source,
                  "bytes": int(size), "passed": within == "yes"})
json.dump({"platform": platform, "items": items}, open(out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
EOF
echo "SHEET: $OUT/sheet.png"
echo "MANIFEST: $OUT/manifest.json items=${#FILES[@]}"
