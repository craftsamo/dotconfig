"""Tests for video-creator's analyze-explainer-video evidence helper.

Tiny synthetic ffmpeg fixtures only; skipped when ffmpeg/ffprobe or Pillow
are missing. The helper is driven through its CLI entry point in-process.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
    / "analyze" / "explainer-video" / "scripts" / "explainer-evidence.py"
)

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - environment dependent
    Image = None

HAVE_TOOLS = bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and Image)


def load_module():
    spec = importlib.util.spec_from_file_location("explainer_evidence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_TOOLS, "ffmpeg, ffprobe and Pillow are required")
class ExplainerEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name).resolve()  # the helper refuses symlinked parents (/var on macOS)
        cls.video = cls.dir / "two-scenes.mp4"
        # 3 s of red, then 3 s of blue: one hard cut at 3 s.
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=3",
             "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10:d=3",
             "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0", "-pix_fmt", "yuv420p", str(cls.video)],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        old = sys.argv
        sys.argv = [str(SCRIPT), *argv]
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    self.module.main()
                    code = 0
                except SystemExit as exc:
                    code = exc.code
        finally:
            sys.argv = old
        text = out.getvalue()
        result = json.loads(text.split("RESULT: ", 1)[1]) if "RESULT: " in text else None
        return code, result, err.getvalue()

    def test_overview_samples_every_second_and_around_the_cut(self):
        out = self.dir / "overview"
        code, result, err = self.run_cli("overview", str(self.video), str(out))
        self.assertEqual(code, 0, err)
        evidence = json.loads((out / "evidence.json").read_text())
        seconds = [frame["seconds"] for frame in evidence["frames"]]
        self.assertEqual(seconds[:6], [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(len(evidence["cuts"]), 1)
        self.assertAlmostEqual(evidence["cuts"][0], 3.0, delta=0.15)
        near = [frame["seconds"] for frame in evidence["cut_frames"]]
        self.assertIn(2.5, near)
        self.assertIn(3.5, near)
        for sheet in evidence["sheets"] + evidence["cut_sheets"]:
            self.assertTrue((out / sheet["file"]).is_file())
        self.assertEqual(evidence["remote_calls"], 0)
        code, _, err = self.run_cli("overview", str(self.video), str(out))
        self.assertEqual(code, 1)
        self.assertIn("output must be new", err)

    def test_window_is_bounded(self):
        code, result, err = self.run_cli("window", str(self.video), str(self.dir / "window"), "--start", "2.5", "--duration", "1")
        self.assertEqual(code, 0, err)
        self.assertEqual(result["frames"], 4)
        code, _, err = self.run_cli("window", str(self.video), str(self.dir / "window-long"), "--start", "0", "--duration", "5")
        self.assertEqual(code, 1)
        self.assertIn("at most 4 s", err)

    def test_detail_writes_a_native_frame_and_an_enlarged_crop(self):
        code, result, err = self.run_cli("detail", str(self.video), str(self.dir / "detail"), "--at", "4",
                                         "--crop", "10", "10", "110", "60", "--scale", "3")
        self.assertEqual(code, 0, err)
        frame, crop = (Path(f) for f in result["files"])
        with Image.open(frame) as picture:
            self.assertEqual(picture.size, (320, 180))
            self.assertGreater(picture.getpixel((5, 5))[2], 200)
        with Image.open(crop) as picture:
            self.assertEqual(picture.size, (300, 150))

    def test_measure_reads_line_heights_by_row_projection(self):
        frame = self.dir / "text.png"
        picture = Image.new("RGB", (960, 540), "black")
        draw = ImageDraw.Draw(picture)
        draw.rectangle((100, 100, 400, 129), fill="white")  # a 30 px "line"
        draw.rectangle((100, 200, 300, 214), fill="white")  # a 15 px "line"
        picture.save(frame)
        code, result, err = self.run_cli("measure", str(frame), "--box", "50", "50", "500", "300")
        self.assertEqual(code, 0, err)
        heights = [line["height_px"] for line in result["lines"]]
        self.assertEqual(heights, [30, 15])
        self.assertEqual([line["height_at_1080p"] for line in result["lines"]], [60.0, 30.0])

    def test_many_cuts_are_thinned_and_disclosed(self):
        original_cuts, original_max = self.module.detect_cuts, self.module.MAX_CUTS
        self.module.detect_cuts = lambda info, threshold: [1.2, 2.2, 3.2, 4.2]
        self.module.MAX_CUTS = 2
        try:
            out = self.dir / "thinned"
            code, result, err = self.run_cli("overview", str(self.video), str(out))
        finally:
            self.module.detect_cuts, self.module.MAX_CUTS = original_cuts, original_max
        self.assertEqual(code, 0, err)
        evidence = json.loads((out / "evidence.json").read_text())
        self.assertEqual(evidence["cuts"], [1.2, 2.2, 3.2, 4.2])
        self.assertEqual(evidence["cuts_sampled"], [1.2, 3.2])
        self.assertEqual(result["cuts_with_stills"], 2)

    def test_measure_refuses_an_enlarged_crop(self):
        frame = self.dir / "d0001.000-crop-0-0-10-10.png"
        Image.new("RGB", (20, 20), "black").save(frame)
        code, _, err = self.run_cli("measure", str(frame), "--box", "0", "0", "10", "10")
        self.assertEqual(code, 1)
        self.assertIn("not an enlarged crop", err)

    def test_clock_labels_never_show_sixty_seconds(self):
        self.assertEqual(self.module.clock(59.96), "1:00.0")
        self.assertEqual(self.module.clock(75.3), "1:15.3")

    def test_refuses_a_video_over_ten_minutes(self):
        original = self.module.MEDIA.probe
        self.module.MEDIA.probe = lambda source: {**original(source), "duration": 601.0}
        try:
            code, _, err = self.run_cli("overview", str(self.video), str(self.dir / "too-long"))
        finally:
            self.module.MEDIA.probe = original
        self.assertEqual(code, 1)
        self.assertIn("longer than 600 s", err)


if __name__ == "__main__":
    unittest.main()
