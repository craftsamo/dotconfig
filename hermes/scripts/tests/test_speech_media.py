"""Tests for audio-creator's speech-media.py (track / edit / analyze).

speech-media.py is loaded directly (via importlib, since its filename is not
a valid module name) and driven through its CLI entry point `main()`
in-process, exactly the way the real CLI is invoked (same argv / stdout /
stderr / exit-code contract, wrapped as a subprocess.CompletedProcess so
existing assertions read the same way). Tiny synthetic ffmpeg fixtures are
used throughout (no network calls, no real media). Skipped entirely when
`ffmpeg`/`ffprobe` are not on PATH.

ASR is never downloaded or run for real: every test that needs a transcript
monkeypatches speech_media.load_asr_model() to return a fake WhisperModel
that mimics its .transcribe() surface (segments with nested word lists),
matching the real object shape rather than a bespoke stub format. The one
test that exercises the real ASR loader (missing-cache) runs the script as
an actual subprocess and isolates HF_HOME/XDG_CACHE_HOME to an empty
directory so it fails the same way regardless of whether faster_whisper
happens to be installed in the interpreter running pytest -- production
code has no test-only environment seam of its own.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    HERMES_ROOT
    / "profiles"
    / "audio-creator"
    / "skills"
    / "audio-creator-pipeline"
    / "scripts"
    / "speech-media.py"
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
HAVE_FFMPEG = bool(FFMPEG and FFPROBE)


def _load_module():
    spec = importlib.util.spec_from_file_location("speech_media_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


# --------------------------------------------------------------------------
# Fake ASR: mimics faster_whisper.WhisperModel's .transcribe() surface, not a
# production test seam. Segments carry a nested `words` list, matching the
# real object shape (each segment has .start/.end/.text/.words; each word has
# .start/.end/.word).
# --------------------------------------------------------------------------

class FakeWord:
    def __init__(self, start: float, end: float, word: str) -> None:
        self.start = start
        self.end = end
        self.word = word


class FakeSegment:
    def __init__(self, start: float, end: float, text: str, words: list) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class FakeInfo:
    def __init__(self, language: str) -> None:
        self.language = language


class FakeWhisperModel:
    def __init__(self, language: str, segments: list) -> None:
        self._language = language
        self._segments = segments

    def transcribe(self, path, language=None, beam_size=5, word_timestamps=True):
        return list(self._segments), FakeInfo(self._language)


def fake_model(language: str, segments: list) -> FakeWhisperModel:
    """segments: list of {"start", "end", "text", "words": [{"start","end","word"}, ...]}"""
    segs = []
    for seg in segments:
        words = [FakeWord(w["start"], w["end"], w["word"]) for w in seg.get("words", [])]
        segs.append(FakeSegment(seg["start"], seg["end"], seg["text"], words))
    return FakeWhisperModel(language, segs)


def run(*args: str, asr: FakeWhisperModel | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run speech-media's main() in-process, with load_asr_model() replaced by
    a fake WhisperModel when `asr` is given. Returns a
    subprocess.CompletedProcess so stdout/stderr/returncode assertions stay
    the same as a real subprocess invocation."""
    argv = ["speech-media.py", *args]
    stdout, stderr = io.StringIO(), io.StringIO()
    patches = [mock.patch.object(sys, "argv", argv)]
    if asr is not None:
        patches.append(mock.patch.object(MODULE, "load_asr_model", return_value=asr))
    if env:
        patches.append(mock.patch.dict(os.environ, env))
    returncode = 0
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                MODULE.main()
            except SystemExit as exc:
                returncode = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return subprocess.CompletedProcess(argv, returncode, stdout.getvalue(), stderr.getvalue())


def run_subprocess(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run speech-media.py as a REAL subprocess. Only used by the missing-ASR-
    cache test, which must exercise the real (uncached) load_asr_model() path
    with no in-process mock."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=full_env,
    )


def result_of(proc: subprocess.CompletedProcess) -> dict:
    line = next(l for l in proc.stdout.splitlines() if l.startswith("RESULT: "))
    return json.loads(line[len("RESULT: "):])


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True,
                    capture_output=True, text=True)


def ffprobe_audio(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    streams = json.loads(out)["streams"]
    return next(s for s in streams if s.get("codec_type") == "audio")


def make_tone(path: Path, duration: float = 2.0, freq: int = 440, rate: int = 44100) -> None:
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}:sample_rate={rate}",
           "-c:a", "pcm_s16le", str(path))


def make_speechlike(path: Path, duration: float = 3.0) -> None:
    """A multi-harmonic tone with a realistic (non-pure-sine) crest factor."""
    ffmpeg("-f", "lavfi", "-i",
           f"aevalsrc=sin(2*PI*200*t)*0.5+sin(2*PI*800*t)*0.3+sin(2*PI*1600*t)*0.2:s=48000:d={duration}",
           "-c:a", "pcm_s16le", str(path))


def make_silence(path: Path, duration: float = 1.0) -> None:
    ffmpeg("-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={duration}",
           "-c:a", "pcm_s16le", str(path))


def make_pauses(path: Path, tone: float = 0.5, gap: float = 0.5) -> None:
    """silence - tone - silence - tone - silence, to test boundary-only trim."""
    ffmpeg("-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={gap}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={tone}",
           "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={gap}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={tone}",
           "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={gap}",
           "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[out]",
           "-map", "[out]", "-c:a", "pcm_s16le", str(path))


def decoded_sha256(path: Path) -> str:
    import hashlib
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "48000",
         "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"],
        check=True, capture_output=True,
    )
    return hashlib.sha256(proc.stdout).hexdigest()


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not found")
class SpeechMediaTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def path(self, name: str) -> Path:
        return self.root / name


class ReadbackStatusTest(SpeechMediaTestBase):
    def test_exact_match_passes(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual("PASS", result["readback"]["script_match"])
        self.assertEqual("PASS", result["status"])

    def test_exact_text_match_without_words_still_fails(self) -> None:
        """No aligned words means the "match" is unverifiable, even if the
        segment text happens to equal the script character-for-character."""
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world", "words": []}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        result = result_of(proc)
        self.assertEqual("FAIL", result["readback"]["script_match"])

    def test_near_match_warns(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world, how are you today")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world how are you",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        # Tuned to the >=0.85 near-match threshold: this pair's similarity ratio is ~0.88.
        self.assertGreaterEqual(result["readback"]["similarity_ratio"], 0.85)
        self.assertEqual("WARN", result["readback"]["script_match"])
        self.assertTrue(out.exists())  # a WARN bundle is still published

    def test_clear_mismatch_fails_but_still_publishes_candidate(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("completely unrelated content about spreadsheets")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "a totally different sentence",
                                  "words": [{"start": 0.0, "end": 0.5, "word": "a"},
                                            {"start": 0.6, "end": 1.5, "word": "totally"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertNotEqual(0, proc.returncode)
        result = result_of(proc)
        self.assertEqual("FAIL", result["readback"]["script_match"])
        # FAIL still saves a candidate bundle with an explicit status; no success is claimed
        # by the nonzero exit code.
        self.assertTrue(out.exists())
        self.assertTrue((out / "speech_speech.wav").exists())

    def test_japanese_coverage_does_not_hide_latin_omission(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("\u3053\u3093\u306b\u3061\u306f world")  # "konnichiwa world"
        # The ASR result drops the Latin word entirely.
        asr = fake_model("ja", [{"start": 0, "end": 2, "text": "\u3053\u3093\u306b\u3061\u306f",
                                  "words": [{"start": 0.0, "end": 1.0, "word": "\u3053\u3093\u306b\u3061\u306f"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        result = result_of(proc)
        # non_latin_coverage is diagnostic against the TRANSCRIPT (LCS of the script's
        # non-Latin characters found in the transcript), not the script's own
        # composition: here every non-Latin script character is present in the
        # transcript (coverage 1.0), but the Latin-word omission still keeps this
        # below PASS.
        self.assertGreaterEqual(result["readback"]["non_latin_coverage"], 0.5)
        self.assertNotEqual("PASS", result["readback"]["script_match"])


class SilentAudioTest(SpeechMediaTestBase):
    def test_silent_audio_measurement_is_finite_json(self) -> None:
        src = self.path("silent.wav")
        make_silence(src)
        asr = fake_model("en", [])
        proc = run("analyze", str(src), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)  # json.loads already proves it is valid JSON (no NaN/Infinity)
        measure = result["measure"]
        self.assertTrue(measure["all_silent"])
        self.assertIsNone(measure["integrated_lufs"])
        self.assertIsNone(measure["true_peak_db"])
        self.assertIsNone(measure["sample_peak_db"])
        self.assertAlmostEqual(measure["leading_silence"], measure["duration"], delta=0.01)
        self.assertAlmostEqual(measure["trailing_silence"], measure["duration"], delta=0.01)

    def test_normalize_refuses_on_silent_audio(self) -> None:
        src = self.path("silent.wav")
        make_silence(src)
        out = self.path("bundle")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize", asr=asr)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("refusing to normalize", proc.stderr)
        self.assertFalse(out.exists())


class OutputSafetyTest(SpeechMediaTestBase):
    def test_existing_output_directory_refused(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        out.mkdir()
        (out / "keepme.txt").write_text("do not touch")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("must not exist", proc.stderr)
        self.assertEqual(["keepme.txt"], [p.name for p in out.iterdir()])

    def test_symlinked_output_refused(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        real_dir = self.path("elsewhere")
        real_dir.mkdir()
        link = self.path("bundle")
        link.symlink_to(real_dir)
        proc = run("edit", str(src), "--out", str(link), "--operations", "normalize")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("must not exist", proc.stderr)
        self.assertEqual([], list(real_dir.iterdir()))

    def test_output_parent_must_already_exist(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("does-not-exist") / "bundle"
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("output parent directory does not exist", proc.stderr)
        self.assertFalse(out.parent.exists())

    def test_publish_failure_rolls_back_without_partial_output(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        real_rename = Path.rename
        moved_into_out = {"n": 0}

        def flaky_rename(self_path, target):
            # Let the first temp->out move succeed, then fail every subsequent
            # one, so the rollback path in _publish() is exercised
            # deterministically. Rollback renames (out->temp) are untouched.
            target_path = Path(target)
            if target_path.parent == out:
                moved_into_out["n"] += 1
                if moved_into_out["n"] > 1:
                    raise OSError("simulated publish failure")
            return real_rename(self_path, target)

        asr = fake_model("en", [])
        with mock.patch.object(Path, "rename", flaky_rename):
            proc = run("edit", str(src), "--out", str(out), "--operations", "normalize", asr=asr)
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(out.exists())  # rolled back: never left half-published


class ValidationTest(SpeechMediaTestBase):
    def test_slug_path_escape_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--slug", "../evil")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("slug must match", proc.stderr)
        self.assertFalse(out.exists())

    def test_uppercase_slug_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--slug", "Bad_Slug")
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(out.exists())

    def test_nonfinite_target_lufs_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--target-lufs", "nan")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("target-lufs", proc.stderr)
        self.assertFalse(out.exists())

    def test_negative_gap_ms_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), str(src), "--out", str(out), "--operations", "concat",
                   "--gap-ms", "-5")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("gap-ms", proc.stderr)
        self.assertFalse(out.exists())

    def test_speed_out_of_range_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "speed",
                   "--speed", "10")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("speed", proc.stderr)
        self.assertFalse(out.exists())

    def test_unknown_operation_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "bogus")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("unknown operations", proc.stderr)

    def test_duplicate_operation_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize,normalize")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("duplicates", proc.stderr)

    def test_multiple_sources_without_concat_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), str(src), "--out", str(out), "--operations", "normalize")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("concat", proc.stderr)
        self.assertFalse(out.exists())

    def test_too_many_sources_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", *([str(src)] * 65), "--out", str(out), "--operations", "concat")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("64 sources", proc.stderr)
        self.assertFalse(out.exists())

    def test_gap_ms_without_concat_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--gap-ms", "50")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("--gap-ms requires the concat operation", proc.stderr)
        self.assertFalse(out.exists())

    def test_target_lufs_without_normalize_rejected(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "trim",
                   "--target-lufs", "-18")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("--target-lufs requires the normalize operation", proc.stderr)
        self.assertFalse(out.exists())

    def test_source_and_output_unchanged_on_validation_failure(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        before = src.read_bytes()
        out = self.path("bundle")
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--target-lufs", "-100")
        self.assertNotEqual(0, proc.returncode)
        self.assertEqual(before, src.read_bytes())
        self.assertFalse(out.exists())


class MissingAsrCacheTest(SpeechMediaTestBase):
    def test_missing_asr_cache_exits_2_without_partial_output(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        out = self.path("bundle")
        empty_cache = self.path("empty-hf-cache")
        empty_cache.mkdir()
        proc = run_subprocess(
            "track", str(src), "--script-file", str(script), "--out", str(out),
            env={"HF_HOME": str(empty_cache), "HUGGINGFACE_HUB_CACHE": str(empty_cache),
                 "TRANSFORMERS_OFFLINE": "1"},
        )
        self.assertEqual(2, proc.returncode, proc.stderr)
        self.assertFalse(out.exists())


class MasterFormatTest(SpeechMediaTestBase):
    def test_mono_48k_master_and_matching_checksum(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, rate=44100)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        wav_path = out / "speech_speech.wav"
        probed = ffprobe_audio(wav_path)
        self.assertEqual("1", probed["channels"] if isinstance(probed["channels"], str) else str(probed["channels"]))
        self.assertEqual(48000, int(probed["sample_rate"]))
        self.assertEqual(decoded_sha256(wav_path), result["measure"]["pcm_sha256"])
        words_json = json.loads((out / "speech_speech.words.json").read_text())
        self.assertEqual(result["measure"]["pcm_sha256"], words_json["pcm_sha256"])

    def test_measure_reports_actual_master_format_not_source_metadata(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, rate=44100)  # source is 44.1k; the published master is always 48k mono
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual("pcm_s16le", result["measure"]["codec"])
        self.assertEqual(48000, result["measure"]["sample_rate"])
        self.assertEqual(1, result["measure"]["channels"])
        # ... while the input measurement separately preserves the source's own metadata.
        self.assertEqual(44100, result["input_measure"]["sample_rate"])
        self.assertIn("wav", result["derivatives"])

    def test_srt_timestamps_within_duration(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, duration=1.5)
        script = self.path("script.txt")
        script.write_text("hello there friend, this is a longer caption line to wrap")
        asr = fake_model("en", [{"start": 0, "end": 1.5,
                                  "text": "hello there friend this is a longer caption line to wrap",
                                  "words": [{"start": 0.0, "end": 1.4, "word": "hello"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        captions = json.loads((out / "speech_speech.words.json").read_text())["captions"]
        self.assertTrue(captions)
        for cap in captions:
            self.assertLessEqual(cap["end"], 1.5 + 0.01)
            self.assertGreaterEqual(cap["start"], 0.0)
        srt_text = (out / "speech_speech.srt").read_text()
        self.assertIn("-->", srt_text)


class VoiceMessageTest(SpeechMediaTestBase):
    def test_voice_message_produces_a_real_ogg_derivative(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out),
                   "--voice-message", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        ogg_path = out / "speech_speech.ogg"
        self.assertTrue(ogg_path.exists())
        probed = ffprobe_audio(ogg_path)
        self.assertEqual("opus", probed["codec_name"])
        # measured/decoded, not just declared present
        self.assertIn("ogg", result["derivatives"])
        self.assertGreater(result["derivatives"]["ogg"]["duration"], 0)
        words_json = json.loads((out / "speech_speech.words.json").read_text())
        self.assertEqual("speech_speech.ogg", words_json["voice_message_file"])

    def test_convert_to_wav_is_a_noop_not_an_error(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "convert",
                   "--format", "wav", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        # No extra derivative beyond the master itself.
        self.assertEqual(["wav"], list(result["derivatives"].keys()))
        self.assertEqual(
            {"speech_speech.wav", "speech_speech.words.json", "speech_speech.srt",
             "speech_speech.take.json"},
            {p.name for p in out.iterdir()},
        )


class NormalizeTest(SpeechMediaTestBase):
    def test_normalize_hits_target_lufs_and_true_peak_ceiling(self) -> None:
        src = self.path("speechlike.wav")
        make_speechlike(src)
        out = self.path("bundle")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--target-lufs", "-16", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertAlmostEqual(-16, result["measure"]["integrated_lufs"], delta=0.7)
        self.assertLessEqual(result["measure"]["true_peak_db"], -0.7)

    def test_normalize_hits_alternate_target_lufs(self) -> None:
        """Two-pass loudnorm must measure at the REQUESTED target (not a
        hardcoded -16) for the second pass to land accurately at other
        targets too."""
        src = self.path("speechlike.wav")
        make_speechlike(src)
        out = self.path("bundle")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "normalize",
                   "--target-lufs", "-20", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertAlmostEqual(-20, result["measure"]["integrated_lufs"], delta=0.7)
        self.assertLessEqual(result["measure"]["true_peak_db"], -0.7)

    def test_normalize_preserves_duration_and_reuses_the_sidecar(self) -> None:
        """normalize does not touch timing (it is not in the trim/speed set
        that forces re-transcription), so a previously-tracked sidecar must
        both be reused AND still describe the same duration afterward."""
        src = self.path("tone.wav")
        make_tone(src, duration=2.0)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        tracked = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(tracked), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        original_duration = result_of(proc)["measure"]["duration"]

        out = self.path("normalized")
        proc = run("edit", str(tracked / "speech_speech.wav"), "--out", str(out),
                   "--operations", "normalize", "--target-lufs", "-18")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["sidecars_reused"])
        self.assertAlmostEqual(original_duration, result["measure"]["duration"], delta=0.01)


class DerivativeTest(SpeechMediaTestBase):
    def test_mp3_derivative_is_measured_and_decodable(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        out = self.path("bundle")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "convert",
                   "--format", "mp3", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        mp3_path = out / "speech_speech.mp3"
        self.assertTrue(mp3_path.exists())
        probed = ffprobe_audio(mp3_path)
        self.assertEqual("mp3", probed["codec_name"])
        self.assertIn("mp3", result["derivatives"])
        self.assertGreater(result["derivatives"]["mp3"]["duration"], 0)

    def test_multichannel_source_input_measure_distinct_from_mono_master(self) -> None:
        src = self.path("stereo.wav")
        # Upmix a mono sine to a genuinely 2-channel source.
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ac", "2", str(src))
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertEqual(2, result["input_measure"]["channels"])
        self.assertEqual(1, result["measure"]["channels"])
        self.assertIn("downmix_note", result["measure"])


class ConcatTest(SpeechMediaTestBase):
    def _tracked(self, slug: str, text: str, words: list) -> Path:
        src = self.path(f"{slug}-src.wav")
        make_tone(src)
        script = self.path(f"{slug}-script.txt")
        script.write_text(text)
        asr = fake_model("en", [{"start": 0, "end": 2, "text": text, "words": words}])
        out = self.path(f"{slug}-bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out),
                   "--slug", slug, asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return out / f"speech_{slug}.wav"

    def test_concat_preserves_offsets_order_and_gap(self) -> None:
        first = self._tracked("first", "hello world",
                               [{"start": 0.0, "end": 0.8, "word": "hello"},
                                {"start": 0.9, "end": 1.8, "word": "world"}])
        second = self._tracked("second", "goodbye now",
                                [{"start": 0.0, "end": 0.8, "word": "goodbye"},
                                 {"start": 0.9, "end": 1.8, "word": "now"}])
        out = self.path("combined")
        proc = run("edit", str(first), str(second), "--out", str(out),
                   "--operations", "concat", "--gap-ms", "100")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["sidecars_reused"])
        words = json.loads((out / "speech_speech.words.json").read_text())["words"]
        self.assertEqual(["hello", "world", "goodbye", "now"], [w["word"] for w in words])
        # The second track's words are shifted by the first track's duration + the gap.
        self.assertAlmostEqual(words[2]["start"], 2.1, delta=0.05)
        self.assertAlmostEqual(result["measure"]["duration"], 4.1, delta=0.05)

    def test_explicit_new_script_on_reuse_rebuilds_captions(self) -> None:
        """When sidecars are reused (no timing change) but the caller supplies
        a NEW --script-file, captions must be rebuilt against that new script
        rather than reusing the inherited captions (which were built from the
        old script's text)."""
        first = self._tracked("firstb", "hello world",
                               [{"start": 0.0, "end": 0.8, "word": "hello"},
                                {"start": 0.9, "end": 1.8, "word": "world"}])
        second = self._tracked("secondb", "goodbye now",
                                [{"start": 0.0, "end": 0.8, "word": "goodbye"},
                                 {"start": 0.9, "end": 1.8, "word": "now"}])
        new_script = self.path("new-script.txt")
        new_script.write_text("a brand new caption script")
        out = self.path("combined")
        proc = run("edit", str(first), str(second), "--out", str(out),
                   "--operations", "concat", "--script-file", str(new_script))
        # The new script legitimately mismatches the inherited transcript
        # ("hello world goodbye now"), so this is a correct FAIL/exit-1, not
        # a crash; the bundle (with rebuilt captions) is still published.
        result = result_of(proc)
        self.assertTrue(out.exists())
        self.assertTrue(result["sidecars_reused"])
        words_json = json.loads((out / "speech_speech.words.json").read_text())
        self.assertEqual("a brand new caption script", words_json["script"])
        captions_text = " ".join(c["text"] for c in words_json["captions"])
        self.assertIn("brand new caption script", captions_text)

    def test_stale_sidecar_is_rejected_not_silently_reused(self) -> None:
        first = self._tracked("firsta", "hello world",
                               [{"start": 0.0, "end": 0.8, "word": "hello"},
                                {"start": 0.9, "end": 1.8, "word": "world"}])
        second = self._tracked("seconda", "goodbye now",
                                [{"start": 0.0, "end": 0.8, "word": "goodbye"},
                                 {"start": 0.9, "end": 1.8, "word": "now"}])
        sidecar = second.parent / "speech_seconda.words.json"
        data = json.loads(sidecar.read_text())
        data["duration"] = 999.0  # corrupt it so it can no longer be trusted
        sidecar.write_text(json.dumps(data))
        out = self.path("combined")
        proc = run("edit", str(first), str(second), "--out", str(out), "--operations", "concat")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("duration does not match", proc.stderr)
        self.assertFalse(out.exists())

    def test_missing_sidecar_falls_back_to_asr(self) -> None:
        """A MISSING sidecar (as opposed to an existing-but-invalid one) is
        the one case that legitimately falls back to re-transcription."""
        src = self.path("plain.wav")
        make_tone(src)
        out = self.path("bundle")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "now"}]}])
        proc = run("edit", str(src), "--out", str(out), "--operations", "trim", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertFalse(result["sidecars_reused"])

    def test_edit_on_voice_message_ogg_falls_back_to_asr_not_the_wav_sidecar(self) -> None:
        """<stem>.words.json is looked up by stem, so an .ogg voice-message
        derivative published next to its .wav master shares that sidecar's
        path on disk -- but the sidecar names the .wav, not the .ogg. That
        must be treated as "no sidecar for this file" (fall back to ASR),
        never as a malformed/stale sidecar for the .ogg."""
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        track_asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                        "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                                  {"start": 0.9, "end": 1.8, "word": "world"}]}])
        tracked = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(tracked),
                   "--voice-message", asr=track_asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        ogg = tracked / "speech_speech.ogg"
        self.assertTrue(ogg.exists())

        edit_asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                       "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                                 {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("edited")
        proc = run("edit", str(ogg), "--out", str(out), "--operations", "normalize",
                   "--target-lufs", "-18", asr=edit_asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertFalse(result["sidecars_reused"])  # the .wav's sidecar is not this file's own


class SidecarStrictnessTest(SpeechMediaTestBase):
    def test_interval_beyond_actual_duration_rejected_even_within_declared_tolerance(self) -> None:
        """Intervals must validate against the ACTUAL decoded duration, not
        the sidecar's declared "duration" field (which is itself only
        checked to within SIDECAR_DURATION_TOLERANCE=.15s of the truth): a
        word ending only within that .15s slack of the declared value could
        otherwise land past the real audio boundary and spill into a
        concatenated successor's timeline."""
        src = self.path("tone.wav")
        make_tone(src, duration=2.0)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        tracked = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(tracked), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        actual_duration = result_of(proc)["measure"]["duration"]

        sidecar = tracked / "speech_speech.words.json"
        data = json.loads(sidecar.read_text())
        # Inflate the declared duration by .1s (still inside the .15s sidecar
        # tolerance) and push a word .1s past the ACTUAL decoded duration.
        data["duration"] = actual_duration + 0.1
        data["words"][-1]["end"] = actual_duration + 0.1
        sidecar.write_text(json.dumps(data))

        out = self.path("edited")
        proc = run("edit", str(tracked / "speech_speech.wav"), "--out", str(out),
                   "--operations", "normalize", "--target-lufs", "-18")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("interval out of range", proc.stderr)
        self.assertFalse(out.exists())

    def test_overlapping_asr_segments_are_clamped_so_the_sidecar_reuses_cleanly(self) -> None:
        """Segments get the same monotonic prev_end clamp as words: ASR is
        not guaranteed to return non-overlapping segments, and an
        overlapping segment surviving into a published sidecar would fail
        strict interval validation the next time that sidecar is reused."""
        src = self.path("tone.wav")
        make_tone(src, duration=3.0)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [
            {"start": 0.0, "end": 2.0, "text": "hello",
             "words": [{"start": 0.0, "end": 1.8, "word": "hello"}]},
            {"start": 1.5, "end": 3.0, "text": "world",  # overlaps the segment above by .5s
             "words": [{"start": 1.6, "end": 2.9, "word": "world"}]},
        ])
        tracked = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(tracked), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        segments = json.loads((tracked / "speech_speech.words.json").read_text())["segments"]
        for a, b in zip(segments, segments[1:]):
            self.assertLessEqual(a["end"], b["start"] + 0.001)

        out = self.path("edited")
        proc = run("edit", str(tracked / "speech_speech.wav"), "--out", str(out),
                   "--operations", "normalize", "--target-lufs", "-18")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["sidecars_reused"])


class TranscribeCleaningTest(SpeechMediaTestBase):
    def test_word_that_rounds_to_zero_duration_is_dropped(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, duration=2.0)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            # rounds to 0.900/0.900 -- zero-width post-rounding
                                            {"start": 0.9001, "end": 0.9004, "word": "glitch"},
                                            {"start": 1.0, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        words = json.loads((out / "speech_speech.words.json").read_text())["words"]
        self.assertEqual(["hello", "world"], [w["word"] for w in words])

    def test_leading_space_word_stripped_for_char_mapping_but_word_text_preserved(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, duration=2.0)
        script = self.path("script.txt")
        script.write_text("hello world")
        asr = fake_model("en", [{"start": 0, "end": 2, "text": " hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": " hello"},
                                            {"start": 0.9, "end": 1.8, "word": " world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        words_json = json.loads((out / "speech_speech.words.json").read_text())
        # The actual ASR word text (with its leading-space token artifact) is
        # preserved verbatim in the reported words -- only the char-mapping
        # used internally for caption timing strips it.
        self.assertEqual(" hello", words_json["words"][0]["word"])
        captions = words_json["captions"]
        self.assertTrue(captions)
        # A single short caption chunk covering "hello world" should start
        # near 0.0 (hello's start), not skewed later by counting each word's
        # un-stripped leading space as an extra character.
        self.assertLess(captions[0]["start"], 0.3)


class CapEnforcementTest(SpeechMediaTestBase):
    """MAX_MEDIA_SECONDS is monkeypatched down to a couple of seconds so these
    exercise the same cap-enforcement code paths as a real 600s+ file would,
    without needing slow, real long-duration fixtures."""

    def test_decode_pcm_rejects_when_actual_length_exceeds_the_cap(self) -> None:
        # Direct unit test of the decode-time safety net: even independent of
        # probe()'s own (metadata-based) duration check, decode_pcm() itself
        # must refuse to silently hand back a cap-truncated buffer.
        src = self.path("tone.wav")
        make_tone(src, duration=3)
        info = MODULE.probe(str(src))
        with self.assertRaises(ValueError) as ctx:
            MODULE.decode_pcm(info["path"], info["audio_index"], max_seconds=1)
        self.assertIn("1s media cap", str(ctx.exception))

    def test_decode_pcm_accepts_audio_under_the_cap(self) -> None:
        src = self.path("tone.wav")
        make_tone(src, duration=1)
        info = MODULE.probe(str(src))
        pcm, samples = MODULE.decode_pcm(info["path"], info["audio_index"], max_seconds=5)
        self.assertGreater(len(samples), 0)
        self.assertEqual(len(pcm), len(samples) * 2)

    def test_aggregate_input_over_small_cap_rejected(self) -> None:
        first = self.path("first.wav")
        second = self.path("second.wav")
        make_tone(first, duration=1.5)
        make_tone(second, duration=1.5)
        out = self.path("bundle")
        with mock.patch.object(MODULE, "MAX_MEDIA_SECONDS", 2):
            proc = run("edit", str(first), str(second), "--out", str(out), "--operations", "concat")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("media cap", proc.stderr)
        self.assertFalse(out.exists())

    def test_speed_slowdown_rejected_before_atempo_when_over_small_cap(self) -> None:
        # 1.6s / 0.5x speed = 3.2s, over a 2s cap -- must be rejected BEFORE
        # apply_speed() runs, not only after measuring the (already-produced)
        # oversized output.
        src = self.path("tone.wav")
        make_tone(src, duration=1.6)
        out = self.path("bundle")
        with mock.patch.object(MODULE, "MAX_MEDIA_SECONDS", 2):
            proc = run("edit", str(src), "--out", str(out), "--operations", "speed", "--speed", "0.5")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("post-speed output would exceed", proc.stderr)
        self.assertFalse(out.exists())


class TimingChangeTest(SpeechMediaTestBase):
    def test_speed_forces_reasr_instead_of_sidecar_reuse(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        track_asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                        "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                                  {"start": 0.9, "end": 1.8, "word": "world"}]}])
        tracked = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(tracked), asr=track_asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        wav = tracked / "speech_speech.wav"

        edit_asr = fake_model("en", [{"start": 0, "end": 1, "text": "sped up speech",
                                       "words": [{"start": 0.0, "end": 0.4, "word": "sped"}]}])
        out = self.path("sped")
        proc = run("edit", str(wav), "--out", str(out), "--operations", "speed",
                   "--speed", "2.0", asr=edit_asr)
        # Re-transcription (not the inherited sidecar's "hello world") mismatches the
        # inherited script here, which is a correct FAIL/exit-1, not a crash.
        result = result_of(proc)
        self.assertFalse(result["sidecars_reused"])
        transcript = json.loads((out / "speech_speech.words.json").read_text())["transcript"]
        self.assertEqual("sped up speech", transcript)
        self.assertAlmostEqual(result["measure"]["duration"], 1.0, delta=0.1)

    def test_trim_preserves_internal_pause(self) -> None:
        src = self.path("pauses.wav")
        make_pauses(src, tone=0.5, gap=0.5)  # 0.5s silence, 0.5s tone, 0.5s silence, 0.5s tone, 0.5s silence
        out = self.path("trimmed")
        asr = fake_model("en", [])
        proc = run("edit", str(src), "--out", str(out), "--operations", "trim", asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = result_of(proc)
        # Only the leading/trailing 0.5s are removed; the interior 0.5s pause survives.
        self.assertAlmostEqual(result["measure"]["duration"], 1.5, delta=0.05)


class TakeEvidenceTest(SpeechMediaTestBase):
    def test_take_json_separates_output_and_source_hashes_and_preserves_raw_evidence(self) -> None:
        src = self.path("tone.wav")
        make_tone(src)
        script = self.path("script.txt")
        script.write_text("hello world")
        take_file = self.path("take.json")
        take_file.write_text(json.dumps({"voice": "narrator-1", "id": "take-42", "engine": "acme-tts"}))
        asr = fake_model("en", [{"start": 0, "end": 2, "text": "hello world",
                                  "words": [{"start": 0.0, "end": 0.8, "word": "hello"},
                                            {"start": 0.9, "end": 1.8, "word": "world"}]}])
        out = self.path("bundle")
        proc = run("track", str(src), "--script-file", str(script), "--out", str(out),
                   "--take-file", str(take_file), asr=asr)
        self.assertEqual(0, proc.returncode, proc.stderr)
        take_json = json.loads((out / "speech_speech.take.json").read_text())
        self.assertIsInstance(take_json["pcm_sha256"], str)
        self.assertIsInstance(take_json["source_pcm_sha256"], list)
        self.assertEqual(take_json["pcm_sha256"], take_json["source_pcm_sha256"][0])
        self.assertEqual("narrator-1", take_json["voice"])
        # The raw supplied evidence is preserved verbatim, including fields
        # (like "id") that are not individually surfaced.
        self.assertEqual("take-42", take_json["evidence"]["id"])
        self.assertEqual("acme-tts", take_json["evidence"]["engine"])


if __name__ == "__main__":
    unittest.main()
