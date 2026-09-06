"""Tests for video-creator's clip-media.py (probe / frames / edit).

Runs clip-media.py as a subprocess, exactly how a skill invokes it, using
tiny synthetic ffmpeg/ffprobe fixtures (no external network calls, no real
media). Skipped entirely when `ffmpeg`/`ffprobe` are not on PATH; the
`frames` command additionally needs `magick` and is skipped without it.

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
    / "video-creator"
    / "skills"
    / "video-creator-pipeline"
    / "scripts"
    / "clip-media.py"
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
MAGICK = shutil.which("magick")
HAVE_FFMPEG = bool(FFMPEG and FFPROBE)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def result_of(proc: subprocess.CompletedProcess) -> dict:
    line = next(l for l in proc.stdout.splitlines() if l.startswith("RESULT: "))
    return json.loads(line[len("RESULT: "):])


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True,
                    capture_output=True, text=True)


def ffprobe_json(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def make_square_clip(path: Path, size: str = "64x64", duration: float = 2.0,
                      fps: int = 25, audio: bool = True) -> None:
    """A tiny H.264 mp4 with a sine-wave audio track (unless `audio=False`)."""
    args = ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={duration}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    args.append(str(path))
    ffmpeg(*args)


def make_odd_clip(path: Path, size: str = "65x49", duration: float = 1.0,
                   fps: int = 25) -> None:
    """An odd-dimension, lossless PNG-coded clip in an mkv container.
    `testsrc2` silently rounds odd sizes down to even, so this uses a
    plain `color=` source instead, which preserves them exactly."""
    ffmpeg(
        "-f", "lavfi", "-i", f"color=c=red:size={size}:rate={fps}:duration={duration}",
        "-c:v", "png", "-pix_fmt", "rgb24", str(path),
    )


def make_audio_only(path: Path, duration: float = 1.0) -> None:
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
           "-c:a", "aac", str(path))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not found")
class ClipMediaTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def path(self, name: str) -> Path:
        return self.root / name


class ProbeTest(ClipMediaTestBase):
    def test_probe_basic_fields(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        result = result_of(run("probe", str(src)))
        self.assertEqual(64, result["width"])
        self.assertEqual(64, result["height"])
        self.assertEqual(64, result["display_width"])
        self.assertEqual(64, result["display_height"])
        self.assertTrue(result["audio"])
        self.assertAlmostEqual(2.0, result["duration"], delta=0.2)
        self.assertEqual("h264", result["codec"])

    def test_probe_missing_source(self) -> None:
        result = run("probe", str(self.path("nope.mp4")))
        self.assertNotEqual(0, result.returncode)

    def test_probe_nonvideo_source_rejected(self) -> None:
        src = self.path("audio.m4a")
        make_audio_only(src)
        result = run("probe", str(src))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no video stream", result.stderr)

    def test_probe_odd_dimensions_preserved(self) -> None:
        src = self.path("odd.mkv")
        make_odd_clip(src)
        result = result_of(run("probe", str(src)))
        self.assertEqual(65, result["width"])
        self.assertEqual(49, result["height"])
        self.assertFalse(result["audio"])


class EditHappyPathTest(ClipMediaTestBase):
    def test_trim_mute_contain_resize(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out),
                    "--trim", "0.2:0.5", "--mute", "--size", "160x90", "--fit", "contain")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertTrue(out.exists())
        self.assertEqual(160, result["width"])
        self.assertEqual(90, result["height"])
        self.assertAlmostEqual(0.5, result["duration"], delta=0.15)
        self.assertFalse(result["audio"])
        self.assertTrue(result["audio_removed"])

    def test_audio_preserved_by_default(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["audio"])
        self.assertFalse(result["audio_removed"])
        # Verify against the actual encoded file, not just the tool's claim.
        probed = ffprobe_json(out)
        self.assertTrue(any(s.get("codec_type") == "audio" for s in probed["streams"]))

    def test_source_unaffected_and_never_overwritten(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        before = src.read_bytes()
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(before, src.read_bytes())

    def test_cover_and_fps(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        proc = run("edit", str(src), str(self.path("cover.mp4")),
                   "--size", "160x90", "--fit", "cover", "--fps", "10")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual((160, 90, 10), (result["width"], result["height"], result["fps"]))
        self.assertIsNone(result["within_cap"])

    def test_rotated_anamorphic_dimensions_match_probe(self) -> None:
        original = self.path("anamorphic.mp4")
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:duration=1",
               "-vf", "setsar=4/3", "-c:v", "libx264", str(original))
        src = self.path("rotated.mp4")
        ffmpeg("-display_rotation", "90", "-i", str(original), "-c", "copy", str(src))
        info = result_of(run("probe", str(src)))
        self.assertEqual((64, 128), (info["display_width"], info["display_height"]))
        proc = run("edit", str(src), str(self.path("fixed.mp4")))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual((64, 128), (result["width"], result["height"]))
        self.assertEqual(0, result["rotation"])


class EditOddSizeTest(ClipMediaTestBase):
    def test_odd_source_padded_when_size_omitted(self) -> None:
        src = self.path("odd.mkv")
        make_odd_clip(src)
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        # Padded up to the next even dimensions, not cropped down.
        self.assertEqual(66, result["width"])
        self.assertEqual(50, result["height"])

    def test_explicit_odd_size_refused_for_mp4(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out), "--size", "65x49")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("must be even", proc.stderr)
        self.assertFalse(out.exists())

    def test_explicit_odd_size_refused_for_webm(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.webm")
        proc = run("edit", str(src), str(out), "--format", "webm", "--size", "65x49")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("must be even", proc.stderr)
        self.assertFalse(out.exists())


class EditTrimValidationTest(ClipMediaTestBase):
    def _src(self) -> Path:
        src = self.path("square.mp4")
        make_square_clip(src)
        return src

    def test_malformed_trim_rejected(self) -> None:
        proc = run("edit", str(self._src()), str(self.path("o.mp4")), "--trim", "abc")
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(self.path("o.mp4").exists())

    def test_negative_start_rejected(self) -> None:
        proc = run("edit", str(self._src()), str(self.path("o.mp4")), "--trim=-1:0.5")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("positive segment", proc.stderr)
        self.assertFalse(self.path("o.mp4").exists())

    def test_nonfinite_trim_rejected(self) -> None:
        proc = run("edit", str(self._src()), str(self.path("o.mp4")), "--trim", "inf:0.5")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("finite", proc.stderr)
        self.assertFalse(self.path("o.mp4").exists())

    def test_trim_end_beyond_source_rejected(self) -> None:
        proc = run("edit", str(self._src()), str(self.path("o.mp4")), "--trim", "0.5:100")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("exceeds the source duration", proc.stderr)
        self.assertFalse(self.path("o.mp4").exists())

    def test_trim_start_at_or_past_duration_rejected(self) -> None:
        proc = run("edit", str(self._src()), str(self.path("o.mp4")), "--trim", "999:1")
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(self.path("o.mp4").exists())


class EditOutputValidationTest(ClipMediaTestBase):
    def test_output_extension_must_match_format(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        proc = run("edit", str(src), str(self.path("out.webm")), "--format", "mp4")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("extension must match format", proc.stderr)

    def test_existing_output_refused_and_source_untouched(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        out.write_bytes(b"already here")
        before_src = src.read_bytes()
        proc = run("edit", str(src), str(out))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("never overwritten", proc.stderr)
        self.assertEqual(b"already here", out.read_bytes())
        self.assertEqual(before_src, src.read_bytes())

    def test_missing_source_rejected(self) -> None:
        proc = run("edit", str(self.path("missing.mp4")), str(self.path("out.mp4")))
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(self.path("out.mp4").exists())

    def test_nonvideo_source_rejected(self) -> None:
        src = self.path("audio.m4a")
        make_audio_only(src)
        proc = run("edit", str(src), str(self.path("out.mp4")))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("no video stream", proc.stderr)

    def test_clip_bound_to_60_seconds(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src, duration=61, fps=1, audio=False)
        proc = run("edit", str(src), str(self.path("o.mp4")))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("at most 60 seconds", proc.stderr)
        self.assertFalse(self.path("o.mp4").exists())


class EditByteCapTest(ClipMediaTestBase):
    def test_tiny_cap_fails_without_output(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        proc = run("edit", str(src), str(out), "--max-bytes", "50")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("too small", proc.stderr)
        self.assertFalse(out.exists())

    def test_feasible_cap_honored_with_actual_bytes(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.mp4")
        cap = 200_000
        proc = run("edit", str(src), str(out), "--max-bytes", str(cap))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertLessEqual(result["bytes"], cap)
        self.assertEqual(out.stat().st_size, result["bytes"])


class EditWebmTest(ClipMediaTestBase):
    def test_webm_encode(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.webm")
        proc = run("edit", str(src), str(out), "--format", "webm")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual("vp9", result["codec"])
        self.assertTrue(out.exists())


class EditGifTest(ClipMediaTestBase):
    def test_gif_trim_selects_content_before_palette(self) -> None:
        src = self.path("colors.mp4")
        ffmpeg("-f", "lavfi", "-i", "color=red:size=64x64:duration=1",
               "-f", "lavfi", "-i", "color=blue:size=64x64:duration=1",
               "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
               "-map", "[v]", "-c:v", "libx264", str(src))
        out = self.path("blue.gif")
        proc = run("edit", str(src), str(out), "--trim", "1:0.5", "--fps", "10")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertAlmostEqual(0.5, result["duration"], delta=0.11)
        pixels = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(out), "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            check=True, capture_output=True).stdout
        self.assertGreater(pixels[2], 200)
        self.assertLess(pixels[0], 20)

    def test_gif_loop_encodes_with_audio_input(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        out = self.path("out.gif")
        proc = run("edit", str(src), str(out), "--format", "gif", "--loop")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual("gif", result["codec"])
        self.assertFalse(result["audio"])
        self.assertTrue(result["decoded"])
        self.assertIn(b"NETSCAPE2.0\x03\x01\x00\x00", out.read_bytes())

    def test_gif_without_loop_has_no_repeat_extension(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src, audio=False)
        out = self.path("once.gif")
        proc = run("edit", str(src), str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn(b"NETSCAPE2.0", out.read_bytes())

    def test_gif_loop_flag_rejected_for_non_gif(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src)
        proc = run("edit", str(src), str(self.path("o.mp4")), "--loop")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("GIF playback metadata", proc.stderr)


@unittest.skipUnless(HAVE_FFMPEG and MAGICK, "ffmpeg/ffprobe/magick not found")
class FramesTest(ClipMediaTestBase):
    def test_frames_start_middle_end_and_json_mapping(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src, duration=2.0)
        out = self.path("review")
        proc = run("frames", str(src), str(out), "--count", "3")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual(3, len(result["times"]))
        self.assertAlmostEqual(0.0, result["times"][0], delta=0.01)
        self.assertGreater(result["times"][1], result["times"][0])
        self.assertGreater(result["times"][2], result["times"][1])
        self.assertLess(result["times"][2], 2.0)
        # The JSON mapping's frame paths must sit inside the requested
        # output directory and actually exist on disk.
        for frame_path in result["frames"]:
            frame = Path(frame_path)
            self.assertEqual(out, frame.parent)
            self.assertTrue(frame.is_file())
        self.assertTrue(Path(result["sheet"]).is_file())
        self.assertEqual(out / "sheet.png", Path(result["sheet"]))

    def test_frames_refuses_existing_review_directory(self) -> None:
        src = self.path("square.mp4")
        make_square_clip(src, duration=1.0)
        out = self.path("review")
        first = run("frames", str(src), str(out), "--count", "3")
        self.assertEqual(0, first.returncode, first.stderr)
        existing = {p.name for p in out.iterdir()}

        second = run("frames", str(src), str(out), "--count", "3")
        self.assertNotEqual(0, second.returncode)
        self.assertIn("must not exist", second.stderr)
        # The refused rerun must not have touched the existing review set.
        self.assertEqual(existing, {p.name for p in out.iterdir()})


if __name__ == "__main__":
    unittest.main()
