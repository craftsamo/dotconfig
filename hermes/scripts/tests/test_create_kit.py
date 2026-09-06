"""Behaviour tests for the `create-kit` leaf's renderer
(profiles/image-creator/skills/image-creator-pipeline/create/kit/scripts/ui-draw.py).

Exercised as a subprocess CLI (the way the skill's Procedure calls it) so
that argument parsing, exit codes and stdout are covered exactly as a
worker would see them. Requires ImageMagick (`magick`) on PATH, same as
every other image-creator renderer script.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    HERMES_ROOT
    / "profiles"
    / "image-creator"
    / "skills"
    / "image-creator-pipeline"
    / "create"
    / "kit"
    / "scripts"
    / "ui-draw.py"
)

MAGICK_AVAILABLE = shutil.which("magick") is not None
MAGICK_PATH = shutil.which("magick")
DEFAULT_ACCENT_RGB = (248, 184, 78)  # #f8b84e, the default --palette accent


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def run_with_path_dirs(path_dirs: list[str], *args: str) -> subprocess.CompletedProcess:
    """Like `run`, but with PATH replaced by exactly `path_dirs` — used to
    prove ui-draw's `rsvg-convert` requirement is real (fail closed without
    it) rather than assumed from reading the code."""
    import os

    env = dict(os.environ)
    env["PATH"] = ":".join(path_dirs)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def magick_only_bin_dir(root: Path) -> str:
    """A PATH entry with `magick` on it but deliberately no
    `rsvg-convert` — simulates the machine this dependency check exists
    for, without touching the real PATH."""
    bin_dir = root / "magick-only-bin"
    bin_dir.mkdir(exist_ok=True)
    link = bin_dir / "magick"
    if not link.exists():
        link.symlink_to(MAGICK_PATH)
    return str(bin_dir)


def magick_json(*args: str) -> str:
    proc = subprocess.run(["magick", *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def pixel(png: Path, x: int, y: int) -> str:
    return magick_json(str(png), "-format", f"%[pixel:p{{{x},{y}}}]", "info:")


def channels(png: Path) -> str:
    return magick_json(str(png), "-format", "%[channels]", "info:")


def alpha_at(png: Path, x: int, y: int) -> int:
    """Exact alpha (0-255) at one pixel, via a 1x1 crop + `fx:` — reliable
    regardless of whether ImageMagick decided to store the PNG as
    graya/srgba/etc, unlike parsing `-format '%[pixel:...]'` text."""
    out = magick_json(f"{png}[1x1+{x}+{y}]", "-format", "%[fx:255*a]", "info:")
    return round(float(out))


def rgb_at(png: Path, x: int, y: int) -> tuple[int, int, int]:
    out = magick_json(
        f"{png}[1x1+{x}+{y}]", "-format", "%[fx:255*r] %[fx:255*g] %[fx:255*b]", "info:"
    )
    r, g, b = (round(float(v)) for v in out.split())
    return r, g, b


def accent_column_height(png: Path, x: int, accent: tuple[int, int, int], tol: int = 40) -> int:
    """Scans one pixel-wide column top-to-bottom, skips any leading
    non-matching rows (the outer stroke), then counts the contiguous run
    of rows whose colour is within `tol` of `accent` — i.e. the title
    bar's own pixel HEIGHT at that column, independent of anything else
    in the image. Used to prove a 9-slice expansion never stretches the
    title bar vertically: this count must stay identical before/after."""
    h = dims(png)[1]
    proc = subprocess.run(
        ["magick", f"{png}[1x{h}+{x}+0]", "-depth", "8", "rgba:-"],
        capture_output=True,
        check=True,
    )
    data = proc.stdout
    count = 0
    started = False
    for i in range(0, len(data), 4):
        r, g, b, a = data[i], data[i + 1], data[i + 2], data[i + 3]
        matches = a > 0 and abs(r - accent[0]) <= tol and abs(g - accent[1]) <= tol and abs(b - accent[2]) <= tol
        if matches:
            count += 1
            started = True
        elif started:
            break
    return count


def dims(png: Path) -> tuple[int, int]:
    w, h = magick_json(str(png), "-format", "%w %h", "info:").split()
    return int(w), int(h)


def alpha_bbox(png: Path) -> tuple[int, int, int, int]:
    """The exclusive (x0, y0, x1, y1) bounding box of every non-transparent
    pixel, computed by scanning the raw alpha plane in Python — NOT via
    ImageMagick's `-trim`, which strips whole rows/columns that match the
    corner colour and so silently eats a uniformly-coloured ring shape
    (a bars `frame` at radius 0 touches every edge with one flat colour;
    `-trim` reported it 2px smaller on every side than it actually is)."""
    w, h = dims(png)
    proc = subprocess.run(
        ["magick", str(png), "-alpha", "extract", "-depth", "8", "gray:-"],
        capture_output=True,
        check=True,
    )
    data = proc.stdout
    assert len(data) == w * h, (len(data), w, h)
    xs = [i % w for i, v in enumerate(data) if v > 0]
    ys = [i // w for i, v in enumerate(data) if v > 0]
    if not xs:
        return 0, 0, 0, 0
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def crop(src: Path, x: int, y: int, w: int, h: int, out: Path) -> Path:
    subprocess.run(
        ["magick", str(src), "-crop", f"{w}x{h}+{x}+{y}", "+repage", str(out)], check=True
    )
    return out


def resize_exact(src: Path, w: int, h: int, out: Path) -> Path:
    subprocess.run(["magick", str(src), "-resize", f"{w}x{h}!", str(out)], check=True)
    return out


def pixels_identical(a: Path, b: Path) -> bool:
    """Pixel-content equality, not raw-file-byte equality: two PNGs that
    went through different ImageMagick pipelines (a plain crop vs. a crop
    of a composited canvas) can legitimately differ in compression/encoding
    while every pixel is identical — `magick compare -metric AE` reports
    the count of differing pixels regardless of encoding."""
    proc = subprocess.run(
        ["magick", "compare", "-metric", "AE", str(a), str(b), "null:"],
        capture_output=True,
        text=True,
    )
    # stderr is "<absolute-error-count> (<normalized>)", e.g. "0 (0)" —
    # not a bare "0" — so only the leading token is the pixel count.
    count = proc.stderr.strip().split()[0]
    return count == "0"


def nine_slice_expand(
    png: Path, left: int, right: int, top: int, bottom: int, target_w: int, target_h: int, work: Path
) -> Path:
    """A real (not simulated) 9-slice expansion using the slices.json
    borders: the four corners are copied unstretched, the four edges
    stretched along one axis, the centre stretched both axes — the
    standard engine algorithm. Proves the numbers in slices.json actually
    describe a usable, non-overlapping 9-slice grid (`cw/ch/tcw/tch > 0`
    below would raise otherwise)."""
    w, h = dims(png)
    cw, ch = w - left - right, h - top - bottom
    assert cw > 0 and ch > 0, "slices leave no centre band"
    tcw, tch = target_w - left - right, target_h - top - bottom
    assert tcw > 0 and tch > 0, "target too small for these borders"

    tl = crop(png, 0, 0, left, top, work / "tl.png")
    tr = crop(png, w - right, 0, right, top, work / "tr.png")
    bl = crop(png, 0, h - bottom, left, bottom, work / "bl.png")
    br = crop(png, w - right, h - bottom, right, bottom, work / "br.png")
    top_edge = resize_exact(
        crop(png, left, 0, cw, top, work / "top_raw.png"), tcw, top, work / "top.png"
    )
    bottom_edge = resize_exact(
        crop(png, left, h - bottom, cw, bottom, work / "bottom_raw.png"), tcw, bottom, work / "bottom.png"
    )
    left_edge = resize_exact(
        crop(png, 0, top, left, ch, work / "left_raw.png"), left, tch, work / "left.png"
    )
    right_edge = resize_exact(
        crop(png, w - right, top, right, ch, work / "right_raw.png"), right, tch, work / "right.png"
    )
    center = resize_exact(
        crop(png, left, top, cw, ch, work / "center_raw.png"), tcw, tch, work / "center.png"
    )

    # One `-layers merge` pass, not N sequential composites onto a
    # transparent canvas re-read/re-written each time: writing a fully
    # transparent `canvas:none` as its own PNG lets ImageMagick infer a
    # Grayscale colour type (every channel is 0), and every subsequent
    # composite against that mistyped file silently collapsed the tiles'
    # colour to grayscale too — `-define png:color-type=6` on the single
    # merged output below forces true RGBA and avoids that entirely.
    canvas = work / "expanded.png"
    tiles = [
        (tl, 0, 0),
        (top_edge, left, 0),
        (tr, target_w - right, 0),
        (left_edge, 0, top),
        (center, left, top),
        (right_edge, target_w - right, top),
        (bl, 0, target_h - bottom),
        (bottom_edge, left, target_h - bottom),
        (br, target_w - right, target_h - bottom),
    ]
    cmd = ["magick", "-size", f"{target_w}x{target_h}", "xc:none"]
    for tile, x, y in tiles:
        # `-page` must be SCOPED to its own image with parentheses:
        # `( tile.png -page +x+y )`. Neither `-page +x+y tile.png` nor
        # `tile.png -page +x+y` (both tried first) positions the tile —
        # unscoped, `-layers merge` read every page setting but applied
        # only the LAST one to every image (confirmed with a 2-square
        # repro: both squares landed at the final page offset, last one
        # painted over the first), which is what let a "corner" composite
        # land at the wrong offset and left transparent corners painted
        # over with an unrelated tile's colour instead of staying empty.
        cmd += ["(", str(tile), "-page", f"+{x}+{y}", ")"]
    cmd += [
        "-background",
        "none",
        "-layers",
        "merge",
        "+repage",
        "-define",
        "png:color-type=6",
        "-strip",
        str(canvas),
    ]
    subprocess.run(cmd, check=True)
    return canvas


@unittest.skipUnless(MAGICK_AVAILABLE, "ImageMagick (magick) not on PATH")
class CreateKitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def out(self, name: str) -> Path:
        return self.root / name

    # ── full fixture invocation, both styles, every state ────────────

    def test_flat_vector_all_contents_all_states(self) -> None:
        out = self.out("flat-full")
        proc = run(
            "--out",
            str(out),
            "--contents",
            "buttons,panels,bars",
            "--style",
            "flat-vector",
            "--states",
            "normal,pressed,hover,disabled",
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(proc.stdout.startswith("RESULT:"), proc.stdout)

        manifest = json.loads((out / "manifest.json").read_text())
        # 2 button items x 4 states + 2 panel items + 2 bar items = 12
        self.assertEqual(12, len(manifest["files"]))
        for entry in manifest["files"]:
            svg = out / entry["svg"]
            png = out / entry["png"]
            self.assertTrue(svg.is_file(), svg)
            self.assertTrue(png.is_file(), png)
            dims = magick_json(str(png), "-format", "%wx%h", "info:")
            self.assertEqual(f"{entry['width']}x{entry['height']}", dims)

        button_states = {
            e["state"] for e in manifest["files"] if e["category"] == "buttons"
        }
        self.assertEqual({"normal", "pressed", "hover", "disabled"}, button_states)
        panel_states = {e["state"] for e in manifest["files"] if e["category"] == "panels"}
        bar_states = {e["state"] for e in manifest["files"] if e["category"] == "bars"}
        self.assertEqual({"static"}, panel_states)
        self.assertEqual({"static"}, bar_states)

    def test_pixel_all_contents_default_states(self) -> None:
        out = self.out("pixel-full")
        proc = run(
            "--out", str(out), "--contents", "buttons,panels,bars", "--style", "pixel", "--scale", "3"
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        # 2 button items x 2 default states + 2 panels + 2 bars = 8
        self.assertEqual(8, len(manifest["files"]))
        for entry in manifest["files"]:
            png = out / entry["png"]
            dims = magick_json(str(png), "-format", "%wx%h", "info:")
            self.assertEqual(f"{entry['width']}x{entry['height']}", dims)
        # pixel logical buttons 48x16 at scale 3 -> 144x48
        button = next(e for e in manifest["files"] if e["category"] == "buttons" and e["state"] == "normal")
        self.assertEqual([144, 48], [button["width"], button["height"]])

    # ── stable bytes (determinism) ────────────────────────────────────

    def test_reruns_produce_identical_bytes(self) -> None:
        out1 = self.out("det1")
        out2 = self.out("det2")
        for out in (out1, out2):
            proc = run("--out", str(out), "--contents", "buttons,panels,bars", "--style", "flat-vector")
            self.assertEqual(0, proc.returncode, proc.stderr)

        rel_files = sorted(p.relative_to(out1).as_posix() for p in out1.rglob("*") if p.is_file())
        rel_files2 = sorted(p.relative_to(out2).as_posix() for p in out2.rglob("*") if p.is_file())
        self.assertEqual(rel_files, rel_files2)
        for rel in rel_files:
            self.assertEqual(
                (out1 / rel).read_bytes(), (out2 / rel).read_bytes(), f"bytes differ for {rel}"
            )

    def test_pixel_reruns_produce_identical_bytes(self) -> None:
        out1 = self.out("pxdet1")
        out2 = self.out("pxdet2")
        for out in (out1, out2):
            proc = run("--out", str(out), "--contents", "bars", "--style", "pixel", "--scale", "2")
            self.assertEqual(0, proc.returncode, proc.stderr)
        for rel in ("assets/bars/kit_frame.png", "assets/bars/kit_fill.png", "manifest.json", "slices.json"):
            self.assertEqual((out1 / rel).read_bytes(), (out2 / rel).read_bytes(), rel)

    # ── PNG exact alpha for pixel ──────────────────────────────────────

    def test_pixel_rounded_corner_is_fully_transparent(self) -> None:
        out = self.out("pixel-alpha")
        proc = run(
            "--out",
            str(out),
            "--contents",
            "buttons",
            "--style",
            "pixel",
            "--radius",
            "4",
            "--stroke",
            "1",
            "--scale",
            "2",
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        png = out / "assets/buttons/kit_primary_normal.png"
        self.assertIn("a", channels(png))  # alpha channel present
        corner = pixel(png, 0, 0)
        self.assertIn("0)", corner.replace(" ", ""), corner)  # alpha component is 0
        centre = pixel(png, 48, 16)
        self.assertNotIn(",0)", centre.replace(" ", ""), centre)  # opaque interior

    def test_pixel_unfilled_frame_interior_is_transparent(self) -> None:
        out = self.out("pixel-frame")
        proc = run("--out", str(out), "--contents", "bars", "--style", "pixel", "--scale", "1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        png = out / "assets/bars/kit_frame.png"
        centre = pixel(png, 32, 4)
        self.assertIn("0)", centre.replace(" ", ""), centre)

    def test_flat_vector_corner_is_fully_transparent(self) -> None:
        out = self.out("flat-alpha")
        proc = run("--out", str(out), "--contents", "panels", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        png = out / "assets/panels/kit_window.png"
        corner = pixel(png, 0, 0)
        self.assertIn("0)", corner.replace(" ", ""), corner)

    # ── output dims ─────────────────────────────────────────────────────

    def test_logical_sizes_match_documented_defaults(self) -> None:
        out = self.out("dims")
        proc = run("--out", str(out), "--contents", "buttons,panels,bars", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        expected = {"buttons": (384, 128), "panels": (512, 384), "bars": (512, 64)}
        for entry in manifest["files"]:
            w, h = expected[entry["category"]]
            self.assertEqual([w, h], [entry["width"], entry["height"]])

    def test_scale_multiplies_flat_vector_canvas(self) -> None:
        out = self.out("scaled")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--scale", "2")
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        entry = manifest["files"][0]
        self.assertEqual([768, 256], [entry["width"], entry["height"]])

    # ── slices bounds and scaled corner consistency ─────────────────────

    def test_slices_bounds_fit_inside_every_image(self) -> None:
        out = self.out("slices")
        proc = run(
            "--out", str(out), "--contents", "buttons,panels,bars", "--style", "flat-vector", "--scale", "2"
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        slices = json.loads((out / "slices.json").read_text())["slices"]
        by_file = {e["png"]: e for e in manifest["files"]}
        self.assertGreater(len(slices), 0)
        for s in slices:
            entry = by_file[s["file"]]
            self.assertLess(s["left"] + s["right"], entry["width"])
            self.assertLess(s["top"] + s["bottom"], entry["height"])
        # a bar's flat `fill` must never be reported as 9-sliceable
        self.assertNotIn("assets/bars/kit_fill.png", {s["file"] for s in slices})
        self.assertIn("assets/bars/kit_frame.png", {s["file"] for s in slices})

    def test_slices_scale_with_scale_flag(self) -> None:
        # `tooltip` (not `window`): a purely generic border with no
        # title-bar override, so it is expected to double exactly. `window`
        # has its own dedicated scaling tests below — its top inset is
        # driven by the title-bar formula, which does NOT always double
        # cleanly across scales (see test_window_title_bar_top_inset_*).
        out1 = self.out("slices-s1")
        out2 = self.out("slices-s2")
        run("--out", str(out1), "--contents", "panels", "--style", "flat-vector", "--scale", "1")
        run("--out", str(out2), "--contents", "panels", "--style", "flat-vector", "--scale", "2")
        slices1 = {s["file"]: s for s in json.loads((out1 / "slices.json").read_text())["slices"]}
        slices2 = {s["file"]: s for s in json.loads((out2 / "slices.json").read_text())["slices"]}
        s1 = slices1["assets/panels/kit_tooltip.png"]
        s2 = slices2["assets/panels/kit_tooltip.png"]
        self.assertEqual(s1["left"] * 2, s2["left"])
        self.assertEqual(s1["top"] * 2, s2["top"])

    # ── bad inputs: path traversal ───────────────────────────────────────

    def test_slug_path_traversal_is_rejected(self) -> None:
        out = self.out("traversal")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--slug", "../evil")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("slug", proc.stderr)
        self.assertFalse(out.exists())

    def test_slug_with_slash_is_rejected(self) -> None:
        out = self.out("traversal2")
        proc = run(
            "--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--slug", "a/b"
        )
        self.assertNotEqual(0, proc.returncode)

    def test_items_override_name_path_traversal_is_rejected(self) -> None:
        out = self.out("traversal-items")
        items = self.root / "items.json"
        items.write_text(json.dumps({"buttons": ["../evil"]}), encoding="utf-8")
        proc = run(
            "--out",
            str(out),
            "--contents",
            "buttons",
            "--style",
            "flat-vector",
            "--items",
            str(items),
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(out.exists())

    # ── unsupported category: early failure, no partial output ─────────

    def test_unsupported_category_fails_before_writing_anything(self) -> None:
        out = self.out("badcat")
        proc = run("--out", str(out), "--contents", "buttons,widgets", "--style", "flat-vector")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("unsupported contents", proc.stderr)
        self.assertFalse(out.exists())

    def test_unsupported_style_fails(self) -> None:
        out = self.out("badstyle")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "isometric")
        self.assertNotEqual(0, proc.returncode)

    # ── other invalid inputs ─────────────────────────────────────────────

    def test_radius_too_large_for_smallest_category_is_rejected(self) -> None:
        out = self.out("badradius")
        proc = run(
            "--out", str(out), "--contents", "bars", "--style", "pixel", "--radius", "10"
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("radius", proc.stderr)

    def test_scale_out_of_range_is_rejected(self) -> None:
        out = self.out("badscale")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--scale", "5")
        self.assertNotEqual(0, proc.returncode)

    def test_bad_palette_hex_is_rejected(self) -> None:
        out = self.out("badpalette")
        proc = run(
            "--out",
            str(out),
            "--contents",
            "buttons",
            "--style",
            "flat-vector",
            "--palette",
            "red,blue,green",
        )
        self.assertNotEqual(0, proc.returncode)

    def test_nonempty_existing_out_dir_is_rejected(self) -> None:
        out = self.out("nonempty")
        out.mkdir()
        (out / "stale.txt").write_text("x", encoding="utf-8")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "flat-vector")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("not empty", proc.stderr)
        # the stale file must survive untouched
        self.assertTrue((out / "stale.txt").is_file())

    def test_items_override_replaces_default_names(self) -> None:
        out = self.out("items")
        items = self.root / "items.json"
        items.write_text(json.dumps({"buttons": ["primary", "cancel"]}), encoding="utf-8")
        proc = run(
            "--out",
            str(out),
            "--contents",
            "buttons",
            "--style",
            "flat-vector",
            "--states",
            "normal",
            "--items",
            str(items),
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        names = {e["name"] for e in json.loads((out / "manifest.json").read_text())["files"]}
        self.assertEqual({"primary", "cancel"}, names)

    # ── (2) geometry that leaves no central band is rejected, not clamped ──

    def test_maximum_accepted_radius_at_default_stroke(self) -> None:
        # bars flat-vector: logical 512x64, m=64, default stroke=2.
        # band = m - 2*(radius+stroke) > 0  =>  radius <= 29 at stroke 2.
        out_ok = self.out("radius-ok")
        proc = run(
            "--out", str(out_ok), "--contents", "bars", "--style", "flat-vector", "--radius", "29"
        )
        self.assertEqual(0, proc.returncode, proc.stderr)

        out_bad = self.out("radius-bad")
        proc = run(
            "--out", str(out_bad), "--contents", "bars", "--style", "flat-vector", "--radius", "30"
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("central band", proc.stderr)
        self.assertFalse(out_bad.exists())

    def test_slices_never_clamped_to_a_degenerate_zero_band(self) -> None:
        # Every accepted geometry must leave left+right < width strictly —
        # never equal (a zero-width centre is a rejection, not a value).
        out = self.out("slices-strict")
        proc = run(
            "--out", str(out), "--contents", "buttons,panels,bars", "--style", "flat-vector", "--radius", "29"
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        by_file = {e["png"]: e for e in manifest["files"]}
        slices = json.loads((out / "slices.json").read_text())["slices"]
        for s in slices:
            entry = by_file[s["file"]]
            self.assertLess(s["left"] + s["right"], entry["width"])
            self.assertLess(s["top"] + s["bottom"], entry["height"])

    def test_bars_stroke_leaving_no_room_for_fill_inset_is_rejected(self) -> None:
        # flat-vector bars: logical 512x64, m=64. BAR_FILL_PAD_LOGICAL is 2
        # for this style, so the fill-inset check (stroke + 2) is STRICTER
        # than the plain central-band check (radius + stroke) whenever
        # radius is small: radius=0, stroke=30 passes the general band
        # check (2*30=60 < 64) but fails the fill-inset one
        # (2*(30+2)=64, not < 64) — must be rejected up front, not
        # silently degenerate at render time.
        # (pixel's BAR_FILL_PAD_LOGICAL is 0 — see finding 2 — so for
        # pixel this check is now always implied by the general band
        # check and cannot fire independently; that is by design, not a
        # gap in coverage.)
        out = self.out("bars-fill-pad-bad")
        proc = run(
            "--out", str(out), "--contents", "bars", "--style", "flat-vector", "--radius", "0", "--stroke", "30"
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("inset fill", proc.stderr)
        self.assertFalse(out.exists())

    def test_radius_stroke_must_be_non_negative(self) -> None:
        out = self.out("neg-radius")
        proc = run("--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--radius", "-1")
        self.assertNotEqual(0, proc.returncode)

    # ── (3) bars fill is inset, never a full-frame stroke ring ─────────────

    def test_bars_fill_never_touches_frames_border_flat_vector_scale1(self) -> None:
        out = self.out("bars-inset-flat-1")
        proc = run("--out", str(out), "--contents", "bars", "--style", "flat-vector", "--scale", "1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        frame = out / "assets/bars/kit_frame.png"
        fill = out / "assets/bars/kit_fill.png"
        # frame is a ring: touches every edge (radius=12/stroke=2 default
        # still reaches x=0 along the straight edges, away from corners).
        fx0, fy0, fx1, fy1 = alpha_bbox(frame)
        self.assertEqual((0, 0), (fx0, fy0))
        w, h = dims(frame)
        self.assertEqual((w, h), (fx1, fy1))
        # fill must be strictly inside frame's box: pad = stroke + 2 = 4.
        gx0, gy0, gx1, gy1 = alpha_bbox(fill)
        self.assertEqual((4, 4), (gx0, gy0))
        self.assertEqual((w - 4, h - 4), (gx1, gy1))
        # the ring between the frame's stroke and the fill's outer edge is
        # transparent in BOTH images — proof of an actual inset, not an
        # overlapping stroke-ring-then-fill paint order.
        self.assertEqual(0, alpha_at(frame, 3, h // 2))
        self.assertEqual(0, alpha_at(fill, 3, h // 2))

    def test_bars_fill_inset_scales_with_scale_flag_flat_vector(self) -> None:
        out = self.out("bars-inset-flat-2")
        proc = run("--out", str(out), "--contents", "bars", "--style", "flat-vector", "--scale", "2")
        self.assertEqual(0, proc.returncode, proc.stderr)
        fill = out / "assets/bars/kit_fill.png"
        w, h = dims(fill)
        gx0, gy0, gx1, gy1 = alpha_bbox(fill)
        # pad = (stroke + 2) * scale = (2 + 2) * 2 = 8 — the +2 constant
        # must scale together with everything else on the SVG canvas.
        self.assertEqual((8, 8), (gx0, gy0))
        self.assertEqual((w - 8, h - 8), (gx1, gy1))

    def test_bars_fill_never_touches_frames_border_pixel_scale1(self) -> None:
        # BAR_FILL_PAD_LOGICAL["pixel"] is 0 (finding 2): the fill's inset
        # equals the frame's own stroke exactly, filling the WHOLE hollow
        # interior with no extra gap — a gap would waste a bar's already
        # tiny 8px logical height (a 2px extra pad, the old flat-shared
        # constant, left only 25% of the height as visible fill).
        out = self.out("bars-inset-px-1")
        proc = run("--out", str(out), "--contents", "bars", "--style", "pixel", "--scale", "1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        frame = out / "assets/bars/kit_frame.png"
        fill = out / "assets/bars/kit_fill.png"
        w, h = dims(frame)
        fx0, fy0, fx1, fy1 = alpha_bbox(frame)
        self.assertEqual((0, 0, w, h), (fx0, fy0, fx1, fy1))
        # pad = stroke(1) + BAR_FILL_PAD_LOGICAL["pixel"](0) = 1, logical.
        gx0, gy0, gx1, gy1 = alpha_bbox(fill)
        self.assertEqual((1, 1), (gx0, gy0))
        self.assertEqual((w - 1, h - 1), (gx1, gy1))
        # fill height (h - 2*pad) is 6 of 8 logical px: well over half the
        # canvas — the whole point of dropping the extra pad for pixel.
        self.assertGreaterEqual((gy1 - gy0) / h, 0.5)
        # frame's OWN interior is still transparent at x=1 (it never draws
        # a fill) — but fill itself is now OPAQUE at x=1: adjacent to
        # frame's stroke, not separated from it by a gap.
        self.assertEqual(0, alpha_at(frame, 1, h // 2))
        self.assertEqual(255, alpha_at(fill, 1, h // 2))

    def test_bars_fill_inset_scales_with_scale_flag_pixel(self) -> None:
        out = self.out("bars-inset-px-2")
        proc = run("--out", str(out), "--contents", "bars", "--style", "pixel", "--scale", "2")
        self.assertEqual(0, proc.returncode, proc.stderr)
        fill = out / "assets/bars/kit_fill.png"
        w, h = dims(fill)
        gx0, gy0, gx1, gy1 = alpha_bbox(fill)
        # a pixel-style pad is logical (1) then the WHOLE raster is
        # upscaled nearest-neighbour afterward, so pad also lands at 1*2=2.
        self.assertEqual((2, 2), (gx0, gy0))
        self.assertEqual((w - 2, h - 2), (gx1, gy1))
        self.assertGreaterEqual((gy1 - gy0) / h, 0.5)

    def test_bars_frame_and_fill_share_outer_box_both_styles(self) -> None:
        for style, scale in (("flat-vector", 1), ("flat-vector", 2), ("pixel", 1), ("pixel", 2)):
            with self.subTest(style=style, scale=scale):
                out = self.out(f"bars-box-{style}-{scale}")
                proc = run(
                    "--out", str(out), "--contents", "bars", "--style", style, "--scale", str(scale)
                )
                self.assertEqual(0, proc.returncode, proc.stderr)
                manifest = json.loads((out / "manifest.json").read_text())
                by_name = {e["name"]: e for e in manifest["files"]}
                self.assertEqual(
                    (by_name["frame"]["width"], by_name["frame"]["height"]),
                    (by_name["fill"]["width"], by_name["fill"]["height"]),
                )

    # ── (4) pixel panels: `window` gets a title bar, `tooltip` does not ───

    def test_pixel_window_and_tooltip_are_not_identical(self) -> None:
        out = self.out("pixel-panels")
        proc = run("--out", str(out), "--contents", "panels", "--style", "pixel", "--scale", "2")
        self.assertEqual(0, proc.returncode, proc.stderr)
        window = (out / "assets/panels/kit_window.png").read_bytes()
        tooltip = (out / "assets/panels/kit_tooltip.png").read_bytes()
        self.assertNotEqual(window, tooltip)

    def test_pixel_window_title_bar_matches_flat_vector_placement(self) -> None:
        out = self.out("pixel-window-bar")
        proc = run("--out", str(out), "--contents", "panels", "--style", "pixel", "--scale", "1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        window = out / "assets/panels/kit_window.png"
        tooltip = out / "assets/panels/kit_tooltip.png"
        # logical panels 96x64, default stroke=0 (pixel default radius/
        # stroke are 0/1) -> panel_title_bar_rect(96, 64, 1) = (1, 1, 95, 9)
        px, py = 10, 4
        window_pixel = magick_json(str(window), "-format", f"%[pixel:p{{{px},{py}}}]", "info:")
        tooltip_pixel = magick_json(str(tooltip), "-format", f"%[pixel:p{{{px},{py}}}]", "info:")
        self.assertNotEqual(window_pixel, tooltip_pixel)

    def test_flat_vector_window_and_tooltip_are_not_identical(self) -> None:
        out = self.out("flat-panels")
        proc = run("--out", str(out), "--contents", "panels", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        window = (out / "assets/panels/kit_window.svg").read_text()
        tooltip = (out / "assets/panels/kit_tooltip.svg").read_text()
        self.assertNotEqual(window, tooltip)

    # ── (finding 1) a window's title bar must survive a 9-slice stretch ────
    # (the bug: slices.json used the generic `(radius+stroke)*scale` top
    # inset for EVERY panel item, including `window` — but the title bar's
    # own bottom edge sits well below that generic radius/stroke corner, so
    # a 9-slice engine's "top" tile (the only band never stretched
    # vertically) did not cover the whole bar, and stretching the panel
    # taller stretched the title bar's height right along with it.)

    def test_window_geometry_that_leaves_no_room_under_title_bar_is_rejected(self) -> None:
        # Both cases pass the plain central-band check (2*(radius+stroke)
        # < min(w,h)) — proving this is a DISTINCT preflight check, not a
        # restatement of the existing one.
        cases = [
            ("flat-vector", 0, 170),  # logical panels 512x384: 2*170=340 < 384
            ("pixel", 0, 30),  # logical panels 96x64: 2*30=60 < 64
        ]
        for style, radius, stroke in cases:
            with self.subTest(style=style):
                out = self.out(f"window-bad-{style}")
                proc = run(
                    "--out", str(out), "--contents", "panels", "--style", style,
                    "--radius", str(radius), "--stroke", str(stroke),
                )
                self.assertNotEqual(0, proc.returncode)
                self.assertIn("title bar", proc.stderr)
                self.assertFalse(out.exists())

    def test_window_title_bar_height_survives_nine_slice_expansion(self) -> None:
        for style in ("flat-vector", "pixel"):
            for gen_scale in (1, 2):
                out = self.out(f"window-titlebar-{style}-{gen_scale}")
                proc = run(
                    "--out", str(out), "--contents", "panels", "--style", style,
                    "--scale", str(gen_scale),
                )
                self.assertEqual(0, proc.returncode, proc.stderr)
                manifest = json.loads((out / "manifest.json").read_text())
                slices = {s["file"]: s for s in json.loads((out / "slices.json").read_text())["slices"]}
                entry = next(e for e in manifest["files"] if e["name"] == "window")
                png = out / entry["png"]
                s = slices[entry["png"]]
                w, h = entry["width"], entry["height"]

                # The slice top must clear the title bar's own bottom edge,
                # not just the generic corner inset.
                self.assertGreaterEqual(s["top"], (0 + 0))  # sanity: non-negative
                original_height = accent_column_height(png, w // 2, DEFAULT_ACCENT_RGB)
                self.assertGreater(original_height, 0, "title bar not found in the original render")

                for factor in (2, 4):
                    with self.subTest(style=style, gen_scale=gen_scale, factor=factor):
                        work = self.root / f"ns-{style}-{gen_scale}-{factor}"
                        work.mkdir()
                        target_w, target_h = w * factor, h * factor
                        expanded = nine_slice_expand(
                            png, s["left"], s["right"], s["top"], s["bottom"], target_w, target_h, work
                        )
                        self.assertEqual((target_w, target_h), dims(expanded))

                        # Corners: still exactly preserved (the existing
                        # contract), not just the title bar.
                        left, top = s["left"], s["top"]
                        orig_tl = crop(png, 0, 0, left, top, work / "orig_tl.png")
                        exp_tl = crop(expanded, 0, 0, left, top, work / "exp_tl.png")
                        self.assertTrue(pixels_identical(orig_tl, exp_tl))

                        # The title bar's own pixel HEIGHT (vertical extent
                        # of accent colour) must be IDENTICAL after the
                        # expansion — this is the actual regression this
                        # finding is about, not just "corners are fine".
                        expanded_height = accent_column_height(
                            expanded, target_w // 2, DEFAULT_ACCENT_RGB
                        )
                        self.assertEqual(
                            original_height,
                            expanded_height,
                            f"title bar stretched vertically at {factor}x ({style}, scale={gen_scale})",
                        )

    # ── (5) a custom `--items` name is generic, and never silent about it ──

    def test_custom_item_name_is_flagged_generic_in_manifest(self) -> None:
        out = self.out("custom-name")
        items = self.root / "items.json"
        items.write_text(json.dumps({"buttons": ["primary", "cancel"]}), encoding="utf-8")
        proc = run(
            "--out", str(out), "--contents", "buttons", "--style", "flat-vector", "--items", str(items)
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("custom_names=buttons:cancel", proc.stdout)
        by_name = {e["name"]: e for e in json.loads((out / "manifest.json").read_text())["files"]}
        self.assertFalse(by_name["primary"]["custom_name"])
        self.assertTrue(by_name["cancel"]["custom_name"])

    def test_default_item_names_are_never_flagged_custom(self) -> None:
        out = self.out("no-custom")
        proc = run("--out", str(out), "--contents", "buttons,panels,bars", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("custom_names=", proc.stdout)
        for entry in json.loads((out / "manifest.json").read_text())["files"]:
            self.assertFalse(entry["custom_name"], entry)

    def test_custom_bar_item_gets_generic_filled_look_not_frame_or_fill_semantics(self) -> None:
        out = self.out("custom-bar")
        items = self.root / "items.json"
        items.write_text(json.dumps({"bars": ["frame", "fill", "segment"]}), encoding="utf-8")
        proc = run(
            "--out", str(out), "--contents", "bars", "--style", "flat-vector", "--items", str(items)
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        segment = out / "assets/bars/kit_segment.png"
        # a custom bar item is a plain filled rounded rect over the WHOLE
        # box (the generic look), not inset like `fill` and not hollow
        # like `frame` — its own bbox should span the full canvas.
        w, h = dims(segment)
        self.assertEqual((0, 0, w, h), alpha_bbox(segment))
        by_name = {e["name"]: e for e in json.loads((out / "manifest.json").read_text())["files"]}
        self.assertTrue(by_name["segment"]["custom_name"])

    # ── (6) the promised 9-slice contract is proven, not just asserted ────

    def test_nine_slice_expansion_preserves_corners_flat_vector_window(self) -> None:
        out = self.out("nineslice-flat")
        proc = run("--out", str(out), "--contents", "panels", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        slices = {s["file"]: s for s in json.loads((out / "slices.json").read_text())["slices"]}
        entry = next(e for e in manifest["files"] if e["name"] == "window")
        png = out / entry["png"]
        s = slices[entry["png"]]
        work = self.root / "nineslice-flat-work"
        work.mkdir()
        expanded = nine_slice_expand(
            png, s["left"], s["right"], s["top"], s["bottom"], entry["width"] * 2, entry["height"] * 2, work
        )
        ew, eh = dims(expanded)
        self.assertEqual((entry["width"] * 2, entry["height"] * 2), (ew, eh))
        # the corner crop of the EXPANDED image must be pixel-identical to
        # the corner crop of the ORIGINAL — the whole point of a correct
        # 9-slice border is that corners are copied, never stretched.
        # (Pixel content, not raw file bytes: the expanded PNG went through
        # an extra composite pipeline that can re-encode identical pixels
        # with different PNG compression.)
        left, top = s["left"], s["top"]
        orig_tl = crop(png, 0, 0, left, top, work / "orig_tl.png")
        exp_tl = crop(expanded, 0, 0, left, top, work / "exp_tl.png")
        self.assertTrue(pixels_identical(orig_tl, exp_tl))

    def test_nine_slice_expansion_preserves_corners_pixel_button(self) -> None:
        out = self.out("nineslice-pixel")
        proc = run(
            "--out", str(out), "--contents", "buttons", "--style", "pixel", "--radius", "4",
            "--stroke", "1", "--scale", "2", "--states", "normal",
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        manifest = json.loads((out / "manifest.json").read_text())
        slices = {s["file"]: s for s in json.loads((out / "slices.json").read_text())["slices"]}
        entry = next(e for e in manifest["files"] if e["name"] == "primary")
        png = out / entry["png"]
        s = slices[entry["png"]]
        work = self.root / "nineslice-pixel-work"
        work.mkdir()
        expanded = nine_slice_expand(
            png, s["left"], s["right"], s["top"], s["bottom"], entry["width"] * 2, entry["height"] * 2, work
        )
        left, top, right, bottom = s["left"], s["top"], s["right"], s["bottom"]
        w, h = entry["width"], entry["height"]
        for name, ox, oy, ex, ey, bw, bh in (
            ("tl", 0, 0, 0, 0, left, top),
            ("br", w - right, h - bottom, entry["width"] * 2 - right, entry["height"] * 2 - bottom, right, bottom),
        ):
            orig = crop(png, ox, oy, bw, bh, work / f"o_{name}.png")
            exp = crop(expanded, ex, ey, bw, bh, work / f"e_{name}.png")
            self.assertTrue(pixels_identical(orig, exp), name)

    # ── regression guard: a frame's border must actually be visible ────────
    # (the bug this catches: ImageMagick's built-in SVG delegate silently
    # rendered a `fill="none"` stroked rect fully transparent — the whole
    # `frame` item disappeared while every check that only sampled the
    # already-transparent interior kept passing.)

    def test_flat_vector_bars_frame_border_is_opaque(self) -> None:
        out = self.out("frame-visible")
        proc = run("--out", str(out), "--contents", "bars", "--style", "flat-vector")
        self.assertEqual(0, proc.returncode, proc.stderr)
        frame = out / "assets/bars/kit_frame.png"
        w, h = dims(frame)
        self.assertEqual(255, alpha_at(frame, 1, h // 2))
        self.assertEqual(0, alpha_at(frame, w // 2, h // 2))

    # ── flat-vector fails closed without rsvg-convert; pixel does not ────
    # (no silently-broken fallback: ImageMagick's own SVG delegate cannot
    # be trusted for the unfilled shapes this style draws, so a missing
    # `rsvg-convert` must stop the run, never quietly degrade.)

    def test_flat_vector_refuses_to_run_without_rsvg_convert(self) -> None:
        out = self.out("no-rsvg-flat")
        bin_dir = magick_only_bin_dir(self.root)
        proc = run_with_path_dirs(
            [bin_dir], "--out", str(out), "--contents", "buttons", "--style", "flat-vector"
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("rsvg-convert", proc.stderr)
        self.assertIn("librsvg", proc.stderr)
        self.assertIn("install.sh --deps", proc.stderr)
        self.assertFalse(out.exists())

    def test_pixel_runs_fine_without_rsvg_convert(self) -> None:
        out = self.out("no-rsvg-pixel")
        bin_dir = magick_only_bin_dir(self.root)
        proc = run_with_path_dirs(
            [bin_dir], "--out", str(out), "--contents", "buttons,panels,bars", "--style", "pixel"
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((out / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
