#!/usr/bin/env python3
"""Draw a pixel still from a cell map and check a pixel still's grid.

Run through Pillow:
    uv run --no-project --with Pillow python pixel.py draw --map map.json --out NEWDIR [--scale 16] [--background #rrggbb]
    uv run --no-project --with Pillow python pixel.py check --native n.png --preview p.png --palette palette.json [--scale N] [--alpha transparent|opaque] [--max-colors N]
    uv run --no-project --with Pillow python pixel.py palette --native n.png --out NEWDIR

Map: {"palette": {"a": "#rrggbb", ...}, "rows": ["..aa..", ...]}; "." is transparent.
`draw` and `palette` write only into a new --out directory; `check` writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def fail(message: str) -> None:
    print(f"pixel: {message}", file=sys.stderr)
    sys.exit(1)


def hex_of(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def new_out(path: str) -> Path:
    out = Path(path)
    if out.exists():
        fail(f"--out already exists: {out}")
    out.mkdir(parents=True)
    return out


def upscale(native: Image.Image, scale: int) -> Image.Image:
    return native.resize((native.width * scale, native.height * scale), Image.Resampling.NEAREST)


def write_palette(out: Path, colors: list[str]) -> None:
    (out / "palette.json").write_text(
        json.dumps({"colors": sorted(set(colors))}, indent=2) + "\n", encoding="utf-8"
    )


def load_map(path: str) -> tuple[dict[str, str], list[str]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"cannot read map: {exc}")
    if not isinstance(data, dict) or set(data) != {"palette", "rows"}:
        fail('map must be an object with exactly the keys "palette" and "rows"')
    palette, rows = data["palette"], data["rows"]
    if not isinstance(palette, dict) or not palette:
        fail("palette must be a non-empty object")
    for key, value in palette.items():
        if len(key) != 1 or key == ".":
            fail(f"palette key must be one character other than '.': {key!r}")
        if not isinstance(value, str) or not HEX.match(value):
            fail(f"palette colour for {key!r} must be #rrggbb")
    if not isinstance(rows, list) or not rows or not all(isinstance(r, str) and r for r in rows):
        fail("rows must be a non-empty list of non-empty strings")
    if len({len(r) for r in rows}) != 1:
        fail("ragged rows: every row must have the same length")
    unknown = sorted({c for r in rows for c in r} - set(palette) - {"."})
    if unknown:
        fail(f"unknown cell keys: {''.join(unknown)}")
    return palette, rows


def cmd_draw(args: argparse.Namespace) -> None:
    if args.scale <= 0:
        fail("--scale must be a positive integer")
    if args.background is not None and not HEX.match(args.background):
        fail("--background must be #rrggbb")
    palette, rows = load_map(args.map)
    out = new_out(args.out)
    native = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    colors = [v.lower() for v in palette.values()]
    fill = None
    if args.background:
        fill = tuple(int(args.background[i : i + 2], 16) for i in (1, 3, 5)) + (255,)
        colors.append(args.background.lower())
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == ".":
                if fill:
                    native.putpixel((x, y), fill)
                continue
            value = palette[cell]
            native.putpixel((x, y), tuple(int(value[i : i + 2], 16) for i in (1, 3, 5)) + (255,))
    native.save(out / "native.png", "PNG")
    upscale(native, args.scale).save(out / "preview.png", "PNG")
    write_palette(out, colors)
    print(f"RESULT: drew native={native.width}x{native.height} preview_scale={args.scale} colors={len(set(colors))} out={out}")


def cmd_palette(args: argparse.Namespace) -> None:
    native = Image.open(args.native).convert("RGBA")
    px = native.load()
    colors = sorted(
        {hex_of(px[x, y][:3]) for y in range(native.height) for x in range(native.width) if px[x, y][3] == 255}
    )
    out = new_out(args.out)
    write_palette(out, colors)
    print(f"RESULT: palette colors={len(colors)} out={out}")


def cmd_check(args: argparse.Namespace) -> None:
    native = Image.open(args.native).convert("RGBA")
    preview = Image.open(args.preview).convert("RGBA")
    try:
        locked = {c.lower() for c in json.loads(Path(args.palette).read_text(encoding="utf-8"))["colors"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(f"cannot read palette: {exc}")
    problems: list[str] = []

    if preview.width % native.width or preview.height % native.height:
        problems.append("preview is not an integer multiple of native")
        scale = 0
    else:
        scale = preview.width // native.width
        if preview.height // native.height != scale:
            problems.append("preview scale differs between width and height")
            scale = 0
    if args.scale is not None and scale != args.scale:
        problems.append(f"preview scale {scale} != expected {args.scale}")

    npx = native.load()
    alphas = {npx[x, y][3] for y in range(native.height) for x in range(native.width)}
    opaque_colors = {
        hex_of(npx[x, y][:3])
        for y in range(native.height)
        for x in range(native.width)
        if npx[x, y][3] == 255
    }
    out_of_palette = len(opaque_colors - locked)
    if out_of_palette:
        problems.append(f"{out_of_palette} colour(s) outside the palette")
    if args.max_colors is not None and len(opaque_colors) > args.max_colors:
        problems.append(f"{len(opaque_colors)} colours exceed the cap {args.max_colors}")
    partial = alphas - {0, 255}
    if partial:
        problems.append("partial alpha (anti-aliased edge)")
    if args.alpha == "transparent" and 0 not in alphas:
        problems.append("no transparent pixel but transparency was asked")
    if args.alpha == "opaque" and alphas != {255}:
        problems.append("transparent pixel but an opaque result was asked")
    alpha_state = "partial" if partial else ("transparent" if 0 in alphas else "opaque")

    uniform = "n/a"
    if scale:
        ppx = preview.load()
        bad = 0
        for y in range(native.height):
            for x in range(native.width):
                want = npx[x, y] if npx[x, y][3] else (0, 0, 0, 0)
                for dy in range(scale):
                    for dx in range(scale):
                        got = ppx[x * scale + dx, y * scale + dy]
                        if (got if got[3] else (0, 0, 0, 0)) != want:
                            bad += 1
        uniform = "yes" if not bad else f"no({bad} px differ)"
        if bad:
            problems.append(f"preview blocks not uniform: {bad} px differ")

    status = "PASS" if not problems else "FAIL"
    print(
        f"RESULT: {status} native={native.width}x{native.height} preview={preview.width}x{preview.height} "
        f"scale={scale} colors={len(opaque_colors)} out_of_palette={out_of_palette} "
        f"uniform_blocks={uniform} alpha={alpha_state}"
    )
    for problem in problems:
        print(f"pixel: {problem}", file=sys.stderr)
    sys.exit(1 if problems else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    draw = commands.add_parser("draw")
    draw.add_argument("--map", required=True)
    draw.add_argument("--out", required=True)
    draw.add_argument("--scale", type=int, default=16)
    draw.add_argument("--background")
    draw.set_defaults(run=cmd_draw)

    palette = commands.add_parser("palette")
    palette.add_argument("--native", required=True)
    palette.add_argument("--out", required=True)
    palette.set_defaults(run=cmd_palette)

    check = commands.add_parser("check")
    check.add_argument("--native", required=True)
    check.add_argument("--preview", required=True)
    check.add_argument("--palette", required=True)
    check.add_argument("--scale", type=int)
    check.add_argument("--alpha", choices=("transparent", "opaque"))
    check.add_argument("--max-colors", type=int)
    check.set_defaults(run=cmd_check)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
