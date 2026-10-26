"""Tests for speech-media.py's prosody measurement (analyze --prosody).

The measurement needs numpy (faster_whisper brings it at runtime); those tests
skip where it is missing, as the other numpy-dependent suites do. Fixtures are
synthetic ffmpeg tones; no ASR runs.
"""

from __future__ import annotations

import builtins
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import hermes_yaml as yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "pipeline"
SCRIPT = PIPELINE / "scripts" / "speech-media.py"

try:
    import numpy as np
except ImportError:  # pragma: no cover - environment dependent
    np = None


def load_module():
    spec = importlib.util.spec_from_file_location("speech_media_prosody", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


speech_media = load_module()


class ProsodyContract(unittest.TestCase):
    def test_leaf_offers_prosody_as_a_measurement_only(self):
        text = (PIPELINE / "speech" / "analyze" / "SKILL.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        field = meta["metadata"]["hermes"]["form"]["prosody"]
        self.assertEqual((field["required"], field["options"]), (False, ["yes", "no"]))
        flat = " ".join(text.split())
        self.assertIn("`--prosody` when `prosody: yes`", flat)
        self.assertIn("never call a delivery too excited, flat or unnatural from them", flat)
        self.assertIn("`m:ss | voice | <reasons> (ASR: <segment text>) | prosody | confirm`", flat)

    def test_missing_numpy_is_a_dependency_error(self):
        real_import = builtins.__import__

        def refuse(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError("no numpy")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=refuse):
            with self.assertRaises(speech_media.DependencyError):
                speech_media._numpy()

    def test_missing_numpy_fails_before_asr(self):
        args = mock.Mock(source="/nowhere.wav", script_file=None, language="en", prosody=True)
        with mock.patch.object(speech_media, "_numpy", side_effect=speech_media.DependencyError("no numpy")), \
                mock.patch.object(speech_media, "_transcribe_pcm") as asr, \
                mock.patch.object(speech_media, "resolve_source") as resolve:
            with self.assertRaises(speech_media.DependencyError):
                speech_media.analyze(args)
        asr.assert_not_called()
        resolve.assert_not_called()

    def test_a_failed_measurement_keeps_the_asr_result(self):
        args = mock.Mock(source="/a.wav", script_file=None, language="en", prosody=True)
        asr = {"segments": [], "words": [], "language": "en", "transcript": "a sample line"}
        failure = subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"boom")
        with mock.patch.object(speech_media, "_numpy"), \
                mock.patch.object(speech_media, "resolve_source", return_value=Path("/a.wav")), \
                mock.patch.object(speech_media, "decode_and_measure", return_value=({"duration": 1.0}, b"", {})), \
                mock.patch.object(speech_media, "_transcribe_pcm", return_value=asr), \
                mock.patch.object(speech_media, "probe", return_value={"path": "/a.wav", "audio_index": 0}), \
                mock.patch.object(speech_media, "prosody_track", side_effect=failure):
            result = speech_media.analyze(args)
        self.assertEqual(result["transcript"], "a sample line")
        self.assertEqual(result["prosody"]["status"], "unmeasured")
        self.assertEqual(result["prosody"]["candidates"], [])


@unittest.skipUnless(np is not None, "numpy is required for the prosody measurement")
class ProsodyReport(unittest.TestCase):
    def segments(self):
        return [{"start": 0.0, "end": 2.0, "text": "low"},
                {"start": 2.0, "end": 4.0, "text": "high"},
                {"start": 4.0, "end": 6.0, "text": "low again"}]

    def words(self):
        return [{"start": 0.0, "end": 6.0, "word": "all"}]

    def test_jumps_and_high_segments_become_candidates(self):
        f0 = np.concatenate([np.full(200, 150.0), np.full(200, 300.0), np.full(200, 150.0)]).astype(np.float32)
        level = np.concatenate([np.full(200, -20.0), np.full(200, -12.0), np.full(200, -20.0)]).astype(np.float32)
        report = speech_media.prosody_report(f0, level, self.segments(), self.words())
        self.assertEqual(report["status"], "measured")
        self.assertEqual(report["reference_hz"], 150.0)
        pitches = [row["pitch_st"] for row in report["segments"]]
        self.assertEqual(pitches, [0.0, 12.0, 0.0])
        starts = [c["start"] for c in report["candidates"]]
        self.assertEqual(starts, [2.0, 4.0])
        high = report["candidates"][0]["reasons"]
        self.assertIn("pitch +12.0 st vs previous measured segment", high)
        self.assertIn("level +8.0 dB vs previous measured segment", high)
        self.assertIn("pitch +12.0 st above the file median", high)
        self.assertIn("a change of speaker also jumps", report["note"])

    def test_small_intonation_stays_quiet(self):
        f0 = np.concatenate([np.full(300, 150.0), np.full(300, 170.0)]).astype(np.float32)
        level = np.full(600, -20.0, dtype=np.float32)
        segments = [{"start": 0.0, "end": 3.0, "text": "a"}, {"start": 3.0, "end": 6.0, "text": "b"}]
        report = speech_media.prosody_report(f0, level, segments, self.words())
        self.assertEqual(report["candidates"], [])

    def test_frames_outside_words_or_unvoiced_are_ignored(self):
        f0 = np.zeros(600, dtype=np.float32)
        report = speech_media.prosody_report(f0, np.full(600, -20.0, dtype=np.float32), self.segments(), self.words())
        self.assertEqual(report["status"], "unmeasured")
        f0 = np.full(600, 150.0, dtype=np.float32)
        report = speech_media.prosody_report(f0, np.full(600, -20.0, dtype=np.float32), self.segments(),
                                             [{"start": 0.0, "end": 2.0, "word": "first"}])
        self.assertEqual([row["measured"] for row in report["segments"]], [True, False, False])


@unittest.skipUnless(np is not None and shutil.which("ffmpeg"), "numpy and ffmpeg are required")
class ProsodyTrack(unittest.TestCase):
    def test_tones_are_tracked_at_their_pitch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tones.wav"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=150:duration=2",
                 "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                 "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", str(path)],
                check=True,
            )
            f0, level = speech_media.prosody_track(str(path), 0)
        self.assertAlmostEqual(float(np.median(f0[20:180])), 150.0, delta=3.0)
        self.assertAlmostEqual(float(np.median(f0[220:380])), 300.0, delta=6.0)
        self.assertTrue(np.all(level[20:380] > -30))

    def test_a_low_voice_with_harmonics_is_not_read_an_octave_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "low.wav"
            harmonics = "+".join(f"{0.6 / k:.3f}*sin(2*PI*{95 * k}*t)" for k in range(1, 7))
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                 "-i", f"aevalsrc={harmonics}:s=16000:d=2", str(path)],
                check=True,
            )
            f0, _level = speech_media.prosody_track(str(path), 0)
        voiced = f0[20:180]
        self.assertGreater(float(np.mean(voiced > 0)), 0.9)
        self.assertAlmostEqual(float(np.median(voiced)), 95.0, delta=3.0)


if __name__ == "__main__":
    unittest.main()
