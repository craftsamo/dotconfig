#!/usr/bin/env python3
"""Sample-anchored palette for pixel-art batches.

The bundled `pixel-art` skill covers the NAMED-palette anchor directly
(``pixel_art.py --palette PICO_8``). This helper covers the OTHER anchor from
the concept/plan slice: derive a fixed palette from ONE approved sample sprite
and quantize every image in the batch to that SAME palette, so a set stays
visually consistent even though each base was generated separately.

Why not just call pixel_art.py? Its ``palette=`` only accepts an int (adaptive
N) or a named-palette string — not an arbitrary sample-derived palette. So the
sample-anchor lives here, in this profile, and the upstream ``pixel_art.py`` is
never edited (it is read-in-place from the catalog and auto-updates).

The pipeline mirrors pixel_art.py (downscale by block -> Floyd-Steinberg
quantize -> nearest upscale); only the palette source differs.

Usage:
    # Record the palette derived from the approved sample:
    palette-extract.py extract sample.png --colors 16 --out palette.png

    # Convert a batch to the sample's palette (writes into out_dir/):
    palette-extract.py apply sample.png out_dir/ base1.png base2.png \
        --colors 16 --block 6
"""
from __future__ import annotations

import argparse
import os

from PIL import Image, ImageEnhance, ImageOps


def extract_palette(sample_path: str, colors: int) -> Image.Image:
    """Return a mode-``P`` image whose palette is the sample's top ``colors``."""
    img = Image.open(sample_path).convert("RGB")
    return img.quantize(colors=colors, dither=Image.NONE)


def convert(
    input_path: str,
    output_path: str,
    pal_img: Image.Image,
    block: int = 6,
    contrast: float = 1.5,
    color: float = 1.3,
    sharpness: float = 1.2,
    posterize_bits: int = 6,
) -> None:
    """Pixel-convert one image, quantizing to ``pal_img``'s palette."""
    img = Image.open(input_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(color)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    img = ImageOps.posterize(img, posterize_bits)

    w, h = img.size
    small = img.resize((max(1, w // block), max(1, h // block)), Image.NEAREST)
    # Quantize AFTER downscale so dithering aligns with the final pixel grid.
    quant = small.quantize(palette=pal_img, dither=Image.FLOYDSTEINBERG)
    quant.convert("RGB").resize((w, h), Image.NEAREST).save(output_path, "PNG")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="derive + save a palette PNG from a sample")
    pe.add_argument("sample")
    pe.add_argument("--colors", type=int, default=16)
    pe.add_argument("--out", default="palette.png")

    pa = sub.add_parser("apply", help="quantize a batch to the sample's palette")
    pa.add_argument("sample")
    pa.add_argument("out_dir")
    pa.add_argument("inputs", nargs="+")
    pa.add_argument("--colors", type=int, default=16)
    pa.add_argument("--block", type=int, default=6)

    args = p.parse_args()
    pal = extract_palette(args.sample, args.colors)

    if args.cmd == "extract":
        pal.convert("RGB").save(args.out, "PNG")
        print(f"Wrote {args.out} ({args.colors}-color palette from {args.sample})")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    for src in args.inputs:
        dst = os.path.join(args.out_dir, os.path.basename(src))
        convert(src, dst, pal, block=args.block)
        print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
