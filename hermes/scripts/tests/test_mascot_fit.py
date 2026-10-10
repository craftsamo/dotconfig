"""Tests for image-creator's mascot-fit.sh key diagnostics (removed / key_loss).

Runs the script as a subprocess, exactly how a leaf invokes it. The drawn
background is a dull green like the ones image models return instead of
pure #00ff00. Skipped entirely when `magick` is not on PATH.
"""

from __future__ import annotations

import re
import shutil
import subprocess
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
    / "scripts"
    / "mascot-fit.sh"
)
DRAWN_GREEN = "#53C440"


def magick(*args: str) -> None:
    subprocess.run(["magick", *args], check=True, capture_output=True, text=True)


def fit(src: Path, out: Path, *options: str) -> dict[str, str]:
    result = subprocess.run(
        ["bash", str(SCRIPT), str(src), str(out), "--size", "256", *options],
        check=True, capture_output=True, text=True,
    )
    line = next(l for l in result.stdout.splitlines() if l.startswith("RESULT:"))
    return dict(re.findall(r"(\w+)=(\S+)", line))


def ring(out: Path, fill: str) -> None:
    """A 120 px square character with a 10 px pocket of background inside it."""
    magick(
        "-size", "200x200", f"xc:{DRAWN_GREEN}",
        "-fill", fill, "-draw", "rectangle 40,40 159,159",
        "-fill", DRAWN_GREEN, "-draw", "rectangle 95,95 104,104",
        str(out),
    )


@unittest.skipUnless(shutil.which("magick"), "ImageMagick not installed")
class MascotFitKeyLossTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_flood_reports_the_sampled_background_without_key_loss(self) -> None:
        ring(self.tmp / "cream.png", "#F5E6C8")
        result = fit(self.tmp / "cream.png", self.tmp / "out.png", "--cutout", "yes")
        self.assertEqual(result["removed"].upper(), DRAWN_GREEN)
        self.assertNotIn("key_loss", result)

    def test_key_that_only_clears_a_pocket_has_small_loss(self) -> None:
        ring(self.tmp / "cream.png", "#F5E6C8")
        result = fit(self.tmp / "cream.png", self.tmp / "out.png", "--cutout", "key", "--fuzz", "30%")
        self.assertLessEqual(float(result["key_loss"]), 0.03)
        self.assertGreater(float(result["key_loss"]), 0)

    def test_key_that_eats_a_costume_near_the_drawn_green_is_flagged(self) -> None:
        ring(self.tmp / "brown.png", "#8B5A2B")
        result = fit(self.tmp / "brown.png", self.tmp / "out.png", "--cutout", "key", "--fuzz", "30%")
        self.assertGreater(float(result["key_loss"]), 0.5)


if __name__ == "__main__":
    unittest.main()
