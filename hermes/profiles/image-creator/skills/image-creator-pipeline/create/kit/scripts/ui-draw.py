#!/usr/bin/env python3
"""
ui-draw.py — the `create-kit` leaf's renderer: a deterministic game-UI KIT
(buttons, panels, bars) as flat-vector or pixel art. Stdlib + ImageMagick
(`magick`) only; no image_generate, no text glyphs (runtime overlays labels).

Tooling: ImageMagick (`magick`) always; `--style flat-vector` ADDITIONALLY
REQUIRES `rsvg-convert` (librsvg) on PATH and refuses to run without it —
ImageMagick's own built-in SVG delegate does not reliably render an
unfilled (`fill="none"`) stroked shape (confirmed directly: a bars `frame`
came out fully transparent), so there is no lower-fidelity fallback here
on purpose. `./install.sh --deps` installs librsvg. `--style pixel` never
touches an SVG renderer and has no `rsvg-convert` requirement.

Usage:
  ui-draw.py --out DIR --contents buttons,panels,bars --style flat-vector|pixel
             [--palette '#surface,#ink,#accent'] [--radius N] [--stroke N]
             [--scale 1-4] [--states normal,pressed] [--slug kit]
             [--items FILE.json]

  --out       output directory; must not already exist and be non-empty
              (atomic: built in a temp dir, then moved into place).
  --contents  comma list, subset of: buttons, panels, bars
  --style     flat-vector | pixel (closed set; no other style is supported)
  --palette   three #rrggbb roles: surface,ink,accent (default
              #243246,#f3f5ff,#f8b84e)
  --radius    corner radius in logical px (default 12 flat-vector / 0 pixel;
              an explicit value is rejected if it does not fit the smallest
              selected category)
  --stroke    border width in logical px (default 2 flat-vector / 1 pixel;
              same fit rule as --radius)
  --scale     integer 1-4. flat-vector: the SVG canvas coordinates (size,
              radius, stroke) are expanded by this factor before rendering.
              pixel: the logical bitmap is upscaled this many times with
              nearest-neighbour (crisp, no antialiasing).
  --states    comma list, subset of: normal, pressed, hover, disabled
              (default normal,pressed). Only the buttons category carries
              state variants; panels and bars render one file per item.
  --slug      file-name stem (default: kit). Must be a slug: a-z 0-9 and
              internal hyphens only.
  --items     optional JSON file overriding the default items per category:
                {"buttons": ["primary", "secondary", "cancel"],
                 "panels": ["window"],
                 "bars": ["frame", "fill"]}
              A category absent from the file keeps its default items.
              Omit this flag unless the default items do not fit the brief.
              A NAME OUTSIDE THE DOCUMENTED DEFAULTS (e.g. "cancel" above)
              is not a bespoke design: it gets a generic fallback role
              (buttons/panels: the `surface` palette colour; bars: `accent`)
              and the SAME geometry as its category's other items — never a
              per-name look. `manifest.json` marks such an entry
              `"custom_name": true` and the RESULT line lists it under
              `custom_names=` so this is never silent. If the brief implies
              a genuinely different look per custom name, that is a scope
              question — ask, don't ship a look-alike as if it were bespoke.

Logical sizes (before --scale): flat-vector buttons 384x128, panels 512x384,
bars 512x64; pixel buttons 48x16, panels 96x64, bars 64x8.

Default items: buttons primary + secondary, panels window + tooltip, bars
frame + fill. Buttons render every requested state; panels and bars render
once each (no state suffix) — a panel/bar is not a pressable widget. A
panel's `window` gets a flat accent title-bar strip along its top (both
styles); `tooltip` does not — that is the only default-item look
difference within a category. The `frame` and `fill` items of a bar share
one outer box; `fill` is inset inside `frame`'s stroke by
`BAR_FILL_PAD_LOGICAL[style]` more (2 logical px for flat-vector, a
visible gap its larger canvas can afford; 0 for pixel — its fill fills
the whole hollow interior right up to the stroke, since an 8px-tall bar
cannot spare a gap the way flat-vector can), drawn with no border of its
own, so a filled bar never drifts relative to its frame and never
overdraws the frame's border.

Output layout under OUT:
  assets/<category>/<slug>_<name>.svg / .png                (panels, bars)
  assets/<category>/<slug>_<name>_<state>.svg / .png         (buttons)
  manifest.json   — every file, its category/state and its measured size
  slices.json     — 9-slice left/right/top/bottom insets, in FINAL (scaled)
                    output pixels, for every stretchable PNG (buttons and
                    panels, plus a bar's frame — never a bar's flat fill).
                    A panel's `window` gets its OWN `top`
                    (max(generic (radius+stroke)*scale, the title bar's
                    own bottom edge)) so a 9-slice stretch never tears
                    through the title bar; every other item uses the
                    plain generic inset on all four sides. Geometry that
                    would leave no non-empty centre band anywhere —
                    including under a window's title bar, or in a bar's
                    inset fill — is REJECTED up front (see
                    validate_geometry) rather than silently clamped, so
                    every slices.json entry always satisfies
                    left+right < width and top+bottom < height.

Deterministic: the same arguments reproduce the same bytes — no timestamps,
metadata is stripped from every PNG, and manifest/slices JSON keys are
written in a fixed order (never sorted, never wall-clock dependent).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CONTENTS = ("buttons", "panels", "bars")
STYLES = ("flat-vector", "pixel")
ALL_STATES = ("normal", "pressed", "hover", "disabled")
DEFAULT_STATES = ("normal", "pressed")
STATEFUL_CATEGORIES = ("buttons",)

DEFAULT_ITEMS = {
    "buttons": ["primary", "secondary"],
    "panels": ["window", "tooltip"],
    "bars": ["frame", "fill"],
}
# Palette role each default item is drawn from.
ITEM_ROLE = {
    "buttons": {"primary": "accent", "secondary": "surface"},
    "panels": {"window": "surface", "tooltip": "surface"},
    "bars": {"frame": "ink", "fill": "accent"},
}
# Items that must never be reported as 9-sliceable (a solid progress fill
# has no border worth protecting, and stretching it is the whole point).
NO_SLICE_ITEMS = {("bars", "fill")}
# A custom `--items` name outside ITEM_ROLE gets this generic role per
# category — never a bespoke per-name look (see the module docstring).
DEFAULT_ROLE_FALLBACK = {"buttons": "surface", "panels": "surface", "bars": "accent"}
# A bar's `fill` is inset this many EXTRA logical px beyond its `frame`'s
# own stroke on every side, so it never draws over the frame's border.
# Per style, not a shared constant: flat-vector's canvas (512x64 logical)
# can afford a visible 2px gap between frame and fill; pixel's canvas is
# only 8px tall, so the same 2px extra pad would leave a 2px-tall fill (25%
# of the bar) — the only real requirement is non-overlap with the stroke,
# not a gap, so pixel gets 0 extra: the fill's inset equals the frame's
# stroke exactly, filling the whole hollow interior (6px tall at the
# default stroke=1, i.e. 75% of the bar). For flat-vector this extra is
# scaled together with everything else on the SVG canvas; for pixel it
# stays in logical units (the whole raster is upscaled afterward).
BAR_FILL_PAD_LOGICAL = {"flat-vector": 2, "pixel": 0}

LOGICAL_SIZE = {
    "flat-vector": {"buttons": (384, 128), "panels": (512, 384), "bars": (512, 64)},
    "pixel": {"buttons": (48, 16), "panels": (96, 64), "bars": (64, 8)},
}
DEFAULT_RADIUS = {"flat-vector": 12, "pixel": 0}
DEFAULT_STROKE = {"flat-vector": 2, "pixel": 1}
DEFAULT_PALETTE = ("#243246", "#f3f5ff", "#f8b84e")  # surface, ink, accent

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class UsageError(Exception):
    pass


def die(message: str) -> "None":
    raise UsageError(message)


# ── colour helpers ──────────────────────────────────────────────────────


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    if not HEX_RE.match(value):
        die(f"colour must be #rrggbb: {value!r}")
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def clamp255(v: float) -> int:
    return max(0, min(255, int(round(v))))


def adjust_for_state(rgb: tuple[int, int, int], state: str) -> tuple[int, int, int]:
    r, g, b = rgb
    if state == "normal":
        return rgb
    if state == "pressed":
        return tuple(clamp255(c * 0.78) for c in rgb)  # type: ignore[return-value]
    if state == "hover":
        return tuple(clamp255(c * 1.12) for c in rgb)  # type: ignore[return-value]
    if state == "disabled":
        gray = 136
        return tuple(clamp255(c * 0.5 + gray * 0.5) for c in rgb)  # type: ignore[return-value]
    die(f"unknown state: {state}")
    raise AssertionError  # unreachable, satisfies type checkers


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


# ── validation ───────────────────────────────────────────────────────────


def parse_list(raw: str, valid: tuple[str, ...], label: str) -> list[str]:
    items = [v.strip() for v in raw.split(",") if v.strip()]
    if not items:
        die(f"--{label} must list at least one value")
    for item in items:
        if item not in valid:
            die(f"unsupported {label}: {item!r} (must be one of {', '.join(valid)})")
    # Preserve the caller's order but drop duplicates, first occurrence wins.
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def validate_slug(value: str, label: str) -> str:
    if not SLUG_RE.match(value):
        die(f"{label} must be a slug (a-z 0-9 and internal hyphens only): {value!r}")
    if ".." in value or "/" in value or "\\" in value:
        die(f"{label} must not contain path separators: {value!r}")
    return value


def min_logical_dim(style: str, contents: list[str]) -> int:
    dims = [min(LOGICAL_SIZE[style][c]) for c in contents]
    return min(dims)


def validate_geometry(style: str, contents: list[str], radius: int, stroke: int, scale: int) -> None:
    """Reject geometry up front rather than silently clamp it later: every
    accepted (radius, stroke) must leave a non-empty central band for every
    requested category (`2*(radius+stroke) < min(w, h)`, strictly — a zero
    or negative band means the "corner" has eaten the whole shape); a
    `bars` category must additionally leave room for the fill's own inset
    (`stroke + BAR_FILL_PAD_LOGICAL[style]` on every side); a `panels`
    category must leave a positive band UNDER the `window` item's
    title-bar strip too — that strip's own bottom edge, not just the
    generic corner radius, is what the top slice must clear (see
    window_title_bar_rows), or a 9-slice stretch would tear right through
    the title bar. `scale` is needed for this last check because the
    title-bar formula is computed at FINAL pixels for flat-vector (its
    canvas coordinates already include `scale`) but at LOGICAL pixels for
    pixel (upscaled as a whole afterward) — see window_title_bar_rows."""
    if radius < 0:
        die(f"--radius must be >= 0, got {radius}")
    if stroke < 0:
        die(f"--stroke must be >= 0, got {stroke}")
    for category in contents:
        w, h = LOGICAL_SIZE[style][category]
        m = min(w, h)
        band = m - 2 * (radius + stroke)
        if band <= 0:
            limit = (m - 1) // 2
            max_radius = limit - stroke
            hint = (
                f"max radius at --stroke {stroke} is {max_radius}"
                if max_radius >= 0
                else f"--stroke {stroke} alone is already too large"
            )
            die(
                f"--radius {radius} + --stroke {stroke} leaves no central band for "
                f"{category} at {style} logical size {w}x{h} "
                f"(need 2*(radius+stroke) < {m}; {hint})"
            )
        if category == "bars":
            fill_pad_extra = BAR_FILL_PAD_LOGICAL[style]
            fill_pad = stroke + fill_pad_extra
            if m - 2 * fill_pad <= 0:
                die(
                    f"--stroke {stroke} leaves no room for a bar's inset fill at "
                    f"{style} logical size {w}x{h} "
                    f"(stroke + {fill_pad_extra} must be < {m // 2})"
                )
        if category == "panels":
            height_final = h * scale
            bottom_final = (radius + stroke) * scale
            if style == "flat-vector":
                _, title_bottom_final = window_title_bar_rows(h * scale, stroke * scale)
            else:  # pixel: computed in logical units, then the whole raster scales
                _, title_bottom_logical = window_title_bar_rows(h, stroke)
                title_bottom_final = title_bottom_logical * scale
            if height_final - title_bottom_final - bottom_final <= 0:
                die(
                    f"--radius {radius} + --stroke {stroke} at --scale {scale} leaves no "
                    f"central band under panels' `window` title bar ({style} logical size "
                    f"{w}x{h}): title bar bottom={title_bottom_final}px + generic bottom "
                    f"inset={bottom_final}px must be < final height={height_final}px"
                )


def load_items_override(path: Path, contents: list[str]) -> dict[str, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"--items: cannot read/parse {path}: {exc}")
        raise
    if not isinstance(data, dict):
        die("--items must be a JSON object of category -> [item names]")
    items: dict[str, list[str]] = {}
    for category in contents:
        names = data.get(category)
        if names is None:
            items[category] = list(DEFAULT_ITEMS[category])
            continue
        if not isinstance(names, list) or not names:
            die(f"--items[{category}] must be a non-empty list of names")
        for name in names:
            if not isinstance(name, str) or not NAME_RE.match(name):
                die(f"--items[{category}] name must be a slug: {name!r}")
        items[category] = list(dict.fromkeys(names))
    return items


# ── ImageMagick invocation ──────────────────────────────────────────────


def run_magick(args: list[str]) -> None:
    magick = shutil.which("magick")
    if not magick:
        die("'magick' (ImageMagick) not found — run ./install.sh --deps")
    try:
        subprocess.run([magick, *args], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        die(f"magick failed: {' '.join(args)}\n{exc.stderr.decode(errors='replace')}")


STRIP_ARGS = ["-strip", "-define", "png:exclude-chunks=date,time,tIME"]


# ── flat-vector rendering (real SVG, rasterized by ImageMagick) ─────────


def rounded_rect_svg(
    w: int, h: int, radius: int, stroke: int, fill: str | None, stroke_color: str
) -> str:
    inset = stroke / 2
    rx = ry = max(radius - inset, 0)
    x = y = inset
    rw = w - stroke
    rh = h - stroke
    fill_attr = fill if fill else "none"
    return (
        f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" rx="{rx}" ry="{ry}" '
        f'fill="{fill_attr}" stroke="{stroke_color}" stroke-width="{stroke}"/>'
    )


def build_button_svg(w: int, h: int, radius: int, stroke: int, fill_hex: str, ink_hex: str) -> str:
    body = rounded_rect_svg(w, h, radius, stroke, fill_hex, ink_hex)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{body}</svg>'
    )


def window_title_bar_rows(h: int, stroke: int) -> tuple[int, int]:
    """The `window` panel's title-bar strip's (y0, y1) rows, in whatever
    units `h`/`stroke` are given — callers pass FINAL px for flat-vector
    (its SVG canvas coordinates already include `--scale`) and LOGICAL px
    for pixel (the whole raster is upscaled as a unit afterward), and each
    rescales the result appropriately for its own pipeline. Shared by both
    styles so a flat-vector and a pixel `window` agree on where the bar
    sits: inset from the border by `stroke` (never bleeds past the outer
    rounded corner), height ~14% of the panel (with a floor so it stays
    visible on the smallest pixel logical size)."""
    bar_h = max(int(h * 0.14), stroke + 4)
    return stroke, stroke + bar_h


def panel_title_bar_rect(w: int, h: int, stroke: int) -> tuple[int, int, int, int]:
    """Returns (x0, y0, x1, y1) — see window_title_bar_rows for the y part."""
    y0, y1 = window_title_bar_rows(h, stroke)
    return stroke, y0, w - stroke, y1


def build_panel_svg(
    w: int, h: int, radius: int, stroke: int, name: str, surface_hex: str, ink_hex: str, accent_hex: str
) -> str:
    parts = [rounded_rect_svg(w, h, radius, stroke, surface_hex, ink_hex)]
    if name == "window":
        x0, y0, x1, y1 = panel_title_bar_rect(w, h, stroke)
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="{accent_hex}"/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{"".join(parts)}</svg>'
    )


def bar_fill_inset(w: int, h: int, radius: int, pad: int) -> tuple[int, int, int]:
    """Shared geometry for a bar's `fill`: inset by `pad` on every side, no
    border of its own. Dies rather than emitting a degenerate/negative box —
    validate_geometry should already guarantee this fits, so hitting this is
    a bug in that guard, not a normal user error."""
    iw, ih = w - 2 * pad, h - 2 * pad
    if iw <= 0 or ih <= 0:
        die(
            f"bars fill inset (pad={pad}) leaves no room at {w}x{h} "
            "— this should have been rejected by validate_geometry"
        )
    ir = max(radius - pad, 0)
    return iw, ih, ir


def build_bar_svg(
    w: int,
    h: int,
    radius: int,
    stroke: int,
    name: str,
    ink_hex: str,
    accent_hex: str,
    scale: int,
    fill_pad_extra_logical: int,
) -> str:
    if name == "frame":
        body = rounded_rect_svg(w, h, radius, stroke, None, ink_hex)
    elif name == "fill":
        # Shares the exact same outer box as `frame` (same w/h/radius) but
        # is inset by the frame's stroke plus `fill_pad_extra_logical` so
        # it never draws over the border, and it is drawn filled with no
        # border of its own. `stroke` here is already scaled by the caller
        # (render_item passes radius*scale/stroke*scale), so the extra
        # logical padding constant must be scaled too, or a --scale > 1 run
        # would under-inset the fill relative to the frame. The caller
        # picks `fill_pad_extra_logical` per style (see
        # BAR_FILL_PAD_LOGICAL) — flat-vector's larger canvas can afford a
        # visible gap between frame and fill; nothing beyond "don't
        # overlap the stroke" is required.
        pad = stroke + fill_pad_extra_logical * scale
        iw, ih, ir = bar_fill_inset(w, h, radius, pad)
        body = (
            f'<g transform="translate({pad},{pad})">'
            + rounded_rect_svg(iw, ih, ir, 0, accent_hex, "none")
            + "</g>"
        )
    else:
        # A custom bar item name (outside the frame/fill contract) gets a
        # plain filled rounded rect — the generic look, never a bespoke
        # per-name interpretation of "bar item".
        body = rounded_rect_svg(w, h, radius, stroke, accent_hex, ink_hex)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{body}</svg>'
    )


def require_rsvg_convert() -> str:
    """`--style flat-vector` FAILS CLOSED without rsvg-convert (librsvg) —
    same tool the sibling `create-icon` renderer (logo-to-icons.sh) prefers,
    but that script can fall back to plain ImageMagick because every shape
    it draws is filled. This one cannot: ImageMagick's own built-in SVG
    delegate does not reliably render an unfilled (`fill="none"`) stroked
    shape — confirmed directly (ImageMagick 7.1.2-26, a plain stroke-only
    rect rasterized fully transparent) — which is exactly the shape used
    for a bars `frame`. A silently-invisible `frame` is worse than a
    stopped run, so there is no lower-fidelity fallback path here on
    purpose. `--style pixel` never calls this — it has no SVG renderer in
    its path at all."""
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        die(
            "rsvg-convert (librsvg) not found — required for --style flat-vector "
            "(ImageMagick's own SVG delegate does not render an unfilled/stroke-only "
            "shape, e.g. a bars `frame`); run ./install.sh --deps. "
            "--style pixel has no rsvg-convert requirement."
        )
    return rsvg


def raster_svg(svg_text: str, w: int, h: int, rsvg: str, work: Path, out_png: Path) -> None:
    svg_path = work / "shape.svg"
    svg_path.write_text(svg_text, encoding="utf-8")
    raw_png = work / "raster_raw.png"
    try:
        subprocess.run(
            [rsvg, "-w", str(w), "-h", str(h), str(svg_path), "-o", str(raw_png)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        die(f"rsvg-convert failed: {exc.stderr.decode(errors='replace')}")
    run_magick([str(raw_png), *STRIP_ARGS, str(out_png)])


# ── pixel rendering (raw raster, no antialiasing, nearest upscale) ──────


def in_rounded_rect(px: float, py: float, w: int, h: int, r: int) -> bool:
    if not (0 <= px <= w and 0 <= py <= h):
        return False
    if r <= 0:
        return True
    if px < r and py < r:
        return (px - r) ** 2 + (py - r) ** 2 <= r * r
    if px > w - r and py < r:
        return (px - (w - r)) ** 2 + (py - r) ** 2 <= r * r
    if px < r and py > h - r:
        return (px - r) ** 2 + (py - (h - r)) ** 2 <= r * r
    if px > w - r and py > h - r:
        return (px - (w - r)) ** 2 + (py - (h - r)) ** 2 <= r * r
    return True


Overlay = tuple[int, int, int, int, tuple[int, int, int]]  # x0, y0, x1, y1, rgb


def apply_overlays(x: int, y: int, color: tuple[int, int, int], overlays: list[Overlay]) -> tuple[int, int, int]:
    for x0, y0, x1, y1, ocolor in overlays:
        if x0 <= x < x1 and y0 <= y < y1:
            color = ocolor
    return color


def pixel_raster(
    w: int,
    h: int,
    radius: int,
    stroke: int,
    fill_rgb: tuple[int, int, int] | None,
    stroke_rgb: tuple[int, int, int],
    overlays: list[Overlay] | None = None,
) -> tuple[list[tuple[int, int, int]], list[int]]:
    """Build a w*h RGB row-major list and a matching alpha list. Every test
    is a plain boolean (no coverage fraction), so corners come out stepped
    on purpose — that is the pixel-art look, not an artifact. `overlays`
    (e.g. a panel's title-bar strip) only ever paints over already-filled
    interior pixels, so it automatically respects the rounded corners."""
    overlays = overlays or []
    rgb: list[tuple[int, int, int]] = []
    alpha: list[int] = []
    inner_r = max(radius - stroke, 0)
    for y in range(h):
        for x in range(w):
            px, py = x + 0.5, y + 0.5
            outer = in_rounded_rect(px, py, w, h, radius)
            inner = in_rounded_rect(px - stroke, py - stroke, w - 2 * stroke, h - 2 * stroke, inner_r)
            if inner and fill_rgb is not None:
                rgb.append(apply_overlays(x, y, fill_rgb, overlays))
                alpha.append(255)
            elif outer and not inner:
                rgb.append(stroke_rgb)
                alpha.append(255)
            else:
                rgb.append((0, 0, 0))
                alpha.append(0)
    return rgb, alpha


def pixel_fill_inset_raster(
    w: int,
    h: int,
    pad: int,
    radius: int,
    fill_rgb: tuple[int, int, int],
    overlays: list[Overlay] | None = None,
) -> tuple[list[tuple[int, int, int]], list[int]]:
    """A solid rounded-rect fill inset by `pad` on every side, no border of
    its own, fully transparent everywhere outside the inset shape — the
    pixel-style twin of the flat-vector `fill` path in build_bar_svg. Never
    draws a stroke ring: that is what makes it a `fill`, not a `frame`."""
    if w - 2 * pad <= 0 or h - 2 * pad <= 0:
        die(
            f"bars fill inset (pad={pad}) leaves no room at {w}x{h} "
            "— this should have been rejected by validate_geometry"
        )
    overlays = overlays or []
    inner_r = max(radius - pad, 0)
    rgb: list[tuple[int, int, int]] = []
    alpha: list[int] = []
    for y in range(h):
        for x in range(w):
            px, py = x + 0.5 - pad, y + 0.5 - pad
            inside = in_rounded_rect(px, py, w - 2 * pad, h - 2 * pad, inner_r)
            if inside:
                rgb.append(apply_overlays(x, y, fill_rgb, overlays))
                alpha.append(255)
            else:
                rgb.append((0, 0, 0))
                alpha.append(0)
    return rgb, alpha


def write_ppm(path: Path, w: int, h: int, rgb: list[tuple[int, int, int]]) -> None:
    with open(path, "wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode("ascii"))
        for r, g, b in rgb:
            f.write(bytes((r, g, b)))


def write_pgm(path: Path, w: int, h: int, alpha: list[int]) -> None:
    with open(path, "wb") as f:
        f.write(f"P5\n{w} {h}\n255\n".encode("ascii"))
        f.write(bytes(alpha))


def compose_pixel_png(
    w: int,
    h: int,
    rgb: list[tuple[int, int, int]],
    alpha: list[int],
    scale: int,
    work: Path,
    out_png: Path,
) -> None:
    ppm = work / "px.ppm"
    pgm = work / "px.pgm"
    write_ppm(ppm, w, h, rgb)
    write_pgm(pgm, w, h, alpha)
    logical_png = work / "px_logical.png"
    run_magick(
        [
            str(ppm),
            str(pgm),
            "-alpha",
            "off",
            "-compose",
            "CopyOpacity",
            "-composite",
            *STRIP_ARGS,
            str(logical_png),
        ]
    )
    if scale == 1:
        shutil.copyfile(logical_png, out_png)
        return
    run_magick(
        [
            str(logical_png),
            "-filter",
            "point",
            "-resize",
            f"{w * scale}x{h * scale}",
            *STRIP_ARGS,
            str(out_png),
        ]
    )


def raster_pixel(
    w: int,
    h: int,
    radius: int,
    stroke: int,
    fill_rgb: tuple[int, int, int] | None,
    stroke_rgb: tuple[int, int, int],
    scale: int,
    work: Path,
    out_png: Path,
    overlays: list[Overlay] | None = None,
) -> None:
    rgb, alpha = pixel_raster(w, h, radius, stroke, fill_rgb, stroke_rgb, overlays)
    compose_pixel_png(w, h, rgb, alpha, scale, work, out_png)


def raster_pixel_fill_inset(
    w: int,
    h: int,
    pad: int,
    radius: int,
    fill_rgb: tuple[int, int, int],
    scale: int,
    work: Path,
    out_png: Path,
    overlays: list[Overlay] | None = None,
) -> None:
    rgb, alpha = pixel_fill_inset_raster(w, h, pad, radius, fill_rgb, overlays)
    compose_pixel_png(w, h, rgb, alpha, scale, work, out_png)


def svg_wrap_raster(png_path: Path, w: int, h: int) -> str:
    """A pixel item still gets an `.svg` (the required source pair), as a
    crisp `image-rendering:pixelated` wrapper around the exact PNG bytes —
    there is no vector path to draw for a hand-placed pixel grid."""
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges">'
        f'<image width="{w}" height="{h}" style="image-rendering:pixelated" '
        f'xlink:href="data:image/png;base64,{b64}"/></svg>'
    )


# ── item rendering dispatch ──────────────────────────────────────────────


def render_item(
    category: str,
    name: str,
    state: str | None,
    style: str,
    radius: int,
    stroke: int,
    scale: int,
    palette: dict[str, str],
    rsvg: str | None,
    work: Path,
    svg_out: Path,
    png_out: Path,
) -> tuple[int, int, bool, dict[str, int] | None]:
    """Returns (width, height, custom_name, slice_override) —
    `custom_name` is True when `name` is outside this category's
    documented defaults, so the caller can surface it (manifest + RESULT
    line) rather than silently rendering a look-alike as if it were
    bespoke. `slice_override` carries any FINAL-px slice insets this item
    needs beyond the generic `(radius+stroke)*scale` on every side — only
    a panels `window` needs one (its title bar's own bottom edge, not the
    generic corner radius, must be what protects it from a 9-slice
    vertical stretch) — computed here, in the same place the title bar is
    actually drawn, so the two can never drift apart."""
    surface, ink, accent = palette["surface"], palette["ink"], palette["accent"]
    lw, lh = LOGICAL_SIZE[style][category]
    custom = name not in ITEM_ROLE.get(category, {})
    role = ITEM_ROLE.get(category, {}).get(name) or DEFAULT_ROLE_FALLBACK[category]
    role_hex = palette[role]
    slice_override: dict[str, int] | None = None

    if style == "flat-vector":
        w, h = lw * scale, lh * scale
        r, s = radius * scale, stroke * scale
        if category == "buttons":
            assert state is not None
            fill_rgb = adjust_for_state(hex_to_rgb(role_hex), state)
            svg = build_button_svg(w, h, r, s, rgb_to_hex(fill_rgb), ink)
        elif category == "panels":
            svg = build_panel_svg(w, h, r, s, name, surface, ink, accent)
            if name == "window":
                _, title_bottom = window_title_bar_rows(h, s)
                slice_override = {"top": title_bottom}
        else:  # bars
            svg = build_bar_svg(w, h, r, s, name, ink, accent, scale, BAR_FILL_PAD_LOGICAL[style])
        assert rsvg is not None  # run() already required it for flat-vector
        raster_svg(svg, w, h, rsvg, work, png_out)
        svg_out.write_text(svg, encoding="utf-8")
        return w, h, custom, slice_override

    # pixel
    w, h = lw, lh
    if category == "buttons":
        assert state is not None
        fill_rgb = adjust_for_state(hex_to_rgb(role_hex), state)
        raster_pixel(w, h, radius, stroke, fill_rgb, hex_to_rgb(ink), scale, work, png_out)
    elif category == "panels":
        overlays: list[Overlay] = []
        if name == "window":
            x0, y0, x1, y1 = panel_title_bar_rect(w, h, stroke)
            overlays = [(x0, y0, x1, y1, hex_to_rgb(accent))]
            # Computed here in LOGICAL px (same space as x0..y1 above);
            # scaled to FINAL px for slices.json, same as the overall
            # w*scale/h*scale the caller reports for this item.
            slice_override = {"top": y1 * scale}
        raster_pixel(
            w, h, radius, stroke, hex_to_rgb(surface), hex_to_rgb(ink), scale, work, png_out, overlays
        )
    else:  # bars
        if name == "frame":
            # Unfilled: interior stays fully transparent, only the stroke
            # ring is drawn.
            raster_pixel(w, h, radius, stroke, None, hex_to_rgb(ink), scale, work, png_out)
        elif name == "fill":
            # Inset by the frame's own stroke plus the style's extra pad
            # (0 for pixel — see BAR_FILL_PAD_LOGICAL), no border of its
            # own — never the full-frame stroke ring this used to draw
            # (that bug painted `fill` as an ink-bordered box covering the
            # whole `frame` box with no inset at all).
            pad = stroke + BAR_FILL_PAD_LOGICAL["pixel"]
            raster_pixel_fill_inset(w, h, pad, radius, hex_to_rgb(accent), scale, work, png_out)
        else:
            # A custom bar item name: a plain filled rounded rect, the
            # generic look — never a bespoke frame/fill interpretation.
            raster_pixel(w, h, radius, stroke, hex_to_rgb(role_hex), hex_to_rgb(ink), scale, work, png_out)
    final_w, final_h = w * scale, h * scale
    svg_out.write_text(svg_wrap_raster(png_out, final_w, final_h), encoding="utf-8")
    return final_w, final_h, custom, slice_override


# ── main ──────────────────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ui-draw.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--out", required=True)
    p.add_argument("--contents", required=True)
    p.add_argument("--style", required=True, choices=STYLES)
    p.add_argument("--palette", default=",".join(DEFAULT_PALETTE))
    p.add_argument("--radius", type=int, default=None)
    p.add_argument("--stroke", type=int, default=None)
    p.add_argument("--scale", type=int, default=1)
    p.add_argument("--states", default=",".join(DEFAULT_STATES))
    p.add_argument("--slug", default="kit")
    p.add_argument("--items", default=None)
    return p


def run(argv: list[str]) -> str:
    args = build_arg_parser().parse_args(argv)

    contents = parse_list(args.contents, CONTENTS, "contents")
    slug = validate_slug(args.slug, "--slug")

    palette_parts = [v.strip() for v in args.palette.split(",")]
    if len(palette_parts) != 3:
        die("--palette must list exactly three #rrggbb roles: surface,ink,accent")
    for v in palette_parts:
        hex_to_rgb(v)  # raises on bad hex
    palette = {"surface": palette_parts[0], "ink": palette_parts[1], "accent": palette_parts[2]}

    if not (1 <= args.scale <= 4):
        die(f"--scale must be an integer 1-4, got {args.scale}")

    radius = args.radius if args.radius is not None else DEFAULT_RADIUS[args.style]
    stroke = args.stroke if args.stroke is not None else DEFAULT_STROKE[args.style]
    validate_geometry(args.style, contents, radius, stroke, args.scale)

    # Fail closed, before any work or --out mutation: flat-vector has no
    # safe fallback renderer (see require_rsvg_convert docstring). Checked
    # here rather than lazily per-item so a missing dependency is reported
    # immediately, not after partially rendering a kit into a temp dir.
    rsvg = require_rsvg_convert() if args.style == "flat-vector" else None

    states = parse_list(args.states, ALL_STATES, "states")

    items: dict[str, list[str]]
    if args.items:
        items = load_items_override(Path(args.items), contents)
    else:
        items = {c: list(DEFAULT_ITEMS[c]) for c in contents}

    out_dir = Path(args.out)
    if out_dir.exists():
        if out_dir.is_dir() and any(out_dir.iterdir()):
            die(f"--out already exists and is not empty: {out_dir}")
        if not out_dir.is_dir():
            die(f"--out exists and is not a directory: {out_dir}")

    with tempfile.TemporaryDirectory(prefix="ui-draw-work-") as work_str:
        work = Path(work_str)
        build_root = work / "build"
        build_root.mkdir()

        files: list[dict] = []
        slices: list[dict] = []
        custom_names: list[str] = []

        for category in contents:
            asset_dir = build_root / "assets" / category
            asset_dir.mkdir(parents=True)
            for name in items[category]:
                item_states: list[str | None]
                if category in STATEFUL_CATEGORIES:
                    item_states = list(states)
                else:
                    item_states = [None]
                for state in item_states:
                    stem = f"{slug}_{name}" + (f"_{state}" if state else "")
                    svg_path = asset_dir / f"{stem}.svg"
                    png_path = asset_dir / f"{stem}.png"
                    item_work = work / f"item_{category}_{name}_{state or 'static'}"
                    item_work.mkdir()
                    w, h, custom, slice_override = render_item(
                        category,
                        name,
                        state,
                        args.style,
                        radius,
                        stroke,
                        args.scale,
                        palette,
                        rsvg,
                        item_work,
                        svg_path,
                        png_path,
                    )
                    if custom and f"{category}:{name}" not in custom_names:
                        custom_names.append(f"{category}:{name}")
                    rel_svg = f"assets/{category}/{stem}.svg"
                    rel_png = f"assets/{category}/{stem}.png"
                    files.append(
                        {
                            "category": category,
                            "name": name,
                            "state": state or "static",
                            "custom_name": custom,
                            "svg": rel_svg,
                            "png": rel_png,
                            "width": w,
                            "height": h,
                        }
                    )
                    # validate_geometry already guarantees 2*(radius+stroke)
                    # < min(logical w, h) (and, for panels, that the
                    # generic border plus the window title bar's own
                    # bottom edge still leave a positive band), which
                    # scales linearly, so these insets always satisfy
                    # left+right < width and top+bottom < height — no
                    # clamp needed (a clamp here would silently paper over
                    # geometry that should have been rejected earlier
                    # instead).
                    if (category, name) not in NO_SLICE_ITEMS:
                        border = (radius + stroke) * args.scale
                        top = border
                        if slice_override and "top" in slice_override:
                            # A window's title bar sits inside a FIXED
                            # band that must never stretch vertically —
                            # the generic corner-radius border is not
                            # enough to protect it, so its own bottom edge
                            # (already validated to fit) wins if larger.
                            top = max(top, slice_override["top"])
                        if top + border >= h or 2 * border >= w:
                            die(
                                f"internal: slices for {rel_png} leave no centre band "
                                f"(top={top} bottom={border} height={h}, "
                                f"left=right={border} width={w}) — validate_geometry "
                                "should have rejected this before any rendering"
                            )
                        slices.append(
                            {
                                "file": rel_png,
                                "left": border,
                                "right": border,
                                "top": top,
                                "bottom": border,
                            }
                        )

        manifest = {
            "kit": slug,
            "style": args.style,
            "palette": palette,
            "radius": radius,
            "stroke": stroke,
            "scale": args.scale,
            "states": states,
            "files": files,
        }
        (build_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        (build_root / "slices.json").write_text(
            json.dumps({"slices": slices}, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )

        if out_dir.exists() and out_dir.is_dir() and not any(out_dir.iterdir()):
            out_dir.rmdir()
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(build_root), str(out_dir))

    result = (
        f"RESULT: out={out_dir} style={args.style} contents={','.join(contents)} "
        f"slug={slug} scale={args.scale} files={len(files)} slices={len(slices)}"
    )
    if custom_names:
        # Never silent: a custom name always gets a generic look, and the
        # caller must see that it happened rather than assume bespoke work.
        result += f" custom_names={','.join(custom_names)}"
    return result


def main() -> int:
    try:
        print(run(sys.argv[1:]))
    except UsageError as exc:
        print(f"ui-draw: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
