"""Real ffmpeg fixtures and subprocess CLI tests; no network or ASR."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "profiles/audio-creator/skills/audio-creator-pipeline/scripts/sfx-media.py"
KINDS = ("click", "beep", "chime", "whoosh", "riser", "pop", "ui-tick", "noise-burst")
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe required")


def cli(*args, env=None):
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=120, env=env)
    lines = proc.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("RESULT: "), (proc.stdout, proc.stderr)
    result = json.loads(lines[0][8:], parse_constant=lambda s: pytest.fail(f"nonfinite JSON {s}"))
    assert (proc.returncode != 0) == (result["status"] == "FAIL"), result
    return result


def fixture(path, expression="0.25*sin(2*PI*880*t)", seconds=.5, rate=48000, codec="pcm_s16le"):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    f"aevalsrc={expression}:s={rate}:d={seconds}", "-c:a", codec, str(path)],
                   capture_output=True, check=True)
    return path


def pcm(path):
    with wave.open(str(path), "rb") as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").reshape(-1, f.getnchannels())


def take(result):
    return json.loads(Path(result["master"]).with_suffix(".take.json").read_text())


def module():
    spec = importlib.util.spec_from_file_location("sfx_media", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("kind", KINDS)
def test_all_kinds_repeat_pcm(tmp_path, kind):
    results = [cli("synth", "--kind", kind, "--seconds", ".15", "--seed", "57",
                   "--out", tmp_path / str(i)) for i in range(2)]
    a, b = results
    assert a["status"] == "WARN"  # Short LUFS is deliberately null, not failure.
    assert a["pcm_sha256"] == b["pcm_sha256"]
    assert np.array_equal(pcm(a["master"]), pcm(b["master"]))
    m = a["measure"]
    assert (m["channels"], m["sample_rate"], m["codec"], m["frames"]) == (1, 48000, "pcm_s16le", 7200)
    assert m["sample_peak_dbfs"] == pytest.approx(-6, abs=.002)
    assert m["integrated_lufs"] is None and m["clipping_count"] == 0
    assert abs(pcm(a["master"])[[0, -1]]).max() == 0
    sidecar = take(a)
    assert sidecar["recipe_version"] == 1 and sidecar["seed"] == 57
    assert sidecar["rng"] == "numpy.PCG64"
    assert "synth master decoded PCM" in sidecar["determinism"]
    assert all(sidecar["versions"][v] for v in ("numpy", "ffmpeg", "ffprobe"))
    assert m["boundary_sample_deltas"]["verification"] == "NOT seamless-loop verification"
    assert m["auditory_quality"] == "unverified"


def test_seed_changes_noise(tmp_path):
    a, b = [cli("synth", "--kind", "whoosh", "--seconds", ".1", "--seed", seed,
                "--out", tmp_path / seed) for seed in ("0", "4294967295")]
    assert a["pcm_sha256"] != b["pcm_sha256"]


@pytest.mark.parametrize("seconds,pitch", [("0.01", "40"), ("22", "8000")])
def test_synth_inclusive_bounds(tmp_path, seconds, pitch):
    r = cli("synth", "--kind", "beep", "--seconds", seconds, "--pitch", pitch, "--out", tmp_path / "out")
    assert r["status"] != "FAIL"
    assert r["measure"]["duration_seconds"] == float(seconds)


def test_antiphase_track_resamples_preserving_evidence_and_source(tmp_path):
    src = fixture(tmp_path / "stereo.wav", "0.25*sin(2*PI*440*t)|-0.25*sin(2*PI*440*t)", rate=44100)
    original = src.read_bytes()
    evidence = {"seed": 17, "provider": "example", "nested": {"unknown": [True, None, "keep"]}}
    ev = tmp_path / "take.json"
    ev.write_text(json.dumps(evidence))
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"  Exact prompt\r\nwith spacing.\n")
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "stereo", "--take-file", ev, "--prompt-file", prompt)
    assert r["status"] == "PASS"
    assert r["measure"]["channels"] == 2 and r["measure"]["sample_rate"] == 48000
    assert r["measure"]["frames"] == 24000 and r["measure"]["codec"] == "pcm_s16le"
    assert np.max(np.abs(pcm(r["master"]).astype(float).mean(axis=1))) <= 1
    assert np.max(np.abs(pcm(r["master"]))) > 8000
    assert src.read_bytes() == original
    assert r["source"]["sha256"] == hashlib.sha256(original).hexdigest()
    native = r["source"]["measure"]
    assert native["sample_rate"] == 44100 and native["frames"] == 22050
    assert native["pcm_sha256"] == hashlib.sha256((pcm(src) / 32768).astype("<f4").tobytes()).hexdigest()
    assert native == cli("analyze", src)["measure"]
    assert native["pcm_sha256"] != r["pcm_sha256"]
    assert "determinism" not in take(r)
    assert take(r)["evidence"] == evidence
    assert (Path(r["out"]) / "prompt.txt").read_bytes() == prompt.read_bytes()
    assert len(r["measure"]["dc_offset_per_channel"]) == 2


@pytest.mark.parametrize("operation,controls,frames", [
    ("track", [], 24000),
    ("edit", ["--start", ".1", "--end", ".4", "--pitch-semitones", "12", "--pad-ms", "50"], 12000),
])
def test_default_slug_and_resampling_before_edits(tmp_path, operation, controls, frames):
    src = fixture(tmp_path / "stereo.wav", "0.25*sin(2*PI*440*t)|-0.25*sin(2*PI*440*t)", rate=44100)
    original = src.read_bytes()
    r = cli(operation, src, "--out", tmp_path / "out", *controls)
    assert r["status"] != "FAIL"
    assert Path(r["master"]).name == "sfx_sfx.wav"
    assert r["controls"]["slug"] == "sfx"
    assert r["measure"]["sample_rate"] == 48000 and r["measure"]["channels"] == 2
    assert r["measure"]["codec"] == "pcm_s16le" and r["measure"]["frames"] == frames
    assert r["source"]["measure"] == cli("analyze", src)["measure"]
    assert r["source"]["measure"]["sample_rate"] == 44100
    assert r["source"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert src.read_bytes() == original
    assert "determinism" not in take(r)
    if operation == "edit":
        assert r["edit"]["pitch_rate"] == 96000


@pytest.mark.parametrize("rate", [44100, 96000])
@pytest.mark.parametrize("seconds", [22, 22.001])
@pytest.mark.parametrize("operation", ["track", "edit"])
def test_resampled_duration_bound(tmp_path, rate, seconds, operation):
    src = fixture(tmp_path / "source.wav", rate=rate, seconds=seconds)
    controls = ["--reverse"] if operation == "edit" else []
    r = cli(operation, src, "--out", tmp_path / "out", *controls)
    if seconds > 22:
        assert r["status"] == "FAIL" and not (tmp_path / "out").exists()
    else:
        assert r["status"] != "FAIL"
        assert r["source"]["measure"]["frames"] == rate * 22
        assert r["measure"]["sample_rate"] == 48000 and r["measure"]["frames"] == 48000 * 22


def test_track_keeps_source_clipping_failure_after_resampling(tmp_path):
    src = fixture(tmp_path / "clipped.wav", "eq(n\\,1000)", rate=96000)
    r = cli("track", src, "--out", tmp_path / "out")
    assert r["source"]["measure"]["clipping_count"] == 1
    assert r["source"]["measure"]["status"] == "FAIL"
    assert r["measure"]["clipping_count"] == 0 and r["measure"]["status"] != "FAIL"
    assert r["status"] == "FAIL" and r["diagnostic_candidate"]
    assert take(r)["source"]["measure"] == cli("analyze", src)["measure"]


@pytest.mark.parametrize("expression,reason", [("0", "silence"), ("2*sin(2*PI*440*t)", "clipping")])
def test_quality_failures_retained_and_analyze_no_delivery(tmp_path, expression, reason):
    src = fixture(tmp_path / "bad.wav", expression)
    before = set(tmp_path.iterdir())
    analysis = cli("analyze", src)
    assert analysis["status"] == "FAIL"
    assert set(tmp_path.iterdir()) == before
    assert reason in " ".join(analysis["measure"]["failures"])
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "bad")
    assert r["status"] == "FAIL" and r["diagnostic_candidate"]
    assert Path(r["master"]).is_file() and take(r)["status"] == "FAIL"


def test_float_overrange_not_hidden_by_quantization(tmp_path):
    src = fixture(tmp_path / "float.wav", "1.2*sin(2*PI*440*t)", codec="pcm_f32le")
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "float")
    assert r["status"] == "FAIL"
    assert r["source"]["measure"]["sample_peak_dbfs"] > 0
    assert r["measure"]["clipping_count"] > 0


def test_positive_24bit_clipping_is_counted(tmp_path):
    src = fixture(tmp_path / "clipped.wav", "1", codec="pcm_s24le")
    r = cli("analyze", src)
    assert r["status"] == "FAIL"
    assert r["measure"]["clipping_count"] == 24000


def test_stereo_one_silent_channel_and_dc_estimate(tmp_path):
    src = fixture(tmp_path / "stereo.wav", "0|0.02+0.2*sin(2*PI*440*t)")
    r = cli("analyze", src)
    assert r["status"] == "PASS"
    assert r["measure"]["dc_offset_per_channel"] == pytest.approx([0, .02], abs=.0001)


def test_decode_cap_does_not_trust_container_duration(tmp_path):
    src = fixture(tmp_path / "misleading.flac", seconds=22.02, codec="flac")
    raw = bytearray(src.read_bytes())
    # FLAC STREAMINFO packs total_samples into the low 36 bits at offset 18.
    field = int.from_bytes(raw[18:26], "big")
    raw[18:26] = ((field & ~((1 << 36) - 1)) | 24000).to_bytes(8, "big")
    src.write_bytes(raw)
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "long")
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()
    assert "22" in r["error"]


@pytest.mark.parametrize("option,value", [
    ("--seconds", "0"), ("--seconds", "22.001"), ("--seconds", "nan"),
    ("--seconds", "inf"), ("--seconds", "true"), ("--pitch", "39"),
    ("--pitch", "8001"), ("--pitch", "NaN"), ("--pitch", "false"),
    ("--seed", "-1"), ("--seed", "4294967296"), ("--seed", "1.5"),
    ("--seed", "True"), ("--seed", "nan"), ("--slug", "../escape"),
    ("--slug", "a\nb"), ("--kind", "music"),
])
def test_invalid_synth_no_output(tmp_path, option, value):
    out = tmp_path / "out"
    r = cli("synth", "--kind", "beep", "--seconds", ".1", "--out", out, option, value)
    assert r["status"] == "FAIL" and not out.exists()


@pytest.mark.parametrize("option,value", [
    ("--start", "-1"), ("--start", "nan"), ("--end", "inf"),
    ("--pad-ms", "10001"), ("--pad-ms", "true"), ("--pad-ms", "1.5"),
    ("--fade-in-ms", "-1"), ("--fade-out-ms", "22001"),
    ("--pitch-semitones", "-25"), ("--pitch-semitones", "25"),
    ("--pitch-semitones", "nan"), ("--target-peak", "-31"),
    ("--target-peak", "0"), ("--target-peak", "false"), ("--format", "flac"),
])
def test_invalid_edit_controls(tmp_path, option, value):
    out = tmp_path / "out"
    r = cli("edit", tmp_path / "missing.wav", "--out", out, "--slug", "bad", option, value)
    assert r["status"] == "FAIL" and not out.exists()


@pytest.mark.parametrize("controls", [[], ["--start", ".5"], ["--end", "0"], ["--end", "1"],
                                     ["--fade-in-ms", "501"], ["--start", ".000001", "--end", ".000002"]])
def test_invalid_edit_intervals_no_bundle(tmp_path, controls):
    src = fixture(tmp_path / "tone.wav")
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "bad", *controls)
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


@pytest.mark.parametrize("mode", ["empty", "directory", "symlink", "large", "long", "channels", "corrupt", "remote-playlist"])
def test_invalid_sources(tmp_path, mode):
    src = tmp_path / "input.wav"
    if mode == "empty":
        src.touch()
    elif mode == "directory":
        src.mkdir()
    elif mode == "symlink":
        src.symlink_to(fixture(tmp_path / "target.wav"))
    elif mode == "large":
        with src.open("wb") as f:
            f.truncate(16 * 1024 * 1024 + 1)
    elif mode == "long":
        fixture(src, seconds=22.02)
    elif mode == "channels":
        fixture(src, "0.1*sin(t)|0.1*cos(t)|0.1*sin(2*t)")
    elif mode == "remote-playlist":
        src.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttps://127.0.0.1:9/audio.ts\n#EXT-X-ENDLIST\n")
    else:
        fixture(src)
        src.write_bytes(src.read_bytes()[:-111])
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "invalid")
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


@pytest.mark.parametrize("mode", ["existing-empty", "existing-files", "symlink", "dangling", "missing-parent", "source"])
def test_exclusive_output_and_source_unchanged(tmp_path, mode):
    src = fixture(tmp_path / "source.wav")
    raw = src.read_bytes()
    out = tmp_path / "out"
    if mode.startswith("existing"):
        out.mkdir()
        if mode == "existing-files":
            (out / "keep").write_text("untouched")
    elif mode in ("symlink", "dangling"):
        out.symlink_to(tmp_path / ("source.wav" if mode == "symlink" else "missing"))
    elif mode == "missing-parent":
        out = tmp_path / "missing" / "out"
    else:
        out = src
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    r = cli("track", src, "--out", out, "--slug", "safe")
    assert r["status"] == "FAIL" and src.read_bytes() == raw
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


def test_publish_race_refuses_existing_empty_directory(tmp_path):
    candidate, out = tmp_path / "candidate", tmp_path / "out"
    candidate.mkdir()
    (candidate / "file").write_text("complete")
    out.mkdir()
    with pytest.raises(OSError):
        module().publish(candidate, out)
    assert list(out.iterdir()) == [] and (candidate / "file").read_text() == "complete"


def test_trim_pad_fades_and_order(tmp_path):
    src = fixture(tmp_path / "source.wav", seconds=1)
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "edited", "--start", ".1", "--end", ".7",
            "--pad-ms", "100", "--fade-in-ms", "200", "--fade-out-ms", "200")
    assert r["status"] != "FAIL"
    assert r["measure"]["duration_seconds"] == pytest.approx(.8)
    samples = pcm(r["master"])
    assert not samples[:4800].any() and not samples[-4800:].any()
    assert np.max(np.abs(samples[4800:6000])) < 5200
    assert r["edit"]["order"] == ["trim", "pitch", "reverse", "pad", "fade", "peak-normalize", "convert"]
    assert r["measure"]["silence_estimate"]["head_seconds"] == pytest.approx(.1, abs=.001)


@pytest.mark.parametrize("semitones,duration", [(12, .25), (-12, 1), (24, .125), (-24, 2)])
def test_pitch_changes_duration(tmp_path, semitones, duration):
    src = fixture(tmp_path / "source.wav")
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "pitch", "--pitch-semitones", semitones)
    assert r["status"] != "FAIL"
    assert r["measure"]["duration_seconds"] == pytest.approx(duration, abs=.001)
    assert "no tempo preservation" in r["edit"]["pitch_method"]
    assert r["edit"]["pitch_duration_ratio"] == pytest.approx(2 ** (-semitones / 12))
    samples = pcm(r["master"])[:, 0]
    frequency = np.fft.rfftfreq(len(samples), 1 / 48000)[np.abs(np.fft.rfft(samples)).argmax()]
    assert frequency == pytest.approx(880 * 2 ** (semitones / 12), abs=8)


def test_reverse_exact_stereo(tmp_path):
    src = fixture(tmp_path / "source.wav", "0.25*sin(2*PI*440*t)|-0.25*sin(2*PI*440*t)")
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "reverse", "--reverse")
    assert r["status"] != "FAIL" and np.array_equal(pcm(r["master"]), pcm(src)[::-1])


@pytest.mark.parametrize("controls", [["--pad-ms", "1000"], ["--pitch-semitones", "-12"]])
def test_actual_edit_cap_no_truncation(tmp_path, controls):
    src = fixture(tmp_path / "long.wav", seconds=21)
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "long", *controls)
    assert r["status"] == "FAIL" and "22" in r["error"]
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("seconds,target", [(.01, -6), (.5, -1), (.5, -30)])
def test_normalization_quantized_true_peak(tmp_path, seconds, target):
    src = fixture(tmp_path / "quiet.wav", "0.015*sin(2*PI*8000*t)", seconds=seconds)
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "peak", "--target-peak", target)
    assert r["status"] != "FAIL", r
    assert r["measure"]["true_peak_dbtp"] == pytest.approx(target, abs=.1)
    assert r["edit"]["gain_db"] > 0
    analysis = cli("analyze", r["master"])
    assert analysis["measure"] == r["measure"]


def test_silent_normalize_retains_failure(tmp_path):
    src = fixture(tmp_path / "silent.wav", "0")
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "silent", "--target-peak", "-6")
    assert r["status"] == "FAIL" and Path(r["master"]).is_file()


@pytest.mark.parametrize("fmt", ["mp3", "ogg"])
@pytest.mark.parametrize("seconds", [.01, .5, 22])
def test_derivatives_measured_independently(tmp_path, fmt, seconds):
    src = fixture(tmp_path / "stereo.wav", "0.25*sin(2*PI*440*t)|-0.25*sin(2*PI*440*t)", seconds=seconds)
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "lossy", "--format", fmt)
    assert r["status"] != "FAIL"
    path = Path(r["out"]) / f"sfx_lossy.{fmt}"
    dm = r["derivatives"][path.name]
    assert dm["channels"] == 2 and dm["pcm_sha256"] != r["pcm_sha256"]
    assert dm["codec"] == ("mp3" if fmt == "mp3" else "opus")
    assert cli("analyze", path)["measure"] == dm
    assert take(r)["derivatives"][path.name] == dm


def test_derivative_peak_mismatch_is_visible_failure(tmp_path):
    src = fixture(tmp_path / "tone.wav", "0.5*eq(n\\,1000)", seconds=.1)
    r = cli("edit", src, "--out", tmp_path / "out", "--slug", "lossy", "--format", "mp3", "--target-peak", "-6")
    dm = r["derivatives"]["sfx_lossy.mp3"]
    assert abs(dm["true_peak_dbtp"] + 6) > .1
    assert r["measure"]["status"] != "FAIL"
    assert r["status"] == "FAIL" and r["diagnostic_candidate"]
    assert dm["status"] == "FAIL" and dm["failures"]
    assert Path(r["out"], "sfx_lossy.mp3").exists()


@pytest.mark.parametrize("content", ["[]", "true", '{"seed": NaN}', '{"seed": 1e999}', "{"])
def test_invalid_take_no_output(tmp_path, content):
    src = fixture(tmp_path / "tone.wav")
    evidence = tmp_path / "take.json"
    evidence.write_text(content)
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "bad", "--take-file", evidence)
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


def test_invalid_utf8_prompt_no_output(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"\xff")
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "bad", "--prompt-file", prompt)
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


def test_empty_utf8_prompt_copied(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    prompt = tmp_path / "prompt.txt"
    prompt.touch()
    r = cli("track", src, "--out", tmp_path / "out", "--slug", "empty", "--prompt-file", prompt)
    assert r["status"] != "FAIL"
    assert (Path(r["out"]) / "prompt.txt").read_bytes() == b""


def test_missing_dependency_json_failure(tmp_path):
    env = {**os.environ, "PATH": str(tmp_path)}
    r = cli("synth", "--kind", "click", "--seconds", ".1", "--out", tmp_path / "out", env=env)
    assert r["status"] == "FAIL" and r["error_type"] == "dependency"
    assert not (tmp_path / "out").exists()


def test_no_numpy_json_failure(tmp_path):
    proc = subprocess.run([sys.executable, "-S", str(SCRIPT), "synth", "--kind", "beep",
                           "--seconds", ".1", "--out", str(tmp_path / "out")],
                          capture_output=True, text=True, env={**os.environ, "PYTHONPATH": ""})
    assert proc.returncode != 0
    r = json.loads(proc.stdout.removeprefix("RESULT: "))
    assert r["error_type"] == "dependency" and "numpy" in r["error"]


def test_numeric_parser_rejects_python_booleans():
    import argparse
    for integer in (False, True):
        with pytest.raises(argparse.ArgumentTypeError):
            module().number(0, 1, integer)(True)
