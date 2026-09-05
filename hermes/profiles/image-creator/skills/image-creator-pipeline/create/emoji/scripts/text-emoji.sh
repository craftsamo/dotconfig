#!/usr/bin/env bash
#
# text-emoji.sh — the `create-emoji` leaf's renderer: text emoji (承認 /
# LGTM / 助かる) drawn deterministically with a bold font, one file per
# item, finished for a platform through emoji-fit.sh.
#
# Usage:
#   text-emoji.sh ITEMS_FILE OUT_DIR --platform PLATFORM
#                 [--color '#rrggbb'] [--tile '#rrggbb'|none] [--font PATH]
#                 [--fit stretch|contain] [--outline PX] [--outline-color '#rrggbb']
#                 [--radius FRACTION]
#     ITEMS_FILE  one item per line: `name<TAB>text`; `|` in text breaks
#                 a line (max 3 lines); blank lines and `#` lines skipped.
#                 Text comes from a FILE on purpose — Japanese punctuation
#                 on the command line trips the terminal guard.
#     OUT_DIR     receives <platform>/<name>.<ext>, sheet.png, manifest.json
#   --platform  slack | discord | telegram | telegram-emoji | line | generic
#               (sizes and caps from emoji-fit.sh)
#   --color     text colour (default #e4572e)
#   --tile      rounded-square tile colour behind the text, or none (default)
#   --font      font file (default Hiragino Sans W8, the bold Japanese
#               gothic on macOS)
#   --fit       stretch (default): each line is stretched to fill the full
#               width and its share of the height — the classic 文字絵文字
#               look; contain: glyph proportions kept, lines centred
#   --outline   stroke width around the glyphs in px at 512 (default 0)
#   --outline-color  stroke colour (default #ffffff)
#   --radius    tile corner radius as a fraction of the edge (default 0.22)
#
# Prints one RESULT: line per item (from emoji-fit.sh, prefixed by the
# item name) and a final SHEET: / MANIFEST: line. Deterministic.
#
# Tooling: ImageMagick (magick), python3 for the manifest.

set -euo pipefail
die() { echo "text-emoji: $*" >&2; exit 1; }
HEX='\#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'
HERE="$(cd "$(dirname "$0")" && pwd)"
FIT_SH="$HERE/../../../scripts/emoji-fit.sh"

[ $# -lt 3 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
ITEMS="$1"; OUT="$2"; shift 2
PLATFORM=""; COLOR="#e4572e"; TILE="none"; FONT="/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
FIT="stretch"; OUTLINE=0; OUTLINE_COLOR="#ffffff"; RADIUS="0.22"
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) PLATFORM="$2"; shift 2 ;;
    --color) COLOR="$2"; shift 2 ;;
    --tile) TILE="$2"; shift 2 ;;
    --font) FONT="$2"; shift 2 ;;
    --fit) FIT="$2"; shift 2 ;;
    --outline) OUTLINE="$2"; shift 2 ;;
    --outline-color) OUTLINE_COLOR="$2"; shift 2 ;;
    --radius) RADIUS="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$PLATFORM" ] || die "--platform is required"
[ -f "$ITEMS" ] || die "items file not found: $ITEMS"
[ -f "$FONT" ] || die "font not found: $FONT"
[ -x "$FIT_SH" ] || die "emoji-fit.sh not found at $FIT_SH"
case "$COLOR" in $HEX) ;; *) die "--color must be #rrggbb" ;; esac
case "$TILE" in none|$HEX) ;; *) die "--tile must be none | #rrggbb" ;; esac
case "$OUTLINE_COLOR" in $HEX) ;; *) die "--outline-color must be #rrggbb" ;; esac
case "$FIT" in stretch|contain) ;; *) die "--fit must be stretch | contain" ;; esac
command -v magick >/dev/null 2>&1 || die "magick (ImageMagick) not found — report as a gap"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/textemoji.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
S=512
if [ "$TILE" = none ]; then AREA=$(( S * 96 / 100 )); else AREA=$(( S * 84 / 100 )); fi
# Bash 3.2 (macOS) treats an empty array as unset under `set -u`, so the
# stroke arguments are always a two-element list; `-stroke none` is a no-op.
if [ "$OUTLINE" -gt 0 ] 2>/dev/null; then STROKE_ARGS=(-stroke "$OUTLINE_COLOR" -strokewidth "$OUTLINE")
else STROKE_ARGS=(-stroke none); fi

PLATFORM_DIR="$OUT/$PLATFORM"; mkdir -p "$PLATFORM_DIR"
MANIFEST_ROWS="$WORK/rows.tsv"; : > "$MANIFEST_ROWS"
FILES=()

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  NAME="${line%%	*}"; TEXT="${line#*	}"
  [ "$NAME" != "$line" ] || die "line has no TAB between name and text: $line"
  case "$NAME" in *[!a-z0-9_-]*|'') die "item name must be a slug (a-z 0-9 _ -): $NAME" ;; esac
  IFS='|' read -r -a LINES <<< "$TEXT"
  N=${#LINES[@]}; [ "$N" -ge 1 ] && [ "$N" -le 3 ] || die "$NAME: 1-3 lines, got $N"
  LINE_H=$(( AREA / N ))
  # Character counts (bytes would miscount Japanese under a C locale).
  MAXLEN=0; LENS=()
  for l in "${LINES[@]}"; do
    LEN="$(printf '%s' "$l" | python3 -c 'import sys; print(len(sys.stdin.buffer.read().decode("utf-8")))')"
    [ "$LEN" -ge 1 ] || die "$NAME: empty line"
    LENS+=("$LEN"); [ "$LEN" -gt "$MAXLEN" ] && MAXLEN="$LEN"
  done

  # Render each line on its own, then stack.
  PARTS=()
  for i in "${!LINES[@]}"; do
    P="$WORK/${NAME}_$i.png"
    if [ "$FIT" = stretch ]; then
      # A shorter line keeps its share of the width (よ under 見て / ます is
      # not stretched to the full edge), so the block stays a text block.
      LINE_W=$(( AREA * LENS[$i] / MAXLEN ))
      magick -background none -fill "$COLOR" "${STROKE_ARGS[@]}" -font "$FONT" \
        -size "${AREA}x${LINE_H}" -gravity center "caption:${LINES[$i]}" \
        -trim +repage -resize "${LINE_W}x${LINE_H}!" \
        -background none -gravity center -extent "${AREA}x${LINE_H}" "$P"
    else
      magick -background none -fill "$COLOR" "${STROKE_ARGS[@]}" -font "$FONT" \
        -size "${AREA}x${LINE_H}" -gravity center "caption:${LINES[$i]}" "$P"
    fi
    PARTS+=("$P")
  done
  TEXT_PNG="$WORK/${NAME}_text.png"
  magick "${PARTS[@]}" -background none -append -gravity center -extent "${S}x${S}" "$TEXT_PNG"

  RAW="$WORK/${NAME}_raw.png"
  if [ "$TILE" = none ]; then
    cp "$TEXT_PNG" "$RAW"
  else
    R="$(python3 -c 'import sys; print(int(int(sys.argv[1])*float(sys.argv[2])))' "$S" "$RADIUS")"
    magick -size "${S}x${S}" xc:none -fill "$TILE" -draw "roundrectangle 0,0 $((S-1)),$((S-1)) $R,$R" \
      "$TEXT_PNG" -gravity center -composite "$RAW"
  fi

  RES="$("$FIT_SH" "$RAW" "$PLATFORM_DIR/$NAME" --platform "$PLATFORM" --cutout no --pad 0)"
  echo "$NAME $RES"
  FILE="$(printf '%s\n' "$RES" | sed -n 's/^RESULT: file=\([^ ]*\).*/\1/p')"
  BYTES="$(printf '%s\n' "$RES" | sed -n 's/.* bytes=\([0-9]*\).*/\1/p')"
  WITHIN="$(printf '%s\n' "$RES" | sed -n 's/.* within_cap=\([a-z]*\).*/\1/p')"
  printf '%s\t%s\t%s\t%s\t%s\n' "$NAME" "$TEXT" "$(basename "$FILE")" "$BYTES" "$WITHIN" >> "$MANIFEST_ROWS"
  FILES+=("$FILE")
done < "$ITEMS"

[ "${#FILES[@]}" -gt 0 ] || die "no items rendered"

# Contact sheet on mid grey (transparent files need a background to be judged).
magick "${FILES[@]}" -resize 128x128 -background '#888888' -gravity center -extent 136x136 +append "$OUT/sheet.png"
python3 - "$MANIFEST_ROWS" "$OUT/manifest.json" "$PLATFORM" <<'EOF'
import json, sys
rows, out, platform = sys.argv[1], sys.argv[2], sys.argv[3]
items = []
for line in open(rows, encoding="utf-8"):
    name, text, file, size, within = line.rstrip("\n").split("\t")
    items.append({"item": name, "text": text.replace("|", "\n"), "code": f":{name}:",
                  "file": file, "bytes": int(size), "passed": within == "yes"})
json.dump({"platform": platform, "items": items}, open(out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
EOF
echo "SHEET: $OUT/sheet.png"
echo "MANIFEST: $OUT/manifest.json items=${#FILES[@]}"
