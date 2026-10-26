#!/usr/bin/env python3
"""kit-images.py — shared ImageMagick-backed image kit for image-creator leaves.

Subcommands:

  fit INPUT OUTPUT --canvas WxH [--cutout auto|yes|no|key] [--fuzz 10]
      [--pad 0.04] [--pixel] [--palette PATH]
    INPUT must be a local PNG/raster file (localize model URLs before
    calling). Fits INPUT onto an exact WxH canvas, aspect-preserving
    (contain after trim) — never crops or stretches.
    --cutout auto (default) keeps an input that already has transparency
      ANYWHERE (corners or interior — an already cut-out asset), otherwise
      floods the background from the four corners (yes) or removes the
      corner colour globally (key, for background trapped in pockets).
      Either way the removed colour is remembered for the key_px diagnostic.
    --fuzz    flood-fill / key tolerance, percent (default 10)
    --pad     fraction of the canvas edge kept clear (default 0.04)
    --pixel   nearest-neighbour scaling + binary (0/255) alpha. --canvas is
              the logical native grid for the result — this is quantization,
              not proof the source was authored pixel by pixel.
    --palette PATH  remap onto a fixed palette PNG (see `palette`), dithering
              OFF; alpha is detached before the remap and reattached
              afterwards via CopyOpacity, unchanged, so a fixed opaque-only
              palette can never move a transparent pixel's alpha. Output is
              always stripped of metadata for repeatable bytes.
    Rejects: empty alpha after cutout, invalid --canvas/--pad/--fuzz, INPUT
    == OUTPUT, an OUTPUT extension other than .png, and canvas dimensions
    over 4096px / 16,000,000px.
    Prints one `RESULT:` line (key=value): width height bytes coverage
    corner_alpha key_px.

  palette INPUT OUTPUT [--colors 16]
    Builds a reusable fixed-palette PNG (an N x 1 strip of swatches) from
    INPUT's OPAQUE foreground colours only — background/transparent pixels
    never enter it. --colors must be 2..256.

  atlas SOURCE OUTPUT_DIR [--columns 4] [--gap 2]
    Recursively collects every *.png under SOURCE (sorted by relative path,
    stable — duplicate basenames in different directories are both kept,
    keyed by their relative path) and packs them, at native size (never
    resized), into one deterministic grid: cell size is the max width/max
    height across all collected images, --gap px between cells. Writes
    atlas.png (one -compose Copy composite per source, all in a single
    magick invocation — no per-file read/modify/write of the whole growing
    canvas — so pasted pixels are byte-identical to the source) + atlas.json
    ({image,width,height,frames:[{file,x,y,width,height}]}, dimensions are
    each frame's full untrimmed original size) + sheet.png (a bounded grey
    review thumbnail). No `magick montage` (needs a default font); OUTPUT_DIR
    must not be inside SOURCE or alias it, and must be empty or not exist —
    reusing an output directory across revisions is refused (use a fresh
    directory per run). Capped at 64 PNG source files per run (split a
    larger asset set into category batches) and fails before allocating the
    canvas if it would exceed the 4096px / 16,000,000px cap.

  measure SOURCE --out OUTPUT_DIR [--against ANCHOR] [--palette PALETTE]
    Recursively measures every *.png under SOURCE (immutable; SOURCE is
    never written) and writes OUTPUT_DIR/measurements.json: per file width,
    height, bytes, alpha (bool), alpha_min/alpha_max, coverage, corners
    (4 alpha values), bbox, top-8 opaque palette colours (nearest colour +
    distance in PALETTE, a palette PNG from `palette`, when given), plus a
    summary count. This is numbers only — pass/fail is a human vision call,
    not something this tool decides. Also writes review sheets, EXACTLY:
      sheet.png       every file at 256px on grey, appended in a row
      native.png      the first file at true pixel size, or a bounded/
                       resized copy when it exceeds the pixel cap (flagged
                       "native".bounded=true in the JSON, not burned into
                       the image, since montage-style text needs a font)
      light.png       every file at 128px on a light page
      dark.png        every file at 128px on a dark page
      silhouette.png  every file's alpha as black-on-white, 160px
      against.png     ANCHOR at 256px beside the first file at 256px
                       (only written when --against is given)
    Every grid sheet (sheet.png, silhouette.png, light.png, dark.png) is
    laid out on a bounded <= 8-column grid, never one unbounded row — with
    the 64-file cap below, the tallest grid is 8 rows, so every sheet stays
    comfortably under the 4096px cap regardless of how many files land in
    one run. OUTPUT_DIR must not be inside SOURCE, and must be empty or not
    exist — reusing an output directory across revisions is refused (e.g. a
    later run without --against would otherwise leave a stale against.png
    behind); use a fresh directory per run. Capped at 64 PNG source files
    per run — split a larger asset set into category batches and measure
    each separately.

Tooling: ImageMagick (`magick`). Paths are resolved to absolute, existing
files before use and rejected if they contain ':' so a crafted name can
never be read as an ImageMagick pseudo-path (xc:, caption:, http:, ...).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_DIM = 4096
MAX_PIXELS = 16_000_000
# atlas/measure: 8 review-grid columns x a 272px cell (256 + 16 padding) is
# 2176px wide; at the file cap below the tallest grid is 8 rows of the same
# cell — 2176px — comfortably under MAX_DIM regardless of how many of the
# <=64 files land in one run. A run over the cap must be split into smaller
# category batches rather than silently truncated or left unbounded.
MAX_SHEET_FILES = 64
SHEET_COLUMNS = 8
HIST_RE = re.compile(r"\s*(\d+):\s*\(([^)]*)\)\s*(#[0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?")


class Fail(Exception):
    """A user-facing failure; caught in main() and reported as an error."""


def magick(*args) -> str:
    try:
        result = subprocess.run(
            ["magick", *[str(a) for a in args]],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise Fail("magick (ImageMagick) not found — report as a gap") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip() or "magick command failed"
        raise Fail(message) from exc
    return result.stdout


def frame0(path) -> str:
    return f"{path}[0]"


def identify_dims(path) -> tuple[int, int]:
    out = magick("identify", "-format", "%w %h\n", frame0(path))
    w, h = out.split()[:2]
    return int(w), int(h)


def alpha_bbox(path) -> tuple[int, int, int, int]:
    """Return (x, y, width, height): the bounding box of pixels with alpha
    STRICTLY GREATER THAN 0, from the alpha plane only — never colour, and
    never a >=50% cutoff (a uniformly ~30% translucent "glass" object is
    real, occupied content — a >=50% threshold would zero its whole bbox
    out and, in `fit --cutout no`, get it wrongly rejected as empty).

    Plain `-trim` samples the CORNER pixel's colour as "background" and
    crops to whatever differs from it. That silently picks the wrong
    shape whenever the corner itself is part of the occupied region: an
    opaque frame that touches every corner (a hollow rectangular border)
    trims down to just its transparent interior hole, and opaque corners
    around a transparent interior hole (an already cut-out asset) can
    likewise mis-crop. Extracting the alpha channel first and always
    adding a forced BLACK border before trimming fixes the reference: the
    trim's background is now always the added border, never the source's
    own corner, so the bounding box comes out as the true extent of every
    nonzero-alpha pixel (antialiased margins and translucent fills
    included) regardless of what touches the corners.
    All-transparent (alpha == 0 everywhere) input returns the zero box
    (0, 0, 0, 0).
    """
    # Checked up front rather than left to `-trim`: a totally uniform
    # (all-background) image doesn't reliably error there — it can trim
    # to a spurious 1x1 box instead of signalling "nothing found".
    maxima = float(magick(frame0(path), "-alpha", "set", "-alpha", "extract",
                           "-format", "%[fx:maxima]", "info:").strip())
    if maxima <= 0:
        return (0, 0, 0, 0)
    try:
        out = magick(
            frame0(path), "-alpha", "set", "-alpha", "extract", "-threshold", "0%",
            "-bordercolor", "black", "-border", "1",
            "-trim", "-format", "%wx%h%X%Y", "info:",
        ).strip()
    except Fail:
        return (0, 0, 0, 0)
    m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", out)
    if not m:
        return (0, 0, 0, 0)
    w, h = int(m.group(1)), int(m.group(2))
    x, y = int(m.group(3)) - 1, int(m.group(4)) - 1
    return (x, y, w, h)


def safe_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.exists():
        raise Fail(f"not found: {raw}")
    resolved = p.resolve()
    if not resolved.is_file():
        raise Fail(f"not a file: {raw}")
    if ":" in str(resolved):
        raise Fail(f"path must not contain ':': {raw}")
    return resolved


def safe_dir(raw: str) -> Path:
    resolved = Path(raw).expanduser().resolve()
    if not resolved.is_dir():
        raise Fail(f"source directory not found: {raw}")
    if ":" in str(resolved):
        raise Fail(f"path must not contain ':': {raw}")
    return resolved


def resolve_output(raw: str) -> Path:
    p = Path(raw).expanduser()
    parent = p.parent if str(p.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)
    resolved = parent.resolve() / p.name
    if ":" in str(resolved):
        raise Fail(f"output path must not contain ':': {raw}")
    return resolved


def reject_nonempty_dir(path: Path) -> None:
    # A reused output directory is how a later run without --against (or
    # with fewer files) leaves a stale sheet behind from a prior revision.
    # Simplest fix: refuse anything but an empty/nonexistent directory —
    # callers use a fresh directory per revision.
    if path.exists():
        if not path.is_dir():
            raise Fail(f"output path exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise Fail(
                f"output directory is not empty — use a fresh directory per "
                f"revision: {path}"
            )


def resolve_output_dir(raw: str, source: Path) -> Path:
    resolved = Path(os.path.realpath(Path(raw).expanduser()))
    if ":" in str(resolved):
        raise Fail(f"output path must not contain ':': {raw}")
    try:
        resolved.relative_to(source)
        raise Fail("output directory must not be SOURCE or inside it")
    except ValueError:
        pass
    try:
        source.relative_to(resolved)
        raise Fail("SOURCE must not be inside the output directory")
    except ValueError:
        pass
    reject_nonempty_dir(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def parse_canvas(raw: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)x(\d+)", raw)
    if not m:
        raise Fail(f"--canvas must be WxH: {raw}")
    w, h = int(m.group(1)), int(m.group(2))
    if w < 1 or h < 1:
        raise Fail("--canvas dimensions must be positive")
    if w > MAX_DIM or h > MAX_DIM:
        raise Fail(f"--canvas dimensions must be <= {MAX_DIM}px")
    if w * h > MAX_PIXELS:
        raise Fail(f"--canvas pixel count must be <= {MAX_PIXELS}")
    return w, h


def parse_fuzz(raw: str) -> float:
    try:
        v = float(raw)
    except ValueError as exc:
        raise Fail(f"--fuzz must be a number: {raw}") from exc
    if not (0 <= v <= 100):
        raise Fail("--fuzz must be between 0 and 100")
    return v


def parse_pad(raw: str) -> float:
    try:
        v = float(raw)
    except ValueError as exc:
        raise Fail(f"--pad must be a number: {raw}") from exc
    if not (0 <= v < 0.5):
        raise Fail("--pad must be in [0, 0.5)")
    return v


def parse_histogram(text: str):
    out = []
    for line in text.splitlines():
        m = HIST_RE.match(line)
        if not m:
            continue
        count, _, hexcolor, alpha_hex = m.groups()
        alpha = int(alpha_hex, 16) if alpha_hex is not None else None
        out.append((int(count), hexcolor.lower(), alpha))
    return out


def rgb(hexcolor: str) -> tuple[int, int, int]:
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def nearest_color(hexcolor: str, palette):
    r, g, b = rgb(hexcolor)
    best = min(palette, key=lambda c: sum((x - y) ** 2 for x, y in zip(rgb(c), (r, g, b))))
    dist = int(sum((x - y) ** 2 for x, y in zip(rgb(best), (r, g, b))) ** 0.5)
    return best, dist


def read_palette_colors(path: Path):
    out = magick(frame0(path), "-unique-colors", "txt:-")
    colors = [m.group(1).lower() for line in out.splitlines() for m in [re.search(r"(#[0-9A-Fa-f]{6})", line)] if m]
    if not colors:
        raise Fail(f"palette file has no colours: {path}")
    return colors


def collect_pngs(source: Path):
    files = []
    for root, dirs, names in os.walk(source):
        dirs.sort()
        for name in sorted(names):
            if name.lower().endswith(".png"):
                full = Path(root) / name
                files.append((str(full.relative_to(source)), full))
    files.sort(key=lambda t: t[0])
    return files


# ---------------------------------------------------------------- fit -----

def cmd_fit(args) -> None:
    input_path = safe_path(args.input)
    if Path(args.output).suffix.lower() != ".png":
        raise Fail("output must be a .png file")
    output_path = resolve_output(args.output)
    if input_path == output_path:
        raise Fail("input and output must not be the same path")

    canvas_w, canvas_h = parse_canvas(args.canvas)
    fuzz = parse_fuzz(args.fuzz)
    pad = parse_pad(args.pad)
    if args.cutout not in ("auto", "yes", "no", "key"):
        raise Fail("--cutout must be auto | yes | no | key")
    palette_path = safe_path(args.palette) if args.palette else None

    with tempfile.TemporaryDirectory(prefix="kitimages-fit-") as workdir_s:
        workdir = Path(workdir_s)
        src = workdir / ("src" + (Path(args.input).suffix or ".png"))
        shutil.copy2(input_path, src)
        try:
            identify_dims(src)
        except Fail as exc:
            raise Fail(f"invalid input image: {args.input}") from exc

        cutout_mode = args.cutout
        if cutout_mode == "auto":
            channels = magick("identify", "-format", "%[channels]", frame0(src)).strip()
            if "a" in channels:
                minima = float(magick(
                    frame0(src), "-alpha", "set", "-alpha", "extract",
                    "-format", "%[fx:minima]", "info:",
                ).strip())
                # Any transparency ANYWHERE (corners or interior) means this
                # is already a cut-out asset — do not flood-fill it again.
                cutout_mode = "no" if minima < 0.98 else "yes"
            else:
                cutout_mode = "yes"

        cut = workdir / "cut.png"
        bgcolor = None
        try:
            if cutout_mode == "yes":
                w, h = identify_dims(src)
                bgcolor = "#" + magick(frame0(src), "-alpha", "off", "-depth", "8",
                                        "-format", "%[hex:p{0,0}]", "info:").strip()
                magick(
                    frame0(src), "-alpha", "set", "-bordercolor", bgcolor, "-border", "1",
                    "-fuzz", f"{fuzz}%", "-fill", "none",
                    "-draw", "color 0,0 floodfill",
                    "-draw", f"color {w + 1},0 floodfill",
                    "-draw", f"color 0,{h + 1} floodfill",
                    "-draw", f"color {w + 1},{h + 1} floodfill",
                    "-shave", "1x1", "-trim", "+repage", str(cut),
                )
            elif cutout_mode == "key":
                bgcolor = "#" + magick(frame0(src), "-alpha", "off", "-depth", "8",
                                        "-format", "%[hex:p{0,0}]", "info:").strip()
                magick(
                    frame0(src), "-alpha", "set", "-fuzz", f"{fuzz}%", "-transparent", bgcolor,
                    "(", "+clone", "-alpha", "extract", "-morphology", "Erode", "Diamond:1", ")",
                    "-alpha", "off", "-compose", "CopyOpacity", "-composite",
                    "-trim", "+repage", str(cut),
                )
            else:
                # Crop to the true alpha-occupied bounds, not a colour
                # `-trim`: a fully opaque input has none to strip (the
                # bbox is the whole canvas — cutout=no must preserve it
                # untouched), and a shape that touches every corner (an
                # opaque frame around a transparent hole, or opaque
                # corners around a transparent interior hole) must keep
                # its full extent rather than collapsing to one region.
                x, y, bw, bh = alpha_bbox(src)
                magick(frame0(src), "-alpha", "set", "-crop", f"{bw}x{bh}+{x}+{y}", "+repage", str(cut))
            identify_dims(cut)
            coverage_cut = float(magick(frame0(cut), "-alpha", "extract",
                                         "-format", "%[fx:mean]", "info:").strip())
        except Fail as exc:
            raise Fail("empty alpha: input has no opaque content after cutout") from exc
        if coverage_cut <= 0.0005:
            raise Fail("empty alpha: input has no opaque content after cutout")

        inner_w = max(1, int(round(canvas_w * (1 - 2 * pad))))
        inner_h = max(1, int(round(canvas_h * (1 - 2 * pad))))
        filt = "point" if args.pixel else "Lanczos"
        fit_img = workdir / "fit.png"
        magick(
            frame0(cut), "-filter", filt, "-resize", f"{inner_w}x{inner_h}",
            "-background", "none", "-gravity", "center",
            "-extent", f"{canvas_w}x{canvas_h}", str(fit_img),
        )

        if args.pixel:
            binarized = workdir / "binarized.png"
            magick(frame0(fit_img), "-channel", "A", "-threshold", "50%", "+channel", str(binarized))
            fit_img = binarized

        final_src = fit_img
        if palette_path is not None:
            # Remap RGB only (alpha detached first, so the nearest-colour
            # search and the fixed opaque-only palette never see it), then
            # reattach the ORIGINAL alpha unchanged via CopyOpacity — a
            # palette built from opaque swatches must never be able to move
            # a transparent pixel's alpha.
            remapped_rgb = workdir / "remapped-rgb.png"
            magick(frame0(fit_img), "-alpha", "off", "-dither", "None",
                   "-remap", str(palette_path), str(remapped_rgb))
            remapped = workdir / "remapped.png"
            # P1 FIX: a bare "-alpha extract" here is an OPERATOR, not a
            # setting — it re-applies to every image already in the
            # command's stack, so an unscoped `remapped_rgb ... frame0(fit_img)
            # -alpha extract` also alpha-extracts remapped_rgb itself and
            # whitens its RGB to a flat silhouette. The alpha extraction
            # must be scoped to ONLY fit_img via a parenthesised subgroup.
            magick(
                str(remapped_rgb),
                "(", frame0(fit_img), "-alpha", "extract", ")",
                "-alpha", "off",
                "-compose", "CopyOpacity", "-composite", str(remapped),
            )
            final_src = remapped

        magick(frame0(final_src), "-strip", "-define", "png:compression-level=9",
               "-define", "png:exclude-chunk=date,time", str(output_path))

        rw, rh = identify_dims(output_path)
        if (rw, rh) != (canvas_w, canvas_h):
            raise Fail(f"rendered {rw}x{rh}, expected {canvas_w}x{canvas_h}")
        bytes_ = output_path.stat().st_size
        # Measured on the actual OUTPUT file (post pixel-binarize, post
        # palette remap), never on the pre-remap intermediate — the RESULT
        # line must describe what was actually written.
        coverage = float(magick(frame0(output_path), "-alpha", "extract",
                                 "-format", "%[fx:mean]", "info:").strip())
        corner_alpha = float(magick(frame0(output_path), "-alpha", "extract",
                                     "-format", "%[fx:p{0,0}]", "info:").strip())
        key_px = 0
        if bgcolor is not None:
            key_px = int(magick(
                frame0(output_path),
                "(", "+clone", "-alpha", "off", "-fuzz", "25%",
                "-fill", "black", "+opaque", bgcolor, "-fill", "white", "-opaque", bgcolor, ")",
                "(", "-clone", "0", "-alpha", "extract", "-threshold", "50%", ")",
                "-delete", "0", "-compose", "Multiply", "-composite",
                "-format", "%[fx:round(mean*w*h)]", "info:",
            ).strip())

    note = " note=quantized_not_verified_pixel_authorship" if args.pixel else ""
    print(f"RESULT: width={rw} height={rh} bytes={bytes_} coverage={coverage:.4f} "
          f"corner_alpha={corner_alpha:.4f} key_px={key_px} canvas={canvas_w}x{canvas_h} "
          f"cutout={cutout_mode} pixel={'yes' if args.pixel else 'no'} "
          f"palette={'yes' if palette_path else 'no'}{note}")


# ------------------------------------------------------------- palette ----

def cmd_palette(args) -> None:
    input_path = safe_path(args.input)
    if Path(args.output).suffix.lower() != ".png":
        raise Fail("output must be a .png file")
    output_path = resolve_output(args.output)
    if input_path == output_path:
        raise Fail("input and output must not be the same path")
    try:
        colors = int(args.colors)
    except ValueError as exc:
        raise Fail(f"--colors must be an integer: {args.colors}") from exc
    if not (2 <= colors <= 256):
        raise Fail("--colors must be between 2 and 256")

    with tempfile.TemporaryDirectory(prefix="kitimages-palette-") as workdir_s:
        workdir = Path(workdir_s)
        src = workdir / ("src" + (Path(args.input).suffix or ".png"))
        shutil.copy2(input_path, src)
        try:
            identify_dims(src)
        except Fail as exc:
            raise Fail(f"invalid input image: {args.input}") from exc

        # Binarizing alpha first makes it a hard clustering dimension, so
        # transparent pixels form their own cluster(s) and never mix their
        # RGB into an opaque cluster's centroid.
        hist = magick(
            frame0(src), "-alpha", "set", "-channel", "A", "-threshold", "50%", "+channel",
            "-depth", "8", "+dither", "-colors", str(colors), "-format", "%c", "histogram:info:-",
        )
        opaque = sorted(
            ((count, hexcolor) for count, hexcolor, alpha in parse_histogram(hist)
             if alpha is None or alpha >= 128),
            reverse=True,
        )
        if not opaque:
            raise Fail("no opaque pixels found")

        tiles = []
        for i, (_, hexcolor) in enumerate(opaque):
            tile = workdir / f"swatch-{i:03d}.png"
            magick("-size", "1x1", f"xc:{hexcolor}", str(tile))
            tiles.append(str(tile))
        magick(*tiles, "+append", "-strip", "-define", "png:exclude-chunk=date,time", str(output_path))

    print(f"RESULT: colors={len(opaque)} requested={colors} width={len(opaque)} "
          f"height=1 path={output_path}")


# --------------------------------------------------------------- atlas ----

def cmd_atlas(args) -> None:
    source = safe_dir(args.source)
    output_dir = resolve_output_dir(args.output_dir, source)
    try:
        columns = int(args.columns)
    except ValueError as exc:
        raise Fail(f"--columns must be an integer: {args.columns}") from exc
    if columns < 1:
        raise Fail("--columns must be >= 1")
    try:
        gap = int(args.gap)
    except ValueError as exc:
        raise Fail(f"--gap must be an integer: {args.gap}") from exc
    if gap < 0:
        raise Fail("--gap must be >= 0")

    files = collect_pngs(source)
    if not files:
        raise Fail(f"no PNG files found under {source}")
    if len(files) > MAX_SHEET_FILES:
        raise Fail(
            f"too many source files ({len(files)} > {MAX_SHEET_FILES}) — "
            f"split into smaller category batches"
        )

    dims = {rel: identify_dims(full) for rel, full in files}
    max_w = max(w for w, _ in dims.values())
    max_h = max(h for _, h in dims.values())
    n = len(files)
    rows = math.ceil(n / columns)
    atlas_w = columns * max_w + (columns - 1) * gap
    atlas_h = rows * max_h + (rows - 1) * gap
    if atlas_w > MAX_DIM or atlas_h > MAX_DIM:
        raise Fail(f"atlas {atlas_w}x{atlas_h} exceeds the {MAX_DIM}px dimension cap")
    if atlas_w * atlas_h > MAX_PIXELS:
        raise Fail(f"atlas {atlas_w}x{atlas_h} exceeds the {MAX_PIXELS}px area cap")

    atlas_path = output_dir / "atlas.png"
    sheet_path = output_dir / "sheet.png"
    frames = []
    # One magick invocation for the whole atlas: a blank canvas followed by
    # one -geometry/-compose Copy/-composite triplet per source, chained in
    # a single command instead of N processes each re-reading and
    # re-writing the whole (growing) canvas file. Copy composition (never
    # Over/alpha-blended) onto the non-overlapping grid cells keeps every
    # pasted pixel byte-identical to its source.
    build_args: list = ["-size", f"{atlas_w}x{atlas_h}", "xc:none"]
    for idx, (rel, full) in enumerate(files):
        col, row = idx % columns, idx // columns
        x, y = col * (max_w + gap), row * (max_h + gap)
        w, h = dims[rel]
        build_args += [frame0(full), "-geometry", f"+{x}+{y}", "-compose", "Copy", "-composite"]
        frames.append({"file": rel, "x": x, "y": y, "width": w, "height": h})
    build_args += ["-strip", "-define", "png:exclude-chunk=date,time", str(atlas_path)]
    magick(*build_args)
    magick(frame0(atlas_path), "-background", "#888888", "-flatten",
           "-resize", "1600x1600>", str(sheet_path))

    atlas_json = {"image": "atlas.png", "width": atlas_w, "height": atlas_h, "frames": frames}
    (output_dir / "atlas.json").write_text(json.dumps(atlas_json, indent=2) + "\n", encoding="utf-8")

    print(f"RESULT: atlas={atlas_path} width={atlas_w} height={atlas_h} "
          f"frames={n} columns={columns} gap={gap}")
    print(f"SHEET: {sheet_path} (grey, bounded review thumbnail)")


# -------------------------------------------------------------- measure ---

def measure_one(full: Path):
    w, h = identify_dims(full)
    channels = magick("identify", "-format", "%[channels]", frame0(full)).strip()
    has_alpha = "a" in channels
    if has_alpha:
        amin = float(magick(frame0(full), "-alpha", "extract", "-format", "%[fx:minima]", "info:").strip())
        amax = float(magick(frame0(full), "-alpha", "extract", "-format", "%[fx:maxima]", "info:").strip())
        coverage = float(magick(frame0(full), "-alpha", "extract", "-format", "%[fx:mean]", "info:").strip())
        corners = [float(v) for v in magick(
            frame0(full), "-alpha", "extract",
            "-format", "%[fx:p{0,0}] %[fx:p{w-1,0}] %[fx:p{0,h-1}] %[fx:p{w-1,h-1}]", "info:",
        ).split()]
    else:
        amin = amax = coverage = 1.0
        corners = [1.0, 1.0, 1.0, 1.0]
    # Alpha-only bounding box (see alpha_bbox docstring) — a colour `-trim`
    # reports the wrong region for a hollow frame or opaque corners around
    # a transparent hole, since its "background" is whatever colour sits
    # at the corner rather than transparency itself.
    bx, by, bw, bh = alpha_bbox(full)
    bbox = {"width": bw, "height": bh, "x": bx, "y": by}
    return w, h, has_alpha, amin, amax, coverage, corners, bbox


def measure_palette(full: Path, palette_colors):
    hist = magick(
        frame0(full), "-alpha", "set", "-channel", "A", "-threshold", "50%", "+channel",
        "-depth", "8", "+dither", "-colors", "8", "-format", "%c", "histogram:info:-",
    )
    entries = [(c, h) for c, h, a in parse_histogram(hist) if a is None or a >= 128]
    total = sum(c for c, _ in entries) or 1
    entries.sort(reverse=True)
    out = []
    for count, hexcolor in entries[:8]:
        entry = {"hex": hexcolor, "share": round(count / total, 4)}
        if palette_colors:
            best, dist = nearest_color(hexcolor, palette_colors)
            entry["nearest"], entry["distance"] = best, dist
        out.append(entry)
    return out


def grid_compose(tiles, cell: int, bg: str, out_path: Path) -> None:
    # Bounded <= SHEET_COLUMNS-wide, multi-row grid (never one unbounded
    # row) built in a single magick invocation, the same one-command
    # technique as the atlas: a blank canvas followed by one
    # -geometry/-compose Copy/-composite triplet per tile.
    n = len(tiles)
    cols = min(SHEET_COLUMNS, n)
    rows = math.ceil(n / cols)
    w, h = cols * cell, rows * cell
    build_args: list = ["-size", f"{w}x{h}", f"xc:{bg}"]
    for idx, tile in enumerate(tiles):
        col, row = idx % cols, idx // cols
        x, y = col * cell, row * cell
        build_args += [str(tile), "-geometry", f"+{x}+{y}", "-compose", "Copy", "-composite"]
    build_args += ["-strip", "-define", "png:exclude-chunk=date,time", str(out_path)]
    magick(*build_args)


def build_measure_sheets(files, output_dir: Path, against_path):
    with tempfile.TemporaryDirectory(prefix="kitimages-measure-") as workdir_s:
        workdir = Path(workdir_s)

        def row(size, bg, out_path, pad, silhouette):
            tiles = []
            for idx, (_, full) in enumerate(files):
                tile = workdir / f"tile-{size}-{idx}.png"
                if silhouette:
                    magick(frame0(full), "-alpha", "set", "-alpha", "extract", "-negate",
                           "-resize", f"{size}x{size}", "-background", bg, "-gravity", "center",
                           "-extent", f"{size + pad}x{size + pad}", str(tile))
                else:
                    magick(frame0(full), "-alpha", "set", "-resize", f"{size}x{size}",
                           "-background", bg, "-gravity", "center",
                           "-extent", f"{size + pad}x{size + pad}", "-flatten", str(tile))
                tiles.append(str(tile))
            grid_compose(tiles, size + pad, bg, out_path)

        row(256, "#888888", output_dir / "sheet.png", 16, False)
        row(160, "#ffffff", output_dir / "silhouette.png", 16, True)
        row(128, "#ffffff", output_dir / "light.png", 12, False)
        row(128, "#1e1f22", output_dir / "dark.png", 12, False)

        rel0, full0 = files[0]
        w0, h0 = identify_dims(full0)
        bounded = w0 * h0 > MAX_PIXELS or w0 > MAX_DIM or h0 > MAX_DIM
        native_path = output_dir / "native.png"
        if bounded:
            magick(frame0(full0), "-resize", f"{MAX_DIM}x{MAX_DIM}>", "-strip", str(native_path))
        else:
            magick(frame0(full0), "-strip", str(native_path))

        if against_path is not None:
            magick(frame0(against_path), "-alpha", "set", "-resize", "256x256",
                   "-background", "#888888", "-gravity", "center", "-extent", "272x272",
                   "-flatten", str(workdir / "a.png"))
            magick(frame0(full0), "-alpha", "set", "-resize", "256x256",
                   "-background", "#888888", "-gravity", "center", "-extent", "272x272",
                   "-flatten", str(workdir / "i.png"))
            magick(str(workdir / "a.png"), str(workdir / "i.png"), "-background", "#888888",
                   "+append", str(output_dir / "against.png"))

    return {"file": rel0, "bounded": bounded, "width": w0, "height": h0}


def cmd_measure(args) -> None:
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise Fail(f"source not found: {args.source}")
    if ":" in str(source):
        raise Fail("path must not contain ':'")
    output_dir = Path(os.path.realpath(Path(args.out).expanduser()))
    if ":" in str(output_dir):
        raise Fail("path must not contain ':'")
    if source.is_dir():
        try:
            output_dir.relative_to(source)
            raise Fail("--out must not be SOURCE or inside it")
        except ValueError:
            pass
    elif output_dir == source:
        raise Fail("--out must not be the source file")
    reject_nonempty_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    against_path = safe_path(args.against) if args.against else None
    palette_colors = read_palette_colors(safe_path(args.palette)) if args.palette else None

    files = collect_pngs(source) if source.is_dir() else [(source.name, source)]
    if not files:
        raise Fail(f"no PNG files found under {source}")
    if len(files) > MAX_SHEET_FILES:
        raise Fail(
            f"too many source files ({len(files)} > {MAX_SHEET_FILES}) — "
            f"split into smaller category batches"
        )

    records = []
    square_count = alpha_count = 0
    for rel, full in files:
        w, h, has_alpha, amin, amax, coverage, corners, bbox = measure_one(full)
        if has_alpha:
            alpha_count += 1
        if w == h:
            square_count += 1
        records.append({
            "file": rel, "width": w, "height": h, "bytes": full.stat().st_size,
            "alpha": has_alpha, "alpha_min": amin, "alpha_max": amax, "coverage": coverage,
            "corners": corners, "bbox": bbox, "palette": measure_palette(full, palette_colors),
        })

    native_info = build_measure_sheets(files, output_dir, against_path)

    measurements = {
        "files": records,
        "native": native_info,
        "summary": {"count": len(records), "square": square_count, "alpha": alpha_count},
    }
    (output_dir / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n", encoding="utf-8")

    print(f"SUMMARY: files={len(records)} square={square_count} alpha={alpha_count}")
    print(f"RESULT: measurements={output_dir / 'measurements.json'}")


# ---------------------------------------------------------------- main ----

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kit-images.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fit = sub.add_parser("fit", help="fit one image onto an exact rectangular canvas")
    p_fit.add_argument("input")
    p_fit.add_argument("output")
    p_fit.add_argument("--canvas", required=True, help="WxH, e.g. 1024x640")
    p_fit.add_argument("--cutout", default="auto", choices=["auto", "yes", "no", "key"])
    p_fit.add_argument("--fuzz", default="10")
    p_fit.add_argument("--pad", default="0.04")
    p_fit.add_argument("--pixel", action="store_true")
    p_fit.add_argument("--palette")
    p_fit.set_defaults(func=cmd_fit)

    p_pal = sub.add_parser("palette", help="build a fixed palette PNG from opaque foreground colours")
    p_pal.add_argument("input")
    p_pal.add_argument("output")
    p_pal.add_argument("--colors", default="16")
    p_pal.set_defaults(func=cmd_palette)

    p_atlas = sub.add_parser("atlas", help="pack PNGs under SOURCE into one deterministic grid atlas")
    p_atlas.add_argument("source")
    p_atlas.add_argument("output_dir")
    p_atlas.add_argument("--columns", default="4")
    p_atlas.add_argument("--gap", default="2")
    p_atlas.set_defaults(func=cmd_atlas)

    p_measure = sub.add_parser(
        "measure",
        help="measure PNGs under SOURCE; writes measurements.json + review sheets",
        epilog="Sheets, exactly: sheet.png, native.png, light.png, dark.png, "
               "silhouette.png, and against.png (only with --against).",
    )
    p_measure.add_argument("source")
    p_measure.add_argument("--out", required=True)
    p_measure.add_argument("--against")
    p_measure.add_argument("--palette")
    p_measure.set_defaults(func=cmd_measure)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Fail as exc:
        print(f"kit-images: {args.command}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
