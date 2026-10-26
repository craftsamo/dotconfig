#!/usr/bin/env python3
"""Render native-grid pixel frames from cell maps and build a contact sheet.

Run through Pillow:
    uv run --no-project --with Pillow python cels.py draw --maps DIR --out NEWDIR [--background #rrggbb]
    uv run --no-project --with Pillow python cels.py sheet --frames DIR --out NEW.png [--scale N] [--columns N]

DIR holds frame_*.json maps: {"palette": {"a": "#rrggbb", ...}, "rows": ["..aa..", ...]};
"." is a background cell. Every map must share one palette and one size.
`draw` writes frame_0001.png, frame_0002.png, ... into a new --out directory;
`sheet` writes one new PNG (ImageMagick `+append` rows, never montage).
Nothing is written outside --out.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def fail(message: str) -> None:
    print(f"cels: {message}", file=sys.stderr)
    sys.exit(1)


def load_map(path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"cannot read map {path.name}: {exc}")
    if not isinstance(data, dict) or set(data) != {"palette", "rows"}:
        fail(f'{path.name}: map must be an object with exactly the keys "palette" and "rows"')
    palette, rows = data["palette"], data["rows"]
    if not isinstance(palette, dict) or not palette:
        fail(f"{path.name}: palette must be a non-empty object")
    for key, value in palette.items():
        if len(key) != 1 or key == ".":
            fail(f"{path.name}: palette key must be one character other than '.': {key!r}")
        if not isinstance(value, str) or not HEX.match(value):
            fail(f"{path.name}: palette colour for {key!r} must be #rrggbb")
    if not isinstance(rows, list) or not rows or not all(isinstance(r, str) and r for r in rows):
        fail(f"{path.name}: rows must be a non-empty list of non-empty strings")
    if len({len(r) for r in rows}) != 1:
        fail(f"{path.name}: ragged rows: every row must have the same length")
    unknown = sorted({c for r in rows for c in r} - set(palette) - {"."})
    if unknown:
        fail(f"{path.name}: unknown cell keys: {''.join(unknown)}")
    return palette, rows


def new_out(path: str) -> Path:
    out = Path(path)
    if out.exists():
        fail(f"--out already exists: {out}")
    return out


def rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def cmd_draw(args: argparse.Namespace) -> None:
    if not HEX.match(args.background):
        fail("--background must be #rrggbb")
    files = sorted(Path(args.maps).glob("frame_*.json"))
    if not files:
        fail(f"no frame_*.json in {args.maps}")
    loaded = [(f, *load_map(f)) for f in files]
    first_palette = {k: v.lower() for k, v in loaded[0][1].items()}
    size = (len(loaded[0][2][0]), len(loaded[0][2]))
    for f, palette, rows in loaded[1:]:
        if {k: v.lower() for k, v in palette.items()} != first_palette:
            fail(f"{f.name}: palette differs from {files[0].name}")
        if (len(rows[0]), len(rows)) != size:
            fail(f"{f.name}: size {len(rows[0])}x{len(rows)} differs from {size[0]}x{size[1]}")
    out = new_out(args.out)
    out.mkdir(parents=True)
    fill = rgb(args.background)
    for index, (_, palette, rows) in enumerate(loaded, start=1):
        image = Image.new("RGB", size, fill)
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell != ".":
                    image.putpixel((x, y), rgb(palette[cell]))
        image.save(out / f"frame_{index:04d}.png", "PNG")
    print(f"RESULT: drew frames={len(loaded)} native={size[0]}x{size[1]} out={out}")


def cmd_sheet(args: argparse.Namespace) -> None:
    if args.scale <= 0 or args.columns <= 0:
        fail("--scale and --columns must be positive integers")
    files = sorted(Path(args.frames).glob("frame_*.png"))
    if not files:
        fail(f"no frame_*.png in {args.frames}")
    out = new_out(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    command = ["magick", "-background", "#808080"]
    for start in range(0, len(files), args.columns):
        command.append("(")
        for file in files[start : start + args.columns]:
            command += ["(", str(file), "-filter", "point", "-scale", f"{args.scale * 100}%",
                        "-bordercolor", "#808080", "-border", "2", ")"]
        command += ["+append", ")"]
    command += ["-append", str(out)]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        fail("'magick' not found")
    except subprocess.CalledProcessError as exc:
        fail(f"magick failed: {exc.stderr.strip()}")
    print(f"RESULT: sheet frames={len(files)} columns={args.columns} scale={args.scale} out={out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    draw = sub.add_parser("draw")
    draw.add_argument("--maps", required=True)
    draw.add_argument("--out", required=True)
    draw.add_argument("--background", default="#000000")
    draw.set_defaults(func=cmd_draw)
    sheet = sub.add_parser("sheet")
    sheet.add_argument("--frames", required=True)
    sheet.add_argument("--out", required=True)
    sheet.add_argument("--scale", type=int, default=4)
    sheet.add_argument("--columns", type=int, default=8)
    sheet.set_defaults(func=cmd_sheet)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
