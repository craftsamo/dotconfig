#!/usr/bin/env python3
"""Apply one approved sample palette to native-grid pixel-art batches.

Usage:
    palette-extract.py extract sample.png --colors 16 --out palette.png
    palette-extract.py apply sample.png out/ base1.png base2.png \
        --grid 48x48 --colors 16 --fit cover
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def parse_grid(value: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("grid must be WxH") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("grid dimensions must be positive")
    return width, height


def extract_palette(sample_path: str, colors: int) -> Image.Image:
    image = Image.open(sample_path).convert("RGBA")
    opaque = Image.new("RGB", image.size, "black")
    opaque.paste(image.convert("RGB"), mask=image.getchannel("A"))
    return opaque.quantize(colors=colors, dither=Image.Dither.NONE)


def fit_native(image: Image.Image, grid: tuple[int, int], fit: str) -> Image.Image:
    if fit == "cover":
        return ImageOps.fit(image, grid, method=Image.Resampling.LANCZOS)
    contained = image.copy()
    contained.thumbnail(grid, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", grid, (0, 0, 0, 0))
    offset = ((grid[0] - contained.width) // 2, (grid[1] - contained.height) // 2)
    canvas.alpha_composite(contained, offset)
    return canvas


def convert(
    input_path: str,
    output_path: str,
    palette: Image.Image,
    grid: tuple[int, int],
    fit: str,
    colors: int,
) -> None:
    source = fit_native(Image.open(input_path).convert("RGBA"), grid, fit)
    alpha = source.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    rgb = ImageEnhance.Contrast(source.convert("RGB")).enhance(1.5)
    rgb = ImageEnhance.Color(rgb).enhance(1.3)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.2)
    rgb = ImageOps.posterize(rgb, 6)
    quantized = rgb.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
    result = quantized.convert("RGBA")
    result.putalpha(alpha)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "PNG", colors=colors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="derive a palette PNG from a sample")
    extract.add_argument("sample")
    extract.add_argument("--colors", type=int, default=16)
    extract.add_argument("--out", default="palette.png")

    apply = commands.add_parser("apply", help="quantize a batch to one sample palette")
    apply.add_argument("sample")
    apply.add_argument("out_dir")
    apply.add_argument("inputs", nargs="+")
    apply.add_argument("--grid", type=parse_grid, required=True)
    apply.add_argument("--colors", type=int, default=16)
    apply.add_argument("--fit", choices=("cover", "contain"), default="cover")

    args = parser.parse_args()
    palette = extract_palette(args.sample, args.colors)

    if args.command == "extract":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        palette.convert("RGB").save(args.out, "PNG")
        print(f"Wrote {args.out} ({args.colors}-color palette from {args.sample})")
        return

    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in args.inputs:
        destination = output_dir / Path(source).name
        convert(source, str(destination), palette, args.grid, args.fit, args.colors)
        print(f"Wrote {destination} ({args.grid[0]}x{args.grid[1]}, alpha preserved)")


if __name__ == "__main__":
    main()
