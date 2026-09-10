"""Tests for image-creator's kit-images.py (fit / palette / atlas / measure).

Runs the script as a subprocess, exactly how a skill invokes it, and reaches
into ImageMagick with the same idiom the sibling *-fit.sh / *-measure.sh
scripts use. Skipped entirely when `magick` is not on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    HERMES_ROOT
    / "profiles"
    / "image-creator"
    / "skills"
    / "image-creator-pipeline"
    / "scripts"
    / "kit-images.py"
)

MAGICK = shutil.which("magick")


def magick(*args: str) -> None:
    subprocess.run(["magick", *args], check=True, capture_output=True, text=True)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def rgb_at(path: Path, x: int, y: int) -> tuple[float, float, float]:
    """The actual (r, g, b) at one pixel, each in [0, 1] — used to catch a
    remap that silently whitens colour while still passing a mere
    unique-colour-COUNT check (white is "one distinct colour" too)."""
    out = subprocess.run(
        [
            "magick", str(path), "-format",
            f"%[fx:p{{{x},{y}}}.r] %[fx:p{{{x},{y}}}.g] %[fx:p{{{x},{y}}}.b]",
            "info:",
        ],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    return tuple(float(v) for v in out)


def make_hollow_frame(out: Path, size: int = 100, hole: str = "20,20 79,79") -> None:
    """An opaque ring that touches every canvas edge/corner, with a
    transparent rectangular hole punched in the middle — the shape a
    colour `-trim` mis-reads as just its interior hole."""
    magick(
        "-size", f"{size}x{size}", "xc:#663311",
        "(", "-size", f"{size}x{size}", "xc:white", "-fill", "black",
        "-draw", f"rectangle {hole}", ")",
        "-alpha", "off", "-compose", "CopyOpacity", "-composite", str(out),
    )


@unittest.skipUnless(MAGICK, "ImageMagick (magick) not found")
class KitImagesTest(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def path(self, name: str) -> Path:
        return self.root / name

    # ------------------------------------------------------------- fit ---

    def test_rectangular_containment_and_alpha(self) -> None:
        src = self.path("src.png")
        magick(
            "-size", "300x200", "xc:#3355ff", "-fill", "#ff0000",
            "-draw", "circle 150,100 150,50", str(src),
        )
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "400x150")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("RESULT:", result.stdout)
        magick(str(out), "-format", "%w %h", "info:")
        proc = subprocess.run(
            ["magick", "identify", "-format", "%w %h", str(out)],
            check=True, capture_output=True, text=True,
        )
        w, h = proc.stdout.split()
        self.assertEqual((400, 150), (int(w), int(h)))
        # aspect-preserving contain: the source was wider-than-tall; the fit
        # must have left transparent margin on the top/bottom or sides, i.e.
        # the corners must stay transparent (no crop/stretch to fill).
        corner = subprocess.run(
            ["magick", str(out), "-alpha", "extract", "-format", "%[fx:p{0,0}]", "info:"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual("0", corner)

    def test_already_transparent_interior_preserved(self) -> None:
        # Opaque corners, but a transparent hole punched in the middle: auto
        # must recognize this as already cut out and skip flood-filling the
        # (opaque, non-background) corners away.
        src = self.path("donut.png")
        magick(
            "-size", "200x200", "xc:#00ff00",
            "(", "-size", "200x200", "xc:black", "-fill", "white",
            "-draw", "circle 100,100 100,40", "-negate", ")",
            "-alpha", "off", "-compose", "CopyOpacity", "-composite", str(src),
        )
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "256x256")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("cutout=no", result.stdout)

    def test_cutout_no_reproduces_hollow_frame_exactly(self) -> None:
        # Regression: a colour `-trim` samples the corner as "background"
        # and, for a frame whose opaque ring touches every corner, crops
        # down to just the transparent interior hole — losing the frame.
        # --cutout no at the same canvas size + zero pad must reproduce
        # the source pixel-for-pixel (alpha-only bbox = the full canvas).
        src = self.path("frame.png")
        make_hollow_frame(src, size=100)
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "100x100",
                     "--pad", "0", "--cutout", "no")
        self.assertEqual(0, result.returncode, result.stderr)
        diff = subprocess.run(
            ["magick", "compare", "-metric", "AE", str(out), str(src), "null:"],
            capture_output=True, text=True,
        )
        self.assertEqual("0", diff.stderr.strip().split()[0])

    def test_cutout_no_preserves_fully_opaque_canvas(self) -> None:
        # A fully opaque, alpha-less input has nothing to trim: --cutout no
        # must preserve the whole canvas rather than stripping a uniform
        # border as if it were background.
        src = self.path("plain.png")
        magick("-size", "80x50", "xc:#22aa88", str(src))
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "80x50",
                     "--pad", "0", "--cutout", "no")
        self.assertEqual(0, result.returncode, result.stderr)
        diff = subprocess.run(
            ["magick", "compare", "-metric", "AE", str(out), str(src), "null:"],
            capture_output=True, text=True,
        )
        self.assertEqual("0", diff.stderr.strip().split()[0])

    def test_key_cutout(self) -> None:
        src = self.path("key.png")
        magick(
            "-size", "100x100", "xc:#00ff00", "-fill", "#ff00ff",
            "-draw", "rectangle 20,20 80,80", str(src),
        )
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "128x128", "--cutout", "key")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("cutout=key", result.stdout)
        self.assertIn("key_px=0", result.stdout)

    def test_blank_input_rejected(self) -> None:
        src = self.path("blank.png")
        magick("-size", "50x50", "xc:#123456", str(src))
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "64x64")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("empty alpha", result.stderr)
        self.assertFalse(out.exists())

    def test_pixel_mode_binary_alpha(self) -> None:
        src = self.path("src.png")
        magick(
            "-size", "300x200", "xc:#3355ff", "-fill", "#ff0000",
            "-draw", "circle 150,100 150,50", str(src),
        )
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "32x32", "--pixel")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("pixel=yes", result.stdout)
        levels = subprocess.run(
            ["magick", str(out), "-alpha", "extract", "-format", "%[fx:minima] %[fx:maxima]", "info:"],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        for v in levels:
            self.assertIn(float(v), (0.0, 1.0))

    def test_stable_repeated_bytes(self) -> None:
        src = self.path("src.png")
        magick(
            "-size", "150x150", "xc:#3355ff", "-fill", "#ff0000",
            "-draw", "circle 75,75 75,20", str(src),
        )
        out1, out2 = self.path("out1.png"), self.path("out2.png")
        r1 = run("fit", str(src), str(out1), "--canvas", "200x200")
        r2 = run("fit", str(src), str(out2), "--canvas", "200x200")
        self.assertEqual(0, r1.returncode, r1.stderr)
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_fit_invalid_inputs(self) -> None:
        src = self.path("src.png")
        magick("-size", "10x10", "xc:#ff0000", str(src))
        out_bad_ext = self.path("out.jpg")
        self.assertNotEqual(0, run("fit", str(src), str(out_bad_ext), "--canvas", "10x10").returncode)
        self.assertNotEqual(
            0, run("fit", str(src), str(self.path("o.png")), "--canvas", "notacanvas").returncode
        )
        self.assertNotEqual(
            0, run("fit", str(src), str(self.path("o.png")), "--canvas", "10x10", "--pad", "0.9").returncode
        )
        self.assertNotEqual(
            0, run("fit", str(src), str(self.path("o.png")), "--canvas", "10x10", "--fuzz", "150").returncode
        )
        self.assertNotEqual(0, run("fit", str(src), str(src), "--canvas", "10x10").returncode)
        self.assertNotEqual(
            0, run("fit", str(self.path("missing.png")), str(self.path("o.png")), "--canvas", "10x10").returncode
        )
        self.assertNotEqual(
            0, run("fit", str(src), str(self.path("o.png")), "--canvas", "5000x5000").returncode
        )

    # --------------------------------------------------------- palette ---

    def test_palette_bounds(self) -> None:
        src = self.path("src.png")
        magick(
            "-size", "40x40", "xc:#ff0000", "-fill", "#00ff00",
            "-draw", "rectangle 0,0 19,39", str(src),
        )
        out = self.path("palette.png")
        self.assertNotEqual(
            0, run("palette", str(src), str(out), "--colors", "1").returncode
        )
        self.assertNotEqual(
            0, run("palette", str(src), str(out), "--colors", "257").returncode
        )
        result = run("palette", str(src), str(out), "--colors", "8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(out.exists())
        w, h = subprocess.run(
            ["magick", "identify", "-format", "%w %h", str(out)],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        self.assertEqual("1", h)
        self.assertLessEqual(int(w), 8)
        self.assertGreaterEqual(int(w), 1)

    def test_palette_excludes_transparent_black_background(self) -> None:
        # `xc:none` stores transparent pixels as RGB (0,0,0) underneath —
        # a common exporter default. A palette built from this image must
        # never contain that background black; only the opaque red circle.
        src = self.path("src.png")
        magick(
            "-size", "80x80", "xc:none", "-fill", "#ff0000",
            "-draw", "circle 40,40 40,10", str(src),
        )
        out = self.path("palette.png")
        result = run("palette", str(src), str(out), "--colors", "4")
        self.assertEqual(0, result.returncode, result.stderr)
        colors = subprocess.run(
            ["magick", str(out), "-alpha", "off", "-unique-colors", "txt:-"],
            check=True, capture_output=True, text=True,
        ).stdout.lower()
        self.assertNotIn("#000000", colors)

    def test_fit_palette_preserves_alpha_and_bounds_colors(self) -> None:
        # Multi-colour foreground on a real transparent background.
        src = self.path("src.png")
        magick(
            "-size", "120x120", "xc:none",
            "-fill", "#ff0000", "-draw", "circle 30,60 30,10",
            "-fill", "#00ff00", "-draw", "circle 60,60 60,10",
            "-fill", "#0000ff", "-draw", "circle 90,60 90,10",
            str(src),
        )
        palette = self.path("palette.png")
        palette_result = run("palette", str(src), str(palette), "--colors", "4")
        self.assertEqual(0, palette_result.returncode, palette_result.stderr)

        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "128x128", "--palette", str(palette))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("palette=yes", result.stdout)

        # Transparency preserved: corners stay transparent (RESULT and the
        # actual file both agree — the RESULT line is read from the final
        # output, not a pre-remap intermediate).
        self.assertIn("corner_alpha=0.0000", result.stdout)
        corner = subprocess.run(
            ["magick", str(out), "-alpha", "extract", "-format", "%[fx:p{0,0}]", "info:"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual("0", corner)
        coverage_line = [p for p in result.stdout.split() if p.startswith("coverage=")][0]
        self.assertGreater(float(coverage_line.split("=")[1]), 0.0)

        # The remap must never introduce more distinct RGB values than the
        # palette it was built from (<=4 requested colours) — but a colour
        # COUNT alone doesn't catch a remap that whitens everything (white
        # is "one distinct colour" too), so also sample the actual centre
        # of each circle and require it to still read as its own hue, not
        # a shared white silhouette.
        colors = subprocess.run(
            ["magick", str(out), "-alpha", "off", "-unique-colors", "txt:-"],
            check=True, capture_output=True, text=True,
        ).stdout
        n_colors = sum(1 for line in colors.splitlines() if line.strip() and not line.startswith("#"))
        self.assertLessEqual(n_colors, 4)

        centres = {
            "red": rgb_at(out, 32, 64),
            "green": rgb_at(out, 64, 64),
            "blue": rgb_at(out, 96, 64),
        }
        for name, (r, g, b) in centres.items():
            self.assertFalse(g > 0.9 and b > 0.9, f"{name} centre whitened: {(r, g, b)}")
        self.assertGreaterEqual(len({tuple(round(c, 2) for c in v) for v in centres.values()}), 2)

    def test_fit_palette_preserves_actual_hues_not_whitened(self) -> None:
        # P1 regression: an unscoped "-alpha extract" in the CopyOpacity
        # reattach step used to apply to BOTH images in the command's
        # stack, alpha-extracting (and so whitening) the remapped RGB
        # image too — every colour came out as a flat white silhouette.
        # Three solid, non-overlapping colour blocks make the failure
        # unambiguous: each swatch's own centre must keep its own hue.
        # --cutout no keeps this test isolated to the remap/reattach step
        # (the blocks span the whole opaque canvas, corner to corner —
        # letting auto-cutout run would flood-fill the corner-colour
        # block away entirely, which is a different code path).
        src = self.path("src.png")
        magick(
            "-size", "90x30", "xc:none",
            "-fill", "#ff0000", "-draw", "rectangle 0,0 29,29",
            "-fill", "#00ff00", "-draw", "rectangle 30,0 59,29",
            "-fill", "#0000ff", "-draw", "rectangle 60,0 89,29",
            str(src),
        )
        palette = self.path("palette.png")
        palette_result = run("palette", str(src), str(palette), "--colors", "3")
        self.assertEqual(0, palette_result.returncode, palette_result.stderr)

        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "90x30", "--pad", "0",
                     "--cutout", "no", "--palette", str(palette))
        self.assertEqual(0, result.returncode, result.stderr)

        red = rgb_at(out, 15, 15)
        green = rgb_at(out, 45, 15)
        blue = rgb_at(out, 75, 15)

        # Each swatch must still read as its own dominant channel — not a
        # shared (1, 1, 1) white silhouette.
        self.assertGreater(red[0], 0.6, red)
        self.assertLess(red[1], 0.4, red)
        self.assertLess(red[2], 0.4, red)
        self.assertGreater(green[1], 0.6, green)
        self.assertLess(green[0], 0.4, green)
        self.assertLess(green[2], 0.4, green)
        self.assertGreater(blue[2], 0.6, blue)
        self.assertLess(blue[0], 0.4, blue)
        self.assertLess(blue[1], 0.4, blue)

        distinct = {tuple(round(c, 2) for c in v) for v in (red, green, blue)}
        self.assertGreaterEqual(len(distinct), 2)

    def test_cutout_no_preserves_uniform_translucent_object(self) -> None:
        # A uniformly ~30%-alpha "glass" object: every pixel is below the
        # old >=50% threshold, so alpha_bbox used to report the zero box
        # and --cutout no's crop-to-bbox step then failed on a 0x0
        # geometry, wrongly rejecting real (if translucent) content as
        # "empty alpha". It must fit through untouched instead.
        src = self.path("glass.png")
        magick("-size", "80x80", "xc:rgba(255,0,255,0.3)", str(src))
        out = self.path("out.png")
        result = run("fit", str(src), str(out), "--canvas", "80x80",
                     "--pad", "0", "--cutout", "no")
        self.assertEqual(0, result.returncode, result.stderr)
        diff = subprocess.run(
            ["magick", "compare", "-metric", "AE", str(out), str(src), "null:"],
            capture_output=True, text=True,
        )
        self.assertEqual("0", diff.stderr.strip().split()[0])
        alpha = subprocess.run(
            ["magick", str(out), "-alpha", "extract", "-format", "%[fx:mean]", "info:"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertAlmostEqual(0.3, float(alpha), places=2)

    # ----------------------------------------------------------- atlas ---

    def test_atlas_roundtrip_and_duplicate_basenames(self) -> None:
        source = self.path("source")
        (source / "a").mkdir(parents=True)
        (source / "b").mkdir(parents=True)
        magick("-size", "40x60", "xc:#ff0000", str(source / "a" / "one.png"))
        magick("-size", "30x30", "xc:#00ff00", str(source / "b" / "one.png"))
        magick("-size", "20x20", "xc:#0000ff", str(source / "a" / "two.png"))

        out_dir = self.path("atlas_out")
        result = run("atlas", str(source), str(out_dir), "--columns", "2", "--gap", "4")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((out_dir / "atlas.png").exists())
        self.assertTrue((out_dir / "sheet.png").exists())

        manifest = json.loads((out_dir / "atlas.json").read_text())
        rel_files = sorted(f["file"] for f in manifest["frames"])
        self.assertEqual(["a/one.png", "a/two.png", "b/one.png"], rel_files)

        for frame in manifest["frames"]:
            crop_spec = f"{frame['width']}x{frame['height']}+{frame['x']}+{frame['y']}"
            crop_out = self.path(f"crop-{frame['file'].replace('/', '_')}.png")
            magick(str(out_dir / "atlas.png"), "-crop", crop_spec, "+repage", str(crop_out))
            diff = subprocess.run(
                ["magick", "compare", "-metric", "AE", str(crop_out), str(source / frame["file"]), "null:"],
                capture_output=True, text=True,
            )
            self.assertEqual("0", diff.stderr.strip().split()[0], frame["file"])

    def test_atlas_nested_output_rejected(self) -> None:
        source = self.path("source")
        source.mkdir()
        magick("-size", "10x10", "xc:#ff0000", str(source / "one.png"))
        result = run("atlas", str(source), str(source / "nested"))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("inside", result.stderr)

    def test_atlas_nonempty_output_dir_refused(self) -> None:
        source = self.path("source")
        source.mkdir()
        magick("-size", "10x10", "xc:#ff0000", str(source / "one.png"))
        out_dir = self.path("atlas_out")
        first = run("atlas", str(source), str(out_dir))
        self.assertEqual(0, first.returncode, first.stderr)
        # A second run into the SAME (now non-empty) directory must be
        # refused outright rather than silently overwriting/leaving a mix
        # of old and new files behind.
        second = run("atlas", str(source), str(out_dir))
        self.assertNotEqual(0, second.returncode)
        self.assertIn("not empty", second.stderr)

    # --------------------------------------------------------- measure ---

    def test_measure_count_and_nested_output_rejected(self) -> None:
        source = self.path("pack")
        source.mkdir()
        magick("-size", "50x50", "xc:#00ff00", str(source / "a.png"))
        magick("-size", "30x30", "xc:#0000ff", str(source / "b.png"))
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        self.assertEqual(2, data["summary"]["count"])
        self.assertTrue((out_dir / "sheet.png").exists())
        self.assertTrue((out_dir / "native.png").exists())
        self.assertTrue((out_dir / "light.png").exists())
        self.assertTrue((out_dir / "dark.png").exists())
        self.assertTrue((out_dir / "silhouette.png").exists())
        self.assertFalse((out_dir / "against.png").exists())

        nested_result = run("measure", str(source), "--out", str(source / "nested"))
        self.assertNotEqual(0, nested_result.returncode)
        self.assertIn("inside", nested_result.stderr)

    def test_measure_bbox_hollow_frame_full_extent(self) -> None:
        # Regression: bbox must be the full occupied extent (the frame's
        # own outer edges, which touch the whole 100x100 canvas), never
        # the transparent interior hole a colour `-trim` would report.
        source = self.path("pack")
        source.mkdir()
        make_hollow_frame(source / "frame.png", size=100, hole="20,20 79,79")
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        bbox = data["files"][0]["bbox"]
        self.assertEqual({"width": 100, "height": 100, "x": 0, "y": 0}, bbox)

    def test_measure_bbox_uniform_opaque_rectangle_is_whole_canvas(self) -> None:
        source = self.path("pack")
        source.mkdir()
        magick("-size", "64x48", "xc:#22aa88", str(source / "plain.png"))
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        bbox = data["files"][0]["bbox"]
        self.assertEqual({"width": 64, "height": 48, "x": 0, "y": 0}, bbox)

    def test_measure_bbox_partial_alpha_content(self) -> None:
        # A real (non-hollow) subject with genuine transparent margins on
        # every side: bbox must be exactly its own bounding rectangle.
        source = self.path("pack")
        source.mkdir()
        magick(
            "-size", "100x100", "xc:none", "-fill", "#ff00ff",
            "-draw", "rectangle 30,10 69,89", str(source / "blob.png"),
        )
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        bbox = data["files"][0]["bbox"]
        self.assertEqual({"width": 40, "height": 80, "x": 30, "y": 10}, bbox)

    def test_measure_bbox_translucent_object_full_extent(self) -> None:
        # A uniformly ~30%-alpha object: every pixel is below a >=50%
        # threshold, so it must not be zeroed out — bbox is the object's
        # real, nonzero extent (the whole canvas here).
        source = self.path("pack")
        source.mkdir()
        magick("-size", "80x80", "xc:rgba(255,0,255,0.3)", str(source / "glass.png"))
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        bbox = data["files"][0]["bbox"]
        self.assertEqual({"width": 80, "height": 80, "x": 0, "y": 0}, bbox)

    def test_measure_bbox_all_transparent_is_zero_box(self) -> None:
        source = self.path("pack")
        source.mkdir()
        magick("-size", "40x40", "xc:none", str(source / "blank.png"))
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads((out_dir / "measurements.json").read_text())
        bbox = data["files"][0]["bbox"]
        self.assertEqual({"width": 0, "height": 0, "x": 0, "y": 0}, bbox)

    def test_measure_against_sheet_written(self) -> None:
        source = self.path("pack")
        source.mkdir()
        magick("-size", "50x50", "xc:#00ff00", str(source / "a.png"))
        anchor = self.path("anchor.png")
        magick("-size", "50x50", "xc:#ff00ff", str(anchor))
        out_dir = self.path("measure_out")
        result = run("measure", str(source), "--out", str(out_dir), "--against", str(anchor))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((out_dir / "against.png").exists())

    def test_measure_rerun_without_against_refused_not_stale(self) -> None:
        # A first run WITH --against writes against.png. Reusing the same
        # output directory for a later run WITHOUT --against must be
        # refused outright — never silently succeed and leave that
        # against.png behind as a stale artifact from the prior revision.
        source = self.path("pack")
        source.mkdir()
        magick("-size", "50x50", "xc:#00ff00", str(source / "a.png"))
        anchor = self.path("anchor.png")
        magick("-size", "50x50", "xc:#ff00ff", str(anchor))
        out_dir = self.path("measure_out")

        first = run("measure", str(source), "--out", str(out_dir), "--against", str(anchor))
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertTrue((out_dir / "against.png").exists())

        second = run("measure", str(source), "--out", str(out_dir))
        self.assertNotEqual(0, second.returncode)
        self.assertIn("not empty", second.stderr)
        # The refused rerun must not have touched anything.
        self.assertTrue((out_dir / "against.png").exists())

    def test_measure_nonempty_output_dir_refused(self) -> None:
        out_dir = self.path("measure_out")
        out_dir.mkdir()
        (out_dir / "stray.txt").write_text("leftover", encoding="utf-8")
        source = self.path("pack")
        source.mkdir()
        magick("-size", "20x20", "xc:#00ff00", str(source / "a.png"))
        result = run("measure", str(source), "--out", str(out_dir))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
