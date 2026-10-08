#!/usr/bin/env python3
"""Deterministic pixel probe for verifying a rendered image.

Reports background/foreground colors, centering, contrast, text-block layout,
and whether ANY content exists outside the main text block. Also emits
contrast-boosted variants so a second OCR pass can catch hidden low-contrast
text.

Usage:
    python3 inspect_image.py <image> [--threshold 90] [--outdir /tmp]

Requires Pillow.  Exits 2 if Pillow is missing.
"""

import argparse
import collections
import os
import sys

try:
    from PIL import Image, ImageOps
except ImportError:
    print("NO_PIL: install with `python3 -m pip install pillow`")
    sys.exit(2)


def hexs(c):
    return "#%02x%02x%02x" % (c[0], c[1], c[2])


def lum(c):
    """WCAG relative luminance (sRGB gamma-corrected)."""
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(c[0]) + 0.7152 * chan(c[1]) + 0.0722 * chan(c[2])


def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--threshold", type=int, default=90,
                    help="Manhattan RGB distance from bg to count as foreground")
    ap.add_argument("--outdir", default="/tmp")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    im = Image.open(args.image).convert("RGBA")
    W, H = im.size
    px = im.load()
    print("SIZE %d x %d" % (W, H))

    # ---- color histogram -------------------------------------------------
    hist = collections.Counter()
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            hist[px[x, y]] += 1
    total = sum(hist.values())
    print("\nTOP_COLORS (hex, rgba, pct):")
    for c, n in hist.most_common(8):
        print("   %-9s %-20s %6.3f%%" % (hexs(c), str(c), 100.0 * n / total))

    bg = hist.most_common(1)[0][0]
    corners = [px[2, 2], px[W - 3, 2], px[2, H - 3], px[W - 3, H - 3]]
    print("\nBACKGROUND %s   CORNERS %s  uniform=%s"
          % (hexs(bg), [hexs(c) for c in corners],
             all(c == bg for c in corners)))

    def dist(p):
        return abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2])

    # ---- foreground bbox -------------------------------------------------
    T = args.threshold
    minx, miny, maxx, maxy = W, H, -1, -1
    fg_count = 0
    fg_hist = collections.Counter()
    for y in range(H):
        for x in range(W):
            p = px[x, y]
            if dist(p) > T:
                fg_count += 1
                fg_hist[p] += 1
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y

    print("\nFG_PIXELS %d (%.3f%% of image)"
          % (fg_count, 100.0 * fg_count / (W * H)))
    if not fg_count:
        print("NO FOREGROUND CONTENT — image is a solid field of %s" % hexs(bg))
        return

    core = fg_hist.most_common(1)[0][0]          # modal glyph fill
    mean = tuple(round(sum(c[i] * n for c, n in fg_hist.items()) / fg_count)
                 for i in range(3))
    print("FG_CORE (modal fill) %s %s" % (hexs(core), str(core)))
    print("FG_MEAN (incl. antialias) %s %s" % (hexs(mean), str(mean)))
    print("CONTRAST core-vs-bg %.2f:1   mean-vs-bg %.2f:1"
          % (contrast(core, bg), contrast(mean, bg)))
    for label, thr in (("AA-normal", 4.5), ("AA-large", 3.0), ("AAA", 7.0)):
        print("   %-10s >= %.1f : %s"
              % (label, thr, "PASS" if contrast(core, bg) >= thr else "FAIL"))

    print("\nBBOX (%d,%d)-(%d,%d)  w=%d h=%d"
          % (minx, miny, maxx, maxy, maxx - minx + 1, maxy - miny + 1))
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    print("BBOX_CENTER (%.1f, %.1f)  IMAGE_CENTER (%.1f, %.1f)"
          % (cx, cy, W / 2.0, H / 2.0))
    print("CENTER_OFFSET dx=%+.1f dy=%+.1f  (sub-2px is noise)"
          % (cx - W / 2.0, cy - H / 2.0))

    # ---- row / column bands ---------------------------------------------
    def bands(vals):
        out, inb, s = [], False, 0
        for i, n in enumerate(vals):
            if n > 0 and not inb:
                inb, s = True, i
            elif n == 0 and inb:
                inb = False
                out.append((s, i - 1))
        if inb:
            out.append((s, len(vals) - 1))
        return out

    rows = [sum(1 for x in range(0, W, 2) if dist(px[x, y]) > T) for y in range(H)]
    rb = bands(rows)
    print("\nROW_BANDS (separate horizontal blocks): %d -> %s" % (len(rb), rb))

    cols = [sum(1 for y in range(miny, maxy + 1) if dist(px[x, y]) > T)
            for x in range(W)]
    cb = bands(cols)
    print("COL_BANDS (approx glyph groups): %d -> %s" % (len(cb), cb))
    print("   note: bold weights merge adjacent glyphs; sanity check only")

    # ---- purity outside the text block ----------------------------------
    pad = 12
    out_any, out_max = 0, 0
    for y in range(H):
        for x in range(W):
            if (minx - pad) <= x <= (maxx + pad) and (miny - pad) <= y <= (maxy + pad):
                continue
            d = dist(px[x, y])
            if d > 0:
                out_any += 1
                out_max = max(out_max, d)
    print("\nOUTSIDE_TEXTBOX pixels differing from bg: %d (max delta %d)"
          % (out_any, out_max))
    print("   -> %s" % ("PURE: nothing else is rendered anywhere on the canvas"
                        if out_any == 0 else
                        "content exists outside the main block; OCR the boosted variants"))

    alpha = im.split()[3]
    print("ALPHA_EXTREMA %s  (255,255 = fully opaque, nothing hidden)"
          % str(alpha.getextrema()))

    # ---- boosted variants for a second OCR pass -------------------------
    base = os.path.splitext(os.path.basename(args.image))[0]
    g = im.convert("L")
    print("\nGRAY_EXTREMA %s" % str(g.getextrema()))
    p1 = os.path.join(args.outdir, base + "-boost.png")
    p2 = os.path.join(args.outdir, base + "-darkboost.png")
    ImageOps.autocontrast(g, cutoff=0).save(p1)
    g.point([min(255, v * 12) for v in range(256)]).save(p2)
    crop = os.path.join(args.outdir, base + "-crop.png")
    im.crop((max(0, minx - 20), max(0, miny - 20),
             min(W, maxx + 20), min(H, maxy + 20))).save(crop)
    print("WROTE %s\n      %s\n      %s" % (p1, p2, crop))
    print("\nNext: OCR the original AND both boosted variants, then grep for forbidden strings.")


if __name__ == "__main__":
    main()
