"""Music subsystem tests using real local ffmpeg fixtures; no model or network."""

import copy
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

SCRIPT = Path(__file__).resolve().parents[2] / "profiles/audio-creator/skills/audio-creator-pipeline/scripts/music-media.py"
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe required")


def module():
    spec = importlib.util.spec_from_file_location("music_media", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cli(*args, script=SCRIPT, env=None):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True,
                          text=True, timeout=120, env=env)
    lines = proc.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("RESULT: "), (proc.stdout, proc.stderr)
    result = json.loads(lines[0][8:], parse_constant=lambda v: pytest.fail(f"nonfinite JSON: {v}"))
    assert (proc.returncode != 0) == (result["status"] == "FAIL"), result
    if "error" in result:
        assert proc.returncode == 2
    elif result["status"] == "FAIL":
        assert proc.returncode == 1
    return result


def fixture(path, expression="0.2*sin(2*PI*440*t)", seconds=2, rate=48000, codec="pcm_s16le"):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    f"aevalsrc={expression}:s={rate}:d={seconds}", "-c:a", codec, str(path)],
                   capture_output=True, check=True, timeout=120)
    return path


def pcm(path):
    with wave.open(str(path), "rb") as handle:
        assert handle.getframerate() == 48000
        assert handle.getsampwidth() == 2
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").reshape(-1, handle.getnchannels())


def score(color="sine"):
    return {"version": 1, "duration_seconds": 2, "bpm": 120, "meter": "4/4", "key": "A minor",
            "seed": 17, "tracks": [{"id": "lead", "instrument": color, "gain_db": -12,
                                    "notes": [{"pitch": 69, "start": .5, "duration": 2}]}]}


def approval_fixture(tmp_path, value=None):
    """Exercise dynamic sibling import, not an installed/generated plan.

    The real approval helper is parent-owned. This contract stub freezes a JSON
    manifest and rejects byte/hash drift, exactly at the agreed integration seam.
    """
    script = tmp_path / "music-media.py"
    script.write_bytes(SCRIPT.read_bytes())
    (tmp_path / "music_plan.py").write_text(
        'import hashlib, json\n'
        'from pathlib import Path\n'
        'def load_approved(path, sha, operation):\n'
        '    assert operation == "create"\n'
        '    raw = Path(path).read_bytes()\n'
        '    if hashlib.sha256(raw).hexdigest() != sha:\n'
        '        raise ValueError("approval mismatch")\n'
        '    return {**json.loads(raw), "approval_sha256": sha}\n'
    )
    plan = tmp_path / "approved.json"
    artifact = json.dumps(score() if value is None else value, indent=2) + "\n"
    plan.write_text(json.dumps({"artifact_text": artifact, "form": {"purpose": "test"}, "settings": {}}))
    return script, plan, hashlib.sha256(plan.read_bytes()).hexdigest(), artifact


@pytest.mark.parametrize("color", ["sine", "triangle", "pulse", "fm-bell", "noise"])
def test_create_repeats_pcm_with_exact_score_evidence(tmp_path, color):
    script, plan, sha, artifact = approval_fixture(tmp_path, score(color))
    a, b = [cli("create", "--approved-plan", plan, "--approval-sha256", sha,
                "--out", tmp_path / str(i), script=script) for i in range(2)]
    assert a["status"] == b["status"] == "PASS", a
    assert np.array_equal(pcm(a["master"]), pcm(b["master"]))
    assert a["pcm_sha256"] == b["pcm_sha256"]
    assert a["renderer_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert a["environment_sha256"] == b["environment_sha256"]
    assert Path(a["out"], "score.json").read_text() == artifact
    assert a["score_sha256"] == hashlib.sha256(artifact.encode()).hexdigest()
    assert a["approval_sha256"] == sha
    samples = pcm(a["master"])
    assert samples.shape == (96000, 2)
    assert not samples[:12000].any() and not samples[60000:].any()
    assert not samples[[12000, 59999]].any()
    assert a["render"]["notes"][0]["start_frame"] == 12000
    assert a["render"]["notes"][0]["end_frame_exclusive"] == 60000
    assert a["auditory_quality"] == "unverified"


def test_meter_labels_do_not_change_quarter_timing_and_seed_defaults():
    mod = module()
    value = score("noise")
    value.pop("seed")
    original = copy.deepcopy(value)
    a, _ = mod.render_score(value)
    assert value == original
    value["meter"] = "6/8"
    b, _ = mod.render_score(value)
    assert np.array_equal(a, b)
    value["seed"] = 1
    c, _ = mod.render_score(value)
    assert not np.array_equal(b, c)


@pytest.mark.parametrize("field,value", [
    ("version", True), ("version", 1.0), ("duration_seconds", .99), ("duration_seconds", 60.01),
    ("bpm", 39), ("bpm", 241), ("bpm", "120"), ("bpm", float("nan")),
    ("seed", -1), ("seed", 2**32), ("seed", False), ("key", " "), ("key", "x" * 41),
    ("meter", "4"), ("meter", True), ("tracks", {}), ("seconds", 2), ("tempo", 120),
])
def test_strict_score_top_level_rejects_unknown_aliases_and_types(field, value):
    s = score()
    s[field] = value
    with pytest.raises(ValueError):
        module().validate_score(s)


@pytest.mark.parametrize("field,value", [("pitch", 23), ("pitch", 97), ("pitch", 60.0), ("pitch", True),
    ("start", -1), ("start", float("inf")), ("start", 4), ("duration", 0), ("duration", 4),
    ("duration", .00000001), ("duration", True), ("velocity", 1.01), ("velocity", -.01), ("beat", 1)])
def test_strict_note_bounds(field, value):
    s = score()
    s["tracks"][0]["notes"][0][field] = value
    with pytest.raises(ValueError):
        module().validate_score(s)


@pytest.mark.parametrize("field,value", [("id", "../lead"), ("id", "A"), ("instrument", "piano"),
    ("gain_db", 1), ("gain_db", -61), ("pan", True), ("pan", 1.01), ("notes", {}), ("volume", .1)])
def test_strict_track_bounds(field, value):
    s = score()
    s["tracks"][0][field] = value
    with pytest.raises(ValueError):
        module().validate_score(s)


def test_score_cardinality_time_overrun_and_inclusive_bounds():
    mod = module()
    s = score()
    s["tracks"] *= 2
    with pytest.raises(ValueError, match="unique"):
        mod.validate_score(s)
    s = score()
    s["tracks"] = [{**s["tracks"][0], "id": f"track-{i}"} for i in range(9)]
    with pytest.raises(ValueError, match="8"):
        mod.validate_score(s)
    s = score()
    s["tracks"][0]["notes"] *= 2049
    with pytest.raises(ValueError, match="2048"):
        mod.validate_score(s)
    for duration, bpm, pitch in ((1, 40, 24), (60, 240, 96)):
        s = score()
        s.update(duration_seconds=duration, bpm=bpm, seed=2**32 - 1)
        s["tracks"][0]["notes"] = [{"pitch": pitch, "start": 0, "duration": duration * bpm / 60}]
        mod.validate_score(s)
    s["tracks"][0]["notes"][0]["duration"] += .000001
    with pytest.raises(ValueError):
        mod.validate_score(s)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"x":NaN}', '{"x":1e999}', '{'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        module().strict_json(raw)


def test_approval_mismatch_and_deep_invalid_no_audio(tmp_path):
    script, plan, sha, _ = approval_fixture(tmp_path)
    result = cli("create", "--approved-plan", plan, "--approval-sha256", "0" * 64,
                 "--out", tmp_path / "bad", script=script)
    assert "approval mismatch" in result["error"] and not (tmp_path / "bad").exists()
    value = json.loads(plan.read_text())
    broken = score()
    broken["tracks"][0]["instrument"] = "violin"
    value["artifact_text"] = json.dumps(broken)
    plan.write_text(json.dumps(value))
    sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    result = cli("create", "--approved-plan", plan, "--approval-sha256", sha,
                 "--out", tmp_path / "bad", script=script)
    assert "synthetic color" in result["error"] and not (tmp_path / "bad").exists()


def test_approval_recheck_before_renderer(monkeypatch, tmp_path):
    mod = module()
    manifest = {"artifact_text": json.dumps(score()), "approval_sha256": "a" * 64}
    calls = []

    def load(*args):
        calls.append(args)
        return manifest if len(calls) == 1 else {**manifest, "artifact_text": "changed"}

    monkeypatch.setattr(mod, "load_approved", load)
    monkeypatch.setattr(mod, "render_score", lambda value: pytest.fail("unapproved render"))
    args = mod.parser().parse_args(["create", "--approved-plan", "ignored", "--approval-sha256", "a" * 64,
                                   "--out", str(tmp_path / "out")])
    with pytest.raises(ValueError, match="changed"):
        mod.execute(args)
    assert len(calls) == 2 and not (tmp_path / "out").exists()


def test_create_overload_keeps_float_diagnostics_without_clipped_master(tmp_path):
    s = score()
    s["tracks"][0]["gain_db"] = 0
    s["tracks"][0]["notes"] *= 8
    script, plan, sha, _ = approval_fixture(tmp_path, s)
    r = cli("create", "--approved-plan", plan, "--approval-sha256", sha, "--out", tmp_path / "out", script=script)
    assert r["status"] == "FAIL" and r["master"] is None
    assert r["pre_quantization_measure"]["out_of_range_count"] > 0
    assert Path(r["out"], "candidate.f32le").stat().st_size == 96000 * 2 * 4
    assert not list(Path(r["out"]).glob("*.wav"))


def test_periodic_partial_cutoff_and_pitch():
    mod = module()
    s = score("pulse")
    s.update(duration_seconds=1, bpm=60)
    s["tracks"][0]["notes"] = [{"pitch": 96, "start": 0, "duration": 1}]
    samples, _ = mod.render_score(s)
    middle = samples[4800:43200, 0]
    spectrum = np.abs(np.fft.rfft(middle * np.hanning(len(middle))))
    frequencies = np.fft.rfftfreq(len(middle), 1 / 48000)
    fundamental = 440 * 2 ** ((96 - 69) / 12)
    assert frequencies[spectrum.argmax()] == pytest.approx(fundamental, abs=2)
    alias = 48000 - fundamental * 13  # First odd partial above Nyquist is omitted.
    assert spectrum[np.argmin(abs(frequencies - alias))] < spectrum.max() * .001


def test_antiphase_track_retains_native_info_raw_prompt_and_take(tmp_path):
    src = fixture(tmp_path / "stereo.wav", "0.2*sin(2*PI*440*t)|-0.2*sin(2*PI*440*t)", rate=44100)
    raw = src.read_bytes()
    ev = tmp_path / "take.json"
    ev.write_text(json.dumps({"settings": {"duration_seconds": 2}, "seed": 9, "raw_sha256": hashlib.sha256(raw).hexdigest()}))
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"  Exact prompt\r\n")
    r = cli("track", src, "--out", tmp_path / "out", "--take-file", ev, "--prompt-file", prompt)
    assert r["status"] == "PASS", r
    assert r["source"]["native"]["sample_rate"] == 44100
    assert r["source"]["measure"]["sample_rate"] == r["measure"]["sample_rate"] == 48000
    assert r["measure"]["channels"] == 2 and r["measure"]["frames"] == 96000
    audio = pcm(r["master"])
    assert abs(audio.astype(float).sum(axis=1)).max() <= 1 and abs(audio).max() > 6000
    assert src.read_bytes() == Path(r["out"], "source.original").read_bytes() == raw
    assert Path(r["out"], "prompt.txt").read_bytes() == prompt.read_bytes()
    assert Path(r["out"], "source.take.json").read_bytes() == ev.read_bytes()
    assert r["evidence"]["seed"] == 9 and r["duration_check"]["status"] == "PASS"
    assert r["prompt_check"]["status"] == "unavailable"


@pytest.mark.parametrize("evidence", [{"requested_seconds": 1}, {"duration_seconds": 3},
                                       {"raw_sha256": "0" * 64}])
def test_take_mismatch_is_failed_candidate(tmp_path, evidence):
    src = fixture(tmp_path / "source.wav")
    ev = tmp_path / "take.json"
    ev.write_text(json.dumps(evidence))
    r = cli("track", src, "--out", tmp_path / "out", "--take-file", ev)
    assert r["status"] == "FAIL" and r["diagnostic_candidate"]
    assert Path(r["master"]).is_file()


@pytest.mark.parametrize("payload", [{"duration_seconds": 2, "text": "local"}, {"duration": 2, "prompt": "remote receipt only"}])
def test_generation_receipt_request_duration_and_raw_wav_hash(tmp_path, payload):
    src = fixture(tmp_path / "source.wav")
    ev = tmp_path / "take.json"
    evidence = {"request": payload, "raw_wav": {"sha256_file": hashlib.sha256(src.read_bytes()).hexdigest()}}
    ev.write_text(json.dumps(evidence))
    r = cli("track", src, "--out", tmp_path / "out", "--take-file", ev)
    assert r["duration_check"]["status"] == "PASS"
    evidence["raw_wav"]["sha256_file"] = "0" * 64
    ev.write_text(json.dumps(evidence))
    r = cli("track", src, "--out", tmp_path / "bad", "--take-file", ev)
    assert r["status"] == "FAIL" and "SHA-256" in " ".join(r["failures"])


@pytest.mark.parametrize("field,duration_field", [("text", "duration_seconds"), ("prompt", "duration")])
def test_track_receipt_prompt_exact_match_preserves_whitespace(tmp_path, field, duration_field):
    src = fixture(tmp_path / "source.wav")
    text = "  Exact receipt prompt.\r\nNo normalization.\n"
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(text.encode("utf-8"))
    receipt = tmp_path / "take.json"
    receipt.write_text(json.dumps({"request": {field: text, duration_field: 2},
                                  "raw_wav": {"sha256_file": hashlib.sha256(src.read_bytes()).hexdigest()}}))
    result = cli("track", src, "--out", tmp_path / "out", "--take-file", receipt, "--prompt-file", prompt)
    assert result["status"] == "PASS", result
    assert result["prompt_check"]["status"] == "PASS"
    assert result["prompt_check"]["fields"] == [f"request.{field}"]
    assert Path(result["out"], "prompt.txt").read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize("field", ["text", "prompt"])
@pytest.mark.parametrize("wrong", ["Different prompt.\r\n", "Exact prompt.\n", "Exact prompt.\r\n "])
def test_wrong_prompt_provenance_refused_before_decode(tmp_path, field, wrong):
    # A nonexistent source proves prompt mismatch is rejected before decoding.
    receipt, prompt, out = tmp_path / "take.json", tmp_path / "prompt.txt", tmp_path / "out"
    receipt.write_text(json.dumps({"request": {field: "Exact prompt.\r\n"}}))
    prompt.write_bytes(wrong.encode("utf-8"))
    result = cli("track", tmp_path / "missing.wav", "--out", out, "--take-file", receipt, "--prompt-file", prompt)
    assert "must match receipt request." + field + " exactly" in result["error"]
    assert not out.exists()


@pytest.mark.parametrize("payload", [{"text": None}, {"prompt": 123}, {"text": "match", "prompt": "different"}])
def test_malformed_or_conflicting_receipt_prompts_are_not_ignored(tmp_path, payload):
    receipt, prompt = tmp_path / "take.json", tmp_path / "prompt.txt"
    receipt.write_text(json.dumps({"request": payload}))
    prompt.write_text("match")
    result = cli("track", tmp_path / "missing", "--out", tmp_path / "out", "--take-file", receipt, "--prompt-file", prompt)
    assert "must match receipt request." in result["error"]
    assert not (tmp_path / "out").exists()


def test_conflicting_take_durations_and_malformed_sidecars(tmp_path):
    src = fixture(tmp_path / "source.wav")
    ev = tmp_path / "take.json"
    for i, value in enumerate(["[]", '{"seed":NaN}', '{"seconds":1,"request":{"duration_seconds":2}}']):
        ev.write_text(value)
        r = cli("track", src, "--out", tmp_path / str(i), "--take-file", ev)
        assert "error" in r and not (tmp_path / str(i)).exists()
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"\xff")
    r = cli("track", src, "--out", tmp_path / "prompt-out", "--prompt-file", prompt)
    assert "error" in r


def test_trim_loop_fades_exact_length_and_stereo(tmp_path):
    src = fixture(tmp_path / "source.wav", "0.2*sin(2*PI*440*t)|-0.2*sin(2*PI*440*t)")
    r = cli("edit", src, "--out", tmp_path / "out", "--start", ".25", "--end", "1.25",
            "--loop-seconds", "3.123", "--crossfade-ms", "100", "--fade-in-ms", "50",
            "--fade-out-ms", "80", "--gain-db", "-6")
    assert r["status"] == "PASS", r
    audio = pcm(r["master"])
    assert len(audio) == round(3.123 * 48000) and not audio[[0, -1]].any()
    assert abs(audio.astype(float).sum(axis=1)).max() <= 1
    assert abs(audio[:500]).max() < abs(audio[4800:9600]).max() / 2
    assert r["edit"]["order"] == list(module().ORDER)
    assert r["edit"]["target_lufs"] is None


@pytest.mark.parametrize("crossfade_ms", [0, 100])
@pytest.mark.parametrize("normalized", [False, True])
def test_repeat_seams_measure_actual_delivered_pcm_with_trim_offset(tmp_path, crossfade_ms, normalized):
    src = fixture(tmp_path / "source.wav", "0.2*sin(2*PI*437*t)|-0.2*sin(2*PI*437*t)")
    controls = ["--target-lufs", "-20"] if normalized else []
    result = cli("edit", src, "--out", tmp_path / "out", "--start", ".25", "--end", "1.25",
                 "--loop-seconds", "3.123", "--crossfade-ms", crossfade_ms,
                 "--fade-in-ms", "1500", "--fade-out-ms", "1200", "--gain-db", "-6", *controls)
    assert result["status"] == "PASS", result
    report = result["edit"]["seams"]
    before = result["edit"]["pre_quantization_seams"]
    assert report["stage"] == "delivered_pcm16"
    assert before["stage"] == "pre_quantization_after_optional_normalization"
    assert report["verification"] == before["verification"] == "NOT seamless-loop verification"
    assert report["total_count"] == report["reported_count"] == 3
    assert report["omitted_count"] == 0
    assert result["edit"]["source_segment"] == {"start_frame": 12000, "end_frame_exclusive": 60000,
                                               "start_seconds": .25, "end_seconds": 1.25}
    audio = pcm(result["master"]).astype(float) / 32768
    cross = crossfade_ms * 48
    for i, seam in enumerate(report["seams"], 1):
        frame = i * (48000 - cross)
        assert seam["repeat_index"] == i
        assert seam["offset_frame"] == frame
        assert seam["offset_seconds"] == frame / 48000  # Output-relative, not +0.25 source offset.
        assert seam["delta_per_channel"] == (audio[frame] - audio[frame - 1]).tolist()
        if cross:
            for name, position in (("crossfade_start", frame), ("crossfade_end_exclusive", frame + cross)):
                assert seam[name]["frame"] == position and seam[name]["time_seconds"] == position / 48000
                assert seam[name]["delta_per_channel"] == (audio[position] - audio[position - 1]).tolist()
        else:
            assert seam["crossfade_start"] is seam["crossfade_end_exclusive"] is None
    sidecar = json.loads(Path(result["master"]).with_suffix(".take.json").read_text())
    assert sidecar["edit"]["seams"] == report


def test_edit_direct_seams_are_post_gain_fades_and_single_source_has_none():
    mod = module()
    source = np.linspace(-.1, .1, 96000).reshape(-1, 1)
    args = mod.parser().parse_args(["edit", "ignored", "--out", "ignored", "--start", ".25", "--end", "1.25",
                                   "--loop-seconds", "3", "--crossfade-ms", "100", "--fade-in-ms", "1500", "--gain-db", "-6"])
    samples, meta = mod.edit(source, args)
    assert meta["seams"]["stage"] == "post_fades_gain_float64"
    for seam in meta["seams"]["seams"]:
        f = seam["offset_frame"]
        assert seam["delta_per_channel"] == (samples[f] - samples[f - 1]).tolist()
    args.loop_seconds, args.crossfade_ms, args.fade_in_ms = None, 0, 0
    _, once = mod.edit(source, args)
    assert once["seams"]["total_count"] == once["seams"]["omitted_count"] == 0
    assert once["seams"]["seams"] == []


def test_seam_metadata_cap_counts_omitted_repeats(tmp_path):
    src = fixture(tmp_path / "short.wav", "0.2*sin(2*PI*1000*t)", seconds=.001)
    result = cli("edit", src, "--out", tmp_path / "out", "--loop-seconds", "1.2")
    assert result["status"] != "FAIL", result
    for field in ("seams", "pre_quantization_seams"):
        report = result["edit"][field]
        assert report["total_count"] == 1199
        assert len(report["seams"]) == report["reported_count"] == report["limit"] == 1024
        assert report["omitted_count"] == 175
    assert result["edit"]["seams"]["seams"][-1]["offset_frame"] == 1024 * 48


def test_single_source_delivery_reports_no_repeat_seams(tmp_path):
    src = fixture(tmp_path / "source.wav")
    result = cli("edit", src, "--out", tmp_path / "out", "--start", ".25", "--end", "1.25")
    report = result["edit"]["seams"]
    assert report["stage"] == "delivered_pcm16"
    assert report["total_count"] == report["reported_count"] == report["omitted_count"] == 0
    assert report["seams"] == []


@pytest.mark.parametrize("controls", [
    ["--crossfade-ms", "1"], ["--loop-seconds", "1"],
    ["--loop-seconds", "3", "--crossfade-ms", "2000"],
    ["--loop-seconds", "2", "--crossfade-ms", "1"],
    ["--fade-in-ms", "2001"], ["--fade-out-ms", "2001"],
    ["--start", "2"], ["--end", "3"], ["--start", ".000001", "--end", ".000002"],
    ["--loop-seconds", "600", "--crossfade-ms", "1999"],
])
def test_invalid_edit_intervals_do_not_publish_or_hang(tmp_path, controls):
    src = fixture(tmp_path / "source.wav")
    r = cli("edit", src, "--out", tmp_path / "out", *controls)
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


@pytest.mark.parametrize("flag,value", [("--start", "nan"), ("--end", "inf"), ("--gain-db", "True"),
    ("--gain-db", "25"), ("--loop-seconds", "600.1"), ("--crossfade-ms", "1.1"),
    ("--target-lufs", "-4"), ("--target-lufs", "nan"), ("--pitch", "2"), ("--slug", "../bad")])
def test_invalid_controls_are_json_errors(tmp_path, flag, value):
    r = cli("edit", tmp_path / "missing", "--out", tmp_path / "out", flag, value)
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


@pytest.mark.parametrize("target", [-16, -24])
def test_two_pass_lufs_final_quantized_recheck(tmp_path, target):
    src = fixture(tmp_path / "quiet.wav", "0.03*sin(2*PI*440*t)", seconds=4)
    r = cli("edit", src, "--out", tmp_path / "out", "--target-lufs", target)
    assert r["status"] == "PASS", r
    assert r["measure"]["integrated_lufs"] == pytest.approx(target, abs=.5)
    assert r["measure"]["true_peak_dbtp"] <= -.9
    assert r["edit"]["normalization"]["target_tp"] == -1
    assert r["pre_quantization_measure"]["integrated_lufs"] == pytest.approx(target, abs=.5)
    assert r["edit"]["normalization_input_measure"]["integrated_lufs"] < -30
    measured = cli("analyze", r["master"])["measure"]
    for field in ("integrated_lufs", "true_peak_dbtp", "pcm_sha256"):
        assert measured[field] == r["measure"][field]


def test_clipping_not_repaired_silently_by_resample_gain_or_normalize(tmp_path):
    src = fixture(tmp_path / "clipped.wav", "eq(n\\,1000)", rate=96000)
    r = cli("edit", src, "--out", tmp_path / "out", "--gain-db", "-12")
    assert r["source"]["native"]["clipping_detected"]
    assert r["status"] == "FAIL" and r["measure"]["clipping_count"] == 0
    over = fixture(tmp_path / "float.wav", "1.2*sin(2*PI*440*t)", codec="pcm_f32le")
    r = cli("track", over, "--out", tmp_path / "over")
    assert r["status"] == "FAIL" and r["master"] is None
    assert r["pre_quantization_measure"]["out_of_range_count"] > 0
    clean = fixture(tmp_path / "clean.wav")
    r = cli("edit", clean, "--out", tmp_path / "gain", "--gain-db", "24", "--target-lufs", "-16")
    assert r["status"] == "FAIL" and r["master"] is None
    assert "refused" in r["edit"]["normalization"]


def test_silence_has_useful_findings_no_key_tempo_and_normalization_fails(tmp_path):
    src = fixture(tmp_path / "silence.wav", "0", seconds=4)
    before = set(tmp_path.iterdir())
    r = cli("analyze", src, "--focus", "Explain the lack of activity")
    assert set(tmp_path.iterdir()) == before
    assert r["status"] == "WARN" and r["analysis"]["silence"]
    for name in ("tempo", "key", "beats", "chords"):
        assert r["analysis"][name]["status"] == "unavailable"
    assert len(r["analysis"]["chords"]["windows"]) == 2
    assert all(w["status"] == "unavailable" and w["candidates"] == [] for w in r["analysis"]["chords"]["windows"])
    assert r["analysis"]["pitch_classes"]["distribution"] == [0] * 12
    assert r["analysis"]["activity"]["windows"] and not r["analysis"]["structure"]["candidate_boundaries"]
    assert r["analysis"]["focus"] == "Explain the lack of activity"
    normalized = cli("edit", src, "--out", tmp_path / "out", "--target-lufs", "-16")
    assert normalized["status"] == "FAIL"


def test_120bpm_pulse_train_and_antiphase_analysis(tmp_path):
    expression = "0.4*lt(mod(t\\,0.5)\\,0.03)*sin(2*PI*440*t)"
    mono = fixture(tmp_path / "pulse.wav", expression, seconds=12)
    stereo = fixture(tmp_path / "anti.wav", f"{expression}|-({expression})", seconds=12)
    a, b = [cli("analyze", path)["analysis"] for path in (mono, stereo)]
    candidates = a["tempo"]["candidates"]
    assert any(abs(c["bpm"] - 120) < 3 for c in candidates), a["tempo"]
    assert any("ambiguity" in c["relation"] for c in candidates)
    assert a["beats"]["status"] == "estimate" and len(a["beats"]["times_seconds"]) >= 8
    assert b["tempo"]["candidates"][0]["bpm"] == a["tempo"]["candidates"][0]["bpm"]
    assert b["pitch_classes"]["distribution"] == pytest.approx(a["pitch_classes"]["distribution"], abs=.001)
    assert not b["silence"]


def test_sustained_tone_does_not_magnify_fft_leakage_into_beats(tmp_path):
    src = fixture(tmp_path / "tone.wav", seconds=8)
    report = cli("analyze", src)["analysis"]
    assert report["tempo"]["status"] == report["beats"]["status"] == "unavailable"


def test_relative_key_ambiguity_numeric_structure_original_time_offset(tmp_path):
    # A/C/E/F/G shared pitch material cannot establish C major versus A minor.
    expression = "(0.045*sin(2*PI*220*t)+0.045*sin(2*PI*261.625565*t)+0.045*sin(2*PI*329.627557*t)+0.025*sin(2*PI*349.228231*t)+0.025*sin(2*PI*391.995436*t))*if(lt(t\\,6)\\,1\\,0.1)"
    src = fixture(tmp_path / "harmony.wav", expression, seconds=10)
    r = cli("analyze", src, "--start", "2", "--end", "10")
    analysis = r["analysis"]
    keys = [c["key"] for c in analysis["key"]["candidates"]]
    assert "A minor" in keys and "C major" in keys, analysis["key"]
    assert "relative major/minor" in analysis["key"]["ambiguity"]
    assert analysis["segment"] == {"start_seconds": 2, "end_seconds": 10}
    assert analysis["activity"]["windows"][0]["start_seconds"] == 2
    boundaries = analysis["structure"]["candidate_boundaries"]
    assert any(abs(b["time_seconds"] - 6) <= 2 for b in boundaries)
    assert all(b["time_seconds"] >= 2 for b in boundaries)
    assert all("label" not in b for b in boundaries)
    assert "vocal presence or absence" in analysis["unverified"]


@pytest.mark.parametrize("name,frequencies", [("C major", (261.625565, 329.627557, 391.995436)),
                                              ("A minor", (220., 261.625565, 329.627557))])
def test_triad_candidates_antiphase_and_all_original_offset_windows(tmp_path, name, frequencies):
    expression = "+".join(f"0.08*sin(2*PI*{frequency}*t)" for frequency in frequencies)
    mono = fixture(tmp_path / "triad.wav", expression, seconds=6)
    stereo = fixture(tmp_path / "antiphase.wav", f"{expression}|-({expression})", seconds=6)
    reports = [cli("analyze", path, "--start", "1", "--end", "5.25")["analysis"] for path in (mono, stereo)]
    for analysis in reports:
        chords = analysis["chords"]
        assert chords["status"] == "estimate"
        assert "not calibrated confidence" in chords["similarity_definition"]
        assert "inversions, extensions and transitions are not transcribed" in chords["limits"]
        windows = chords["windows"]
        assert [(w["start_seconds"], w["end_seconds"]) for w in windows] == [(1, 3), (3, 5), (5, 5.25)]
        assert len(windows) == len(analysis["activity"]["windows"])
        for w in windows:
            assert w["status"] == "estimate" and w["unavailable_reason"] is None
            assert len(w["candidates"]) == 3
            assert w["candidates"][0]["chord"] == name, w
            assert all(0 <= c["similarity"] <= 1 and "confidence" not in c for c in w["candidates"])
    for mono_window, stereo_window in zip(reports[0]["chords"]["windows"], reports[1]["chords"]["windows"]):
        assert [c["chord"] for c in mono_window["candidates"]] == [c["chord"] for c in stereo_window["candidates"]]
        assert [c["similarity"] for c in mono_window["candidates"]] == pytest.approx(
            [c["similarity"] for c in stereo_window["candidates"]], abs=.001)


@pytest.mark.parametrize("kind", ["noise", "flat", "quiet", "single-tone"])
def test_chords_unavailable_for_weak_diffuse_or_noise_evidence(tmp_path, kind):
    src = tmp_path / "unavailable.wav"
    if kind == "noise":
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                        "anoisesrc=sample_rate=48000:duration=4:amplitude=0.1:seed=42", "-c:a", "pcm_s16le", str(src)],
                       capture_output=True, check=True, timeout=30)
    elif kind == "flat":
        expression = "+".join(f"0.01*sin(2*PI*{440 * 2 ** ((pitch - 69) / 12)}*t)" for pitch in range(60, 72))
        fixture(src, expression, seconds=4)
    elif kind == "quiet":
        fixture(src, "0.0001*(sin(2*PI*261.625565*t)+sin(2*PI*329.627557*t)+sin(2*PI*391.995436*t))", seconds=4)
    else:
        fixture(src, seconds=4)
    report = cli("analyze", src)["analysis"]["chords"]
    assert report["status"] == "unavailable", report
    assert len(report["windows"]) == 2
    assert all(w["status"] == "unavailable" and not w["candidates"] and w["unavailable_reason"] for w in report["windows"])


def test_batched_stft_allocations_stay_bounded(monkeypatch):
    mod = module()
    fft = np.fft.rfft
    sizes = []

    def recording(value, *args, **kwargs):
        sizes.append(value.shape)
        return fft(value, *args, **kwargs)

    monkeypatch.setattr(np.fft, "rfft", recording)
    report = mod.musical_analysis(np.zeros((48000 * 5, 2), dtype=np.float32))
    assert len(sizes) > 1 and max(shape[0] for shape in sizes) <= 64
    assert report["memory_bound"]["stft_batch_frames"] == 64


@pytest.mark.parametrize("kind", ["empty", "directory", "symlink", "fifo", "device", "oversize", "playlist", "concat", "channels", "corrupt"])
def test_unsafe_inputs_blocked(tmp_path, kind):
    src = tmp_path / "input.wav"
    if kind == "empty":
        src.touch()
    elif kind == "directory":
        src.mkdir()
    elif kind == "symlink":
        src.symlink_to(fixture(tmp_path / "target.wav"))
    elif kind == "fifo":
        os.mkfifo(src)
    elif kind == "device":
        src = Path("/dev/zero")
    elif kind == "oversize":
        with src.open("wb") as handle:
            handle.truncate(128 * 1024 * 1024 + 1)
    elif kind == "playlist":
        src.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttps://127.0.0.1:9/audio.ts\n#EXT-X-ENDLIST\n")
    elif kind == "concat":
        src.write_text("ffconcat version 1.0\nfile 'file:/etc/passwd'\n")
    elif kind == "channels":
        fixture(src, "0.1*sin(t)|0.1*cos(t)|0.1*sin(2*t)")
    else:
        fixture(src)
        src.write_bytes(src.read_bytes()[:-111])
    r = cli("track", src, "--out", tmp_path / "out")
    assert r["status"] == "FAIL" and not (tmp_path / "out").exists()


def test_decode_does_not_trust_declared_duration_and_caps_resampled_output(tmp_path):
    src = fixture(tmp_path / "long.flac", seconds=600.02, rate=8000, codec="flac")
    raw = bytearray(src.read_bytes())
    field = int.from_bytes(raw[18:26], "big")
    raw[18:26] = ((field & ~((1 << 36) - 1)) | 8000).to_bytes(8, "big")
    src.write_bytes(raw)
    r = cli("track", src, "--out", tmp_path / "out")
    assert r["status"] == "FAIL" and "600" in r["error"]
    assert not (tmp_path / "out").exists()


def test_inclusive_600_second_decode_and_native_duration_evidence(tmp_path):
    src = fixture(tmp_path / "bound.flac", seconds=600, rate=8000, codec="flac")
    samples, native = module().decode(src, src.read_bytes())
    assert samples.shape == (600 * 48000, 1)
    assert native["sample_rate"] == 8000 and native["decoded_frames"] == 600 * 8000
    assert native["decoded_duration_seconds"] == 600


def test_full_60_second_score_has_no_hidden_envelope_tail(tmp_path):
    s = score("sine")
    s["duration_seconds"] = 60
    s["tracks"][0]["notes"] = [{"pitch": 24, "start": 0, "duration": 120}]
    script, plan, sha, _ = approval_fixture(tmp_path, s)
    r = cli("create", "--approved-plan", plan, "--approval-sha256", sha, "--out", tmp_path / "out", script=script)
    assert r["status"] != "FAIL", r
    assert r["measure"]["frames"] == 60 * 48000
    assert r["render"]["notes"][0]["end_frame_exclusive"] == 60 * 48000
    assert not pcm(r["master"])[[0, -1]].any()


@pytest.mark.parametrize("kind", ["empty", "populated", "symlink", "dangling", "source", "missing-parent"])
def test_output_exclusive_and_existing_untouched(tmp_path, kind):
    src = fixture(tmp_path / "source.wav")
    raw = src.read_bytes()
    out = tmp_path / "out"
    if kind in ("empty", "populated"):
        out.mkdir()
        if kind == "populated":
            (out / "keep").write_bytes(b"untouched")
    elif kind in ("symlink", "dangling"):
        out.symlink_to(src if kind == "symlink" else tmp_path / "missing")
    elif kind == "source":
        out = src
    else:
        out = tmp_path / "missing" / "out"
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    r = cli("track", src, "--out", out)
    assert r["status"] == "FAIL" and src.read_bytes() == raw
    assert sorted(str(path) for path in tmp_path.rglob("*")) == before
    if kind == "populated":
        assert (out / "keep").read_bytes() == b"untouched"


def test_publication_race_is_atomic_no_replace(tmp_path):
    candidate, out = tmp_path / "candidate", tmp_path / "out"
    candidate.mkdir()
    (candidate / "complete").write_text("complete")
    out.mkdir()
    with pytest.raises(OSError):
        module().publish(candidate, out)
    assert not list(out.iterdir()) and (candidate / "complete").read_text() == "complete"


def test_missing_dependencies_return_json(tmp_path):
    r = cli("track", tmp_path / "source", "--out", tmp_path / "out", env={**os.environ, "PATH": str(tmp_path)})
    assert r["error_type"] == "dependency"
    proc = subprocess.run([sys.executable, "-S", str(SCRIPT), "analyze", "missing"],
                          capture_output=True, text=True, env={**os.environ, "PYTHONPATH": ""})
    assert proc.returncode == 2
    assert json.loads(proc.stdout.removeprefix("RESULT: "))["error_type"] == "dependency"
