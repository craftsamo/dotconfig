#!/usr/bin/env bash
#
# img-postprocess.sh — normalize a generated image to an exact target.
#
# Accepts a URL or a local path (image_generate returns either), then optionally
# resizes+crops to exact dimensions, converts format, and caps file size.
#
# Usage:
#   img-postprocess.sh INPUT OUTPUT [options]
#     INPUT          http(s) URL or local image path
#     OUTPUT         output file path (extension implies --format if omitted)
#   Options:
#     --size WxH     resize+crop to exact pixels (e.g. 1200x630)
#     --fit MODE     cover (default, crops) | contain (pads, transparent)
#     --format F     webp | png | jpg   (default: from OUTPUT ext, else webp)
#     --max-bytes N  cap size; N accepts K/M/KB/MB (webp: cwebp -size; jpg: extent)
#     -h, --help
#
# Tooling: ImageMagick (magick) for resize/crop/convert, cwebp for WebP.
# Install via the repo Brewfile: ./install.sh --deps   (or: brew bundle)

set -euo pipefail

die() { echo "img-postprocess: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found — run ./install.sh --deps to install image tooling"; }

[ $# -lt 2 ] && { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

INPUT="$1"; OUTPUT="$2"; shift 2
SIZE=""; FIT="cover"; FORMAT=""; MAXBYTES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --size) SIZE="$2"; shift 2 ;;
    --fit) FIT="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --max-bytes) MAXBYTES="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

# Resolve format from OUTPUT extension if not given.
if [ -z "$FORMAT" ]; then
  case "${OUTPUT##*.}" in
    webp|WEBP) FORMAT=webp ;;
    png|PNG) FORMAT=png ;;
    jpg|jpeg|JPG|JPEG) FORMAT=jpg ;;
    *) FORMAT=webp ;;
  esac
fi

# Parse --max-bytes (K/M/KB/MB suffix) into raw bytes.
bytes() {
  local v="$1" n="${1%%[KkMmBb]*}"
  case "$v" in
    *[Mm]*) echo $(( ${n%.*} * 1024 * 1024 )) ;;
    *[Kk]*) echo $(( ${n%.*} * 1024 )) ;;
    *) echo "${n%.*}" ;;
  esac
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/imgpp.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# 1) Obtain the source locally.
SRC="$WORK/src"
case "$INPUT" in
  http://*|https://*) need curl; curl -fsSL "$INPUT" -o "$SRC" || die "download failed: $INPUT" ;;
  *) [ -f "$INPUT" ] || die "input not found: $INPUT"; cp "$INPUT" "$SRC" ;;
esac

# 2) Resize/crop into a normalized PNG master (ImageMagick).
need magick
MASTER="$WORK/master.png"
if [ -n "$SIZE" ]; then
  case "$FIT" in
    cover)   magick "$SRC" -resize "${SIZE}^" -gravity center -extent "$SIZE" "$MASTER" ;;
    contain) magick "$SRC" -resize "$SIZE" -background none -gravity center -extent "$SIZE" "$MASTER" ;;
    *) die "unknown --fit: $FIT (use cover|contain)" ;;
  esac
else
  magick "$SRC" "$MASTER"
fi

mkdir -p "$(dirname "$OUTPUT")"

# 3) Encode to target format, honoring --max-bytes where supported.
case "$FORMAT" in
  webp)
    need cwebp
    if [ -n "$MAXBYTES" ]; then
      # cwebp -size is a target, not a hard cap; retry tighter until <= cap.
      cap="$(bytes "$MAXBYTES")"; target="$cap"; tries=0
      while :; do
        cwebp -quiet -size "$target" "$MASTER" -o "$OUTPUT" || die "cwebp failed"
        got="$(wc -c < "$OUTPUT" | tr -d ' ')"
        { [ "$got" -le "$cap" ] || [ "$tries" -ge 3 ]; } && break
        target=$(( target * 85 / 100 )); tries=$((tries + 1))
      done
    else
      cwebp -quiet -q 90 "$MASTER" -o "$OUTPUT" || die "cwebp failed"
    fi
    ;;
  jpg)
    if [ -n "$MAXBYTES" ]; then
      magick "$MASTER" -quality 90 -define jpeg:extent="$(bytes "$MAXBYTES")"b "$OUTPUT"
    else
      magick "$MASTER" -quality 90 "$OUTPUT"
    fi
    ;;
  png)
    magick "$MASTER" "$OUTPUT"
    [ -n "$MAXBYTES" ] && [ "$(wc -c < "$OUTPUT")" -gt "$(bytes "$MAXBYTES")" ] && \
      echo "img-postprocess: warning: PNG over --max-bytes (lossless); reduce --size or use --format webp/jpg" >&2
    ;;
  *) die "unknown --format: $FORMAT" ;;
esac

FINAL_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
DIMS="$(magick identify -format '%wx%h' "$OUTPUT" 2>/dev/null || echo '?')"
echo "ok: $OUTPUT  ($FORMAT, $DIMS, ${FINAL_BYTES} bytes)"
