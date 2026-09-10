"""Mix subsystem tests using real local ffmpeg fixtures; no model or network.

Mix places already-finished sources on a shared timeline: propose (round A,
zero render) then render (round B, only against a matching approval). This
mirrors test_music_media.py's real-fixture style but exercises mix-media.py.
"""

from __future__ import annotations

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

HERMES = Path(__file__).resolve().parents[2]
SCRIPTS = HERMES / "profiles/audio-creator/skills/audio-creator-pipeline/scripts"
SCRIPT = SCRIPTS / "mix-media.py"
MUSIC_SCRIPT = SCRIPTS / "music-media.py"
RATE = 48000
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe required")


def module():
    spec = importlib.util.spec_from_file_location("mix_media", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def script_copy(tmp_path):
    """A controllable script pair so a test can mutate the renderer fingerprint."""
    directory = tmp_path / "scripts"
    directory.mkdir(exist_ok=True)
    mix_copy = directory / "mix-media.py"
    music_copy = directory / "music-media.py"
    mix_copy.write_bytes(SCRIPT.read_bytes())
    music_copy.write_bytes(MUSIC_SCRIPT.read_bytes())
    return mix_copy


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
        assert handle.getframerate() == RATE
        assert handle.getsampwidth() == 2
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").reshape(-1, handle.getnchannels())


def source_entry(ident, path, role="music", words=None):
    entry = {"id": ident, "path": str(path), "role": role}
    if words is not None:
        entry["words"] = str(words)
    return entry


def cue_entry(ident, source, start, source_start, duration, gain_db=0., fade_in=0., fade_out=0., envelope=None):
    return {"id": ident, "source": source, "start": start, "source_start": source_start, "duration": duration,
            "gain_db": gain_db, "fade_in": fade_in, "fade_out": fade_out, "envelope": envelope or []}


def spec(duration_seconds=2, channels=1, target_lufs=None, true_peak_dbtp=-1., sources=None, cues=None, **extra):
    return {"version": 1, "what_for": "test mix", "direction": "layer test tone",
            "duration_seconds": duration_seconds, "channels": channels, "target_lufs": target_lufs,
            "true_peak_dbtp": true_peak_dbtp,
            "sources": sources if sources is not None else [source_entry("tone", "/tmp/does-not-matter.wav")],
            "cues": cues if cues is not None else [cue_entry("main", "tone", 0, 0, duration_seconds)],
            **extra}


def write(path, obj_or_text):
    if isinstance(obj_or_text, str):
        path.write_text(obj_or_text, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj_or_text), encoding="utf-8")
    return path


def propose(tmp_path, spec_dict, out, description="A description of the mix, nonblank.",
            previous=None, script=SCRIPT, index=0):
    spec_file = write(tmp_path / f"spec-{index}.json", spec_dict)
    desc_file = write(tmp_path / f"description-{index}.md", description)
    args = ["propose", "--spec-file", spec_file, "--description-file", desc_file, "--out", out]
    if previous:
        args += ["--previous", previous]
    return cli(*args, script=script)


def render(result, out, kind="create", slug="mix", script=SCRIPT):
    return cli("render", "--approved-plan", result["approved_plan"], "--approval-sha256", result["approval_sha256"],
               "--kind", kind, "--out", out, "--slug", slug, script=script)


def speech_source(mix_mod, tmp_path, name, expression="0.2*sin(2*PI*440*t)", seconds=2,
                   words=(("hello", .1, .4), ("there", .5, .9))):
    path = fixture(tmp_path / name, expression, seconds=seconds)
    raw = path.read_bytes()
    _, native = mix_mod.media.decode(path, raw)
    pcm_bytes = mix_mod.media.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
                                   "-f", native["container"], "-i", str(path), "-map", "0:a:0", "-ar", str(RATE),
                                   "-ac", "1", "-t", "600.01", "-f", "s16le", "pipe:1"]).stdout
    text = " ".join(w for w, *_ in words)
    doc = {"file": name, "duration": native["decoded_duration_seconds"],
           "pcm_sha256": hashlib.sha256(pcm_bytes).hexdigest(),
           "words": [{"start": a, "end": b, "word": w} for w, a, b in words],
           "captions": [{"start": words[0][1], "end": words[-1][2], "text": text}],
           "segments": [{"start": words[0][1], "end": words[-1][2], "text": text}]}
    sidecar = write(tmp_path / (name + ".words.json"), doc)
    return path, sidecar, doc


# ---------------------------------------------------------------------------
# validate_spec: strict types, unknown fields, cardinality, quantization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("version", True), ("version", 1.0), ("version", 2),
    ("duration_seconds", .99), ("duration_seconds", 600.01), ("duration_seconds", "2"),
    ("channels", 3), ("channels", 1.0), ("channels", True), ("channels", 0),
    ("target_lufs", -70.01), ("target_lufs", -4.99), ("target_lufs", "quiet"), ("target_lufs", True),
    ("true_peak_dbtp", -9.01), ("true_peak_dbtp", -0.09), ("true_peak_dbtp", True),
    ("what_for", ""), ("what_for", " "), ("what_for", "x" * 8001), ("what_for", 1),
    ("direction", 123), ("must_keep", ""),
    ("sources", []), ("cues", []),
    ("seconds", 2), ("length", 2), ("notes", "x"),
])
def test_strict_spec_top_level_rejects_unknown_aliases_and_types(field, value):
    s = spec()
    s[field] = value
    with pytest.raises(ValueError):
        module().validate_spec(s)


def test_spec_target_lufs_null_is_explicitly_valid():
    s = spec(target_lufs=None)
    assert module().validate_spec(copy.deepcopy(s)) == s


@pytest.mark.parametrize("field,value", [
    ("id", "../lead"), ("id", "A"), ("path", 1), ("path", ""), ("path", "x" * 4097),
    ("role", "vocal"), ("words", "sidecar.json"),  # words on a non-speech role
    ("extra", "nope"),
])
def test_strict_source_bounds(field, value):
    s = spec(sources=[{**source_entry("tone", "/tmp/a.wav"), field: value}])
    with pytest.raises(ValueError):
        module().validate_spec(s)


def test_duplicate_source_id_refused():
    s = spec(sources=[source_entry("tone", "/tmp/a.wav"), source_entry("tone", "/tmp/b.wav")],
             cues=[cue_entry("main", "tone", 0, 0, 2)])
    with pytest.raises(ValueError, match="duplicate source id"):
        module().validate_spec(s)


def test_1_to_16_source_and_1_to_32_cue_cardinality():
    mod = module()
    s = spec(sources=[source_entry(f"s{i}", f"/tmp/{i}.wav") for i in range(17)],
             cues=[cue_entry("main", "s0", 0, 0, 2)])
    with pytest.raises(ValueError, match="1..16"):
        mod.validate_spec(s)
    s = spec(cues=[cue_entry(f"c{i}", "tone", 0, 0, 2) for i in range(33)])
    with pytest.raises(ValueError, match="1..32"):
        mod.validate_spec(s)


@pytest.mark.parametrize("field,value", [
    ("id", "../cue"), ("source", "missing"), ("start", -1), ("start", float("inf")),
    ("source_start", -1), ("source_start", 601), ("duration", 0), ("duration", 3),
    ("gain_db", -61), ("gain_db", 25), ("fade_in", 3), ("fade_out", 3),
    ("envelope", "not-a-list"), ("envelope", [{"at": 0, "gain_db": 0}] * 65), ("extra", "nope"),
])
def test_strict_cue_bounds(field, value):
    s = spec(duration_seconds=2, cues=[{**cue_entry("main", "tone", 0, 0, 2), field: value}])
    with pytest.raises(ValueError):
        module().validate_spec(s)


def test_duplicate_cue_id_refused():
    s = spec(cues=[cue_entry("main", "tone", 0, 0, 1), cue_entry("main", "tone", 1, 0, 1)])
    with pytest.raises(ValueError, match="duplicate cue id"):
        module().validate_spec(s)


def test_cue_extends_beyond_timeline_or_source_bound_before_quantization():
    mod = module()
    s = spec(duration_seconds=2, cues=[cue_entry("main", "tone", 1.5, 0, 1)])
    with pytest.raises(ValueError, match="beyond timeline/source bound"):
        mod.validate_spec(s)
    s = spec(duration_seconds=2, cues=[cue_entry("main", "tone", 0, 599.5, 1)])
    with pytest.raises(ValueError, match="beyond timeline/source bound"):
        mod.validate_spec(s)


def test_cue_exceeds_timeline_after_sample_quantization():
    """start+duration <= total in float, but rounding start and duration separately overruns."""
    mod = module()
    total = 48000.4 / RATE
    start = 24000.55 / RATE
    duration = 23999.85 / RATE
    assert start + duration <= total + 1e-9
    assert round(start * RATE) + round(duration * RATE) > round(total * RATE)
    s = spec(duration_seconds=total, cues=[cue_entry("main", "tone", start, 0, duration)])
    with pytest.raises(ValueError, match="exceeds timeline after sample quantization"):
        mod.validate_spec(s)


def test_unused_sources_are_refused():
    s = spec(sources=[source_entry("tone", "/tmp/a.wav"), source_entry("other", "/tmp/b.wav")],
             cues=[cue_entry("main", "tone", 0, 0, 2)])
    with pytest.raises(ValueError, match="unused sources"):
        module().validate_spec(s)


def test_repeated_source_across_multiple_cues_is_allowed():
    s = spec(duration_seconds=2, cues=[cue_entry("a", "tone", 0, 0, 1), cue_entry("b", "tone", 1, 0, 1)])
    assert module().validate_spec(copy.deepcopy(s)) == s


def test_work_bound_256_million_source_frames():
    s = spec(duration_seconds=600, cues=[cue_entry(f"c{i}", "tone", 0, 0, 600) for i in range(32)])
    with pytest.raises(ValueError, match="256 million source-frame DSP work bound"):
        module().validate_spec(s)


@pytest.mark.parametrize("envelope", [
    [{"at": 0, "gain_db": 0}],  # single point when nonempty must span at least two
    [{"at": .1, "gain_db": 0}, {"at": 1, "gain_db": -6}],  # does not start at 0
    [{"at": 0, "gain_db": 0}, {"at": .9, "gain_db": -6}],  # does not end at duration
    [{"at": 0, "gain_db": 0}, {"at": 0, "gain_db": -6}, {"at": 1, "gain_db": -6}],  # nonincreasing after quant
])
def test_envelope_must_span_exactly_0_to_cue_duration_strictly_increasing(envelope):
    s = spec(duration_seconds=1, cues=[cue_entry("main", "tone", 0, 0, 1, envelope=envelope)])
    with pytest.raises(ValueError):
        module().validate_spec(s)


def test_words_sidecar_field_requires_speech_role():
    s = spec(sources=[source_entry("s", "/tmp/a.wav", role="music", words="/tmp/a.words.json")],
             cues=[cue_entry("main", "s", 0, 0, 2)])
    with pytest.raises(ValueError, match="words sidecar requires speech role"):
        module().validate_spec(s)


# ---------------------------------------------------------------------------
# validate_timing
# ---------------------------------------------------------------------------

def test_timing_duration_must_match_spec():
    mod = module()
    s = spec(duration_seconds=2)
    timing = {"version": 1, "duration_seconds": 3, "cues": [{"id": "main", "source": "tone",
              "start": 0, "source_start": 0, "duration": 2}]}
    with pytest.raises(ValueError, match="video timing duration changed"):
        mod.validate_timing(timing, s)


def test_timing_cue_must_exist_and_be_unique():
    mod = module()
    s = spec(duration_seconds=2)
    timing = {"version": 1, "duration_seconds": 2, "cues": [{"id": "unknown", "source": "tone",
              "start": 0, "source_start": 0, "duration": 2}]}
    with pytest.raises(ValueError, match="duplicate/unknown timing cue"):
        mod.validate_timing(timing, s)
    timing["cues"] = [{"id": "main", "source": "tone", "start": 0, "source_start": 0, "duration": 2}] * 2
    with pytest.raises(ValueError, match="duplicate/unknown timing cue"):
        mod.validate_timing(timing, s)


def test_timing_constraint_must_exactly_match_spec_cue():
    mod = module()
    s = spec(duration_seconds=2)
    timing = {"version": 1, "duration_seconds": 2, "cues": [{"id": "main", "source": "tone",
              "start": 0, "source_start": 0, "duration": 1.9}]}
    with pytest.raises(ValueError, match="video cue timing changed"):
        mod.validate_timing(timing, s)
    timing["cues"][0]["duration"] = 2
    assert mod.validate_timing(copy.deepcopy(timing), s) == timing


# ---------------------------------------------------------------------------
# gain_curve: fades and envelope are targeted only at their own cue
# ---------------------------------------------------------------------------

def test_gain_curve_linear_fade_in_reaches_unity_and_holds():
    mod = module()
    cue = cue_entry("main", "tone", 0, 0, 1, gain_db=0, fade_in=480 / RATE, fade_out=0)
    gain = mod.gain_curve(cue, 0, RATE)
    assert gain[0] == 0
    assert gain[479] == pytest.approx(1.0)
    assert (gain[480:] == 1.0).all()


def test_gain_curve_envelope_db_ramp_is_linear_in_db_not_linear_gain():
    mod = module()
    cue = cue_entry("main", "tone", 0, 0, 1, envelope=[{"at": 0, "gain_db": 0}, {"at": 1, "gain_db": -20}])
    mid = mod.frame(.5)
    gain = mod.gain_curve(cue, mid, mid + 1)
    assert gain[0] == pytest.approx(10 ** (-10 / 20), rel=1e-3)


def test_gain_curve_cue_gain_db_and_envelope_combine_additively_in_db():
    mod = module()
    cue = cue_entry("main", "tone", 0, 0, 1, gain_db=-6, envelope=[{"at": 0, "gain_db": -6}, {"at": 1, "gain_db": -6}])
    gain = mod.gain_curve(cue, 0, RATE)
    assert gain[100] == pytest.approx(10 ** (-12 / 20), rel=1e-3)


# ---------------------------------------------------------------------------
# propose (round A): zero render, frozen sources, no wav master
# ---------------------------------------------------------------------------

def test_propose_freezes_sources_and_makes_no_audio_call(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    raw = src.read_bytes()
    s = spec(duration_seconds=2, sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    assert result["status"] == "proposal-only"
    assert result["kind"] == "create"
    assert result["audio_created"] is False
    assert result["spend"] == 0
    out = Path(result["approved_plan"]).parent
    assert not list(out.glob("mix_*.wav"))
    assert not list(out.glob("*.take.json"))
    frozen = out / "sources" / "tone.audio"
    assert frozen.read_bytes() == raw
    assert Path(result["approved_plan"]).read_bytes()
    assert result["approval_sha256"] == hashlib.sha256(Path(result["approved_plan"]).read_bytes()).hexdigest()


def test_propose_rejects_blank_or_manifest_marked_description(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    r = propose(tmp_path, s, tmp_path / "out", description="   ")
    assert r["status"] == "FAIL"
    r = propose(tmp_path, s, tmp_path / "out2", description="text\nMIX_MANIFEST\n")
    assert r["status"] == "FAIL"


def test_propose_never_overwrites_existing_output(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep").write_bytes(b"keep me")
    r = propose(tmp_path, s, out)
    assert r["status"] == "FAIL"
    assert (out / "keep").read_bytes() == b"keep me"


# ---------------------------------------------------------------------------
# load_approved / render: approval hash, mutation, renderer drift, wrong kind
# ---------------------------------------------------------------------------

def test_render_refuses_when_approval_sha_does_not_match(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = cli("render", "--approved-plan", result["approved_plan"], "--approval-sha256", "0" * 64,
            "--kind", "create", "--out", tmp_path / "take-01")
    assert r["status"] == "FAIL" and "approval SHA-256" in r["error"] or "changed since approval" in r.get("error", "")
    assert not (tmp_path / "take-01").exists()


def test_render_refuses_when_proposal_text_mutated_after_approval(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    plan = Path(result["approved_plan"])
    plan.write_bytes(plan.read_bytes() + b"\n<!-- tampered -->\n")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL" and "changed since approval" in r["error"]
    assert not (tmp_path / "take-01").exists()


def test_render_refuses_when_frozen_source_changed_after_approval(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    frozen = Path(result["approved_plan"]).parent / "sources" / "tone.audio"
    frozen.write_bytes(frozen.read_bytes()[:-2] + b"\x00\x00")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL"
    assert "changed" in r["error"]
    assert not (tmp_path / "take-01").exists()


def test_render_refuses_wrong_kind_for_proposal(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01", kind="edit")
    assert r["status"] == "FAIL" and "wrong Mix leaf for proposal" in r["error"]
    assert not (tmp_path / "take-01").exists()


def test_render_refuses_when_renderer_drifted(tmp_path):
    script = script_copy(tmp_path)
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1", script=script)
    script.write_bytes(script.read_bytes() + b"\n# drift\n")
    r = render(result, tmp_path / "take-01", script=script)
    assert r["status"] == "FAIL" and "renderer changed" in r["error"]
    assert not (tmp_path / "take-01").exists()


# ---------------------------------------------------------------------------
# render: determinism, normalization, clipping, overrange, silence
# ---------------------------------------------------------------------------

def test_render_is_deterministic_same_approved_plan_twice(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    a = render(result, tmp_path / "take-a")
    b = render(result, tmp_path / "take-b")
    assert a["status"] == b["status"] == "PASS", (a, b)
    assert np.array_equal(pcm(a["master_path"]), pcm(b["master_path"]))
    assert a["measure"]["pcm_sha256"] == b["measure"]["pcm_sha256"]


def test_render_reports_no_audio_and_full_frozen_source_playback(tmp_path):
    src = fixture(tmp_path / "tone.wav", seconds=2)
    s = spec(duration_seconds=2, channels=1, sources=[source_entry("tone", src)],
             cues=[cue_entry("main", "tone", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "PASS", r
    audio = pcm(r["master_path"])
    assert audio.shape == (2 * RATE, 1)
    assert r["auditory_quality"] == "unverified"


def test_normalize_hits_true_peak_and_lufs_target(tmp_path):
    src = fixture(tmp_path / "quiet.wav", "0.05*sin(2*PI*440*t)", seconds=3)
    s = spec(duration_seconds=3, target_lufs=-18, true_peak_dbtp=-1.0,
             sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 3)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "PASS", r
    assert r["measure"]["integrated_lufs"] == pytest.approx(-18, abs=.5)
    assert r["measure"]["true_peak_dbtp"] <= -1.0 + .05


def test_source_clipping_survives_gain_attenuation_still_fails(tmp_path):
    src = fixture(tmp_path / "clipped.wav", "eq(n\\,1000)", rate=96000)
    s = spec(duration_seconds=2, target_lufs=None,
             sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 2, gain_db=-30)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL"
    assert any("clipping" in f for f in r["failures"])
    assert r["source_measures"]["tone"]["native"]["clipping_detected"]


def test_sum_overrange_without_normalization_produces_no_master(tmp_path):
    src = fixture(tmp_path / "loud.wav", "0.9*sin(2*PI*440*t)", seconds=2)
    s = spec(duration_seconds=2, channels=1, target_lufs=None,
             sources=[source_entry("a", src), source_entry("b", src)],
             cues=[cue_entry("ca", "a", 0, 0, 2), cue_entry("cb", "b", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL"
    assert r["master"] is None
    assert any("out-of-range" in f for f in r["failures"])


def test_exact_silence_master_fails(tmp_path):
    src = fixture(tmp_path / "silence.wav", "0", seconds=2)
    s = spec(duration_seconds=2, sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL"
    assert any("silent" in f for f in r["failures"])


# ---------------------------------------------------------------------------
# edit-mix: no-op refused, real revision recreates from originals
# ---------------------------------------------------------------------------

def test_noop_revision_is_refused(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    first = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(first, tmp_path / "take-01")
    assert bundle["status"] == "PASS"
    r = propose(tmp_path, s, tmp_path / "proposal-v2", previous=bundle["out"], index=1)
    assert r["status"] == "FAIL"
    assert "no audio change" in r["error"]


def test_edit_revision_reuses_frozen_originals_and_renders_new_take(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 2, gain_db=0)])
    first = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(first, tmp_path / "take-01")
    assert bundle["status"] == "PASS"
    revised = spec(sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 2, gain_db=-6)])
    r = propose(tmp_path, revised, tmp_path / "proposal-v2", previous=bundle["out"], index=1)
    assert r["status"] == "proposal-only" and r["kind"] == "edit"
    take = render(r, tmp_path / "take-02", kind="edit")
    assert take["status"] == "PASS", take
    assert take["previous"]["master_sha256"] == bundle["master"]["sha256"]
    quieter = pcm(take["master_path"]).astype(float)
    louder = pcm(bundle["master_path"]).astype(float)
    assert abs(quieter).max() < abs(louder).max()


def test_only_a_creative_field_change_and_text_only_change_distinguished(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    first = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(first, tmp_path / "take-01")
    changed_text_only = {**copy.deepcopy(s), "what_for": "a totally different sentence"}
    r = propose(tmp_path, changed_text_only, tmp_path / "proposal-v2", previous=bundle["out"], index=1)
    assert r["status"] == "FAIL" and "no audio change" in r["error"]


# ---------------------------------------------------------------------------
# analyze: lone audio vs verified bundle mismatch
# ---------------------------------------------------------------------------

def test_analyze_lone_source_has_no_recorded_mix(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    r = cli("analyze", src)
    assert r["status"] in ("PASS", "WARN")
    assert r["recorded_mix"] is None
    assert r["auditory_quality"] == "unverified"


def test_analyze_bundle_reports_recorded_spec(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    r = cli("analyze", bundle["master_path"], "--bundle", bundle["out"])
    assert r["status"] in ("PASS", "WARN")
    assert r["recorded_mix"]["duration_seconds"] == s["duration_seconds"]


def test_analyze_source_differing_from_bundle_master_is_refused(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    other = fixture(tmp_path / "other.wav", "0.2*sin(2*PI*880*t)")
    r = cli("analyze", other, "--bundle", bundle["out"])
    assert r["status"] == "FAIL" and "differs from Mix bundle" in r["error"]


# ---------------------------------------------------------------------------
# verify: tamper / missing / captions
# ---------------------------------------------------------------------------

def test_verify_passes_on_freshly_delivered_bundle(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    r = cli("verify", "--bundle", bundle["out"])
    assert r["status"] == "PASS"
    assert r["master"] == bundle["master_path"]


def test_verify_detects_tampered_master_bytes(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    master = Path(bundle["master_path"])
    raw = bytearray(master.read_bytes())
    raw[-2] ^= 0xFF
    master.write_bytes(raw)
    r = cli("verify", "--bundle", bundle["out"])
    assert r["status"] == "FAIL" and "hash mismatch" in r["error"]


def test_verify_detects_missing_source_file(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    (Path(bundle["out"]) / "sources" / "tone.audio").unlink()
    r = cli("verify", "--bundle", bundle["out"])
    assert r["status"] == "FAIL"


def test_verify_refuses_bundle_that_is_not_a_physical_directory(tmp_path):
    r = cli("verify", "--bundle", tmp_path / "missing")
    assert r["status"] == "FAIL" and "physical Mix bundle directory required" in r["error"]


def test_verify_reports_captions_when_present(tmp_path):
    mod = module()
    speech, sidecar, _ = speech_source(mod, tmp_path, "speech.wav", seconds=2)
    s = spec(duration_seconds=2, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("main", "voice", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    assert bundle["status"] in ("PASS", "WARN")
    assert "captions.json" in bundle["files"]
    r = cli("verify", "--bundle", bundle["out"])
    assert r["status"] in ("PASS", "WARN")


# ---------------------------------------------------------------------------
# captions: offset correctness, stale hash, trim crossing a word, overlap
# ---------------------------------------------------------------------------

def test_speech_captions_are_offset_correctly_by_cue_start(tmp_path):
    mod = module()
    speech, sidecar, doc = speech_source(mod, tmp_path, "speech.wav", seconds=2)
    cue_start = 1.0
    s = spec(duration_seconds=3, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("main", "voice", cue_start, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    assert bundle["status"] in ("PASS", "WARN"), bundle
    captions = json.loads((Path(bundle["out"]) / "captions.json").read_text())
    original = doc["words"][0]
    shifted = captions["words"][0]
    assert shifted["start"] == pytest.approx(original["start"] + cue_start, abs=1 / RATE)
    assert shifted["end"] == pytest.approx(original["end"] + cue_start, abs=1 / RATE)
    assert shifted["word"] == original["word"]


def test_stale_pcm_hash_sidecar_is_blocked(tmp_path):
    mod = module()
    speech, sidecar, doc = speech_source(mod, tmp_path, "speech.wav", seconds=2)
    doc["pcm_sha256"] = "0" * 64
    write(sidecar, doc)
    s = spec(duration_seconds=2, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("main", "voice", 0, 0, 2)])
    r = propose(tmp_path, s, tmp_path / "proposal-v1")
    assert r["status"] == "FAIL" and "PCM hash mismatch" in r["error"]


def test_cue_trim_crossing_a_word_boundary_is_blocked(tmp_path):
    mod = module()
    speech, sidecar, doc = speech_source(mod, tmp_path, "speech.wav", seconds=2,
                                         words=(("hello", .1, .6),))
    # A cue ending in the middle of the single word interval [.1, .6).
    s = spec(duration_seconds=1, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("main", "voice", 0, 0, .3)])
    r = propose(tmp_path, s, tmp_path / "proposal-v1")
    assert r["status"] == "FAIL"
    assert "crosses a word/caption/segment" in r["error"]


def test_overlapping_speech_cues_are_blocked(tmp_path):
    mod = module()
    speech, sidecar, _ = speech_source(mod, tmp_path, "speech.wav", seconds=2)
    s = spec(duration_seconds=3, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("a", "voice", 0, 0, 2), cue_entry("b", "voice", 1, 0, 2)])
    r = propose(tmp_path, s, tmp_path / "proposal-v1")
    assert r["status"] == "FAIL"
    assert "overlapping speech cues" in r["error"]


def test_captions_absent_and_warned_when_speech_source_has_no_words(tmp_path):
    src = fixture(tmp_path / "speech.wav", seconds=2)
    s = spec(duration_seconds=2, sources=[source_entry("voice", src, role="speech")],
             cues=[cue_entry("main", "voice", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] != "FAIL", r
    assert "captions.json" not in r["files"]
    assert any("speech timing unavailable" in w for w in r["warnings"])


def test_validate_delivery_refuses_dropped_or_invented_captions(tmp_path):
    mod = module()
    speech, sidecar, _ = speech_source(mod, tmp_path, "speech.wav", seconds=2)
    s = spec(duration_seconds=2, sources=[source_entry("voice", speech, role="speech", words=sidecar)],
             cues=[cue_entry("main", "voice", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    bundle = render(result, tmp_path / "take-01")
    receipt = Path(bundle["out"]) / "mix.take.json"
    master = Path(bundle["master_path"])
    with pytest.raises(ValueError, match="must not be silently dropped or added"):
        mod.validate_delivery(master, receipt, captions_path=None)


def test_missing_dependencies_return_json(tmp_path):
    r = cli("analyze", tmp_path / "missing.wav", env={**os.environ, "PATH": str(tmp_path)})
    assert r["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Channel conversion: mono<->stereo, real primary fixes
# ---------------------------------------------------------------------------

def test_mono_source_to_stereo_duplicates_at_unity_with_identical_columns(tmp_path):
    src = fixture(tmp_path / "mono.wav", "0.2*sin(2*PI*440*t)", seconds=1)
    s = spec(duration_seconds=1, channels=2, sources=[source_entry("tone", src)],
             cues=[cue_entry("main", "tone", 0, 0, 1)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "PASS", r
    assert r["source_measures"]["tone"]["channel_conversion"] == "mono to stereo: duplicate at unity"
    audio = pcm(r["master_path"])
    assert audio.shape == (RATE, 2)
    assert np.array_equal(audio[:, 0], audio[:, 1])


def test_stereo_source_to_mono_is_the_exact_arithmetic_mean(tmp_path):
    mod = module()
    src = fixture(tmp_path / "stereo.wav", "0.2*sin(2*PI*440*t)|0.1*sin(2*PI*440*t)", seconds=1)
    samples, _ = mod.media.decode(src, src.read_bytes())
    expected = mod.media.write_wav(tmp_path / "expected.wav", samples.astype(np.float64).mean(axis=1, keepdims=True))
    s = spec(duration_seconds=1, channels=1, sources=[source_entry("tone", src)],
             cues=[cue_entry("main", "tone", 0, 0, 1)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "PASS", r
    assert r["source_measures"]["tone"]["channel_conversion"] == "stereo to mono: arithmetic mean"
    assert r["source_measures"]["tone"]["mono_fold_energy_delta_db"] == pytest.approx(-0.4575702709, abs=1e-3)
    got = pcm(r["master_path"])
    assert np.array_equal(got[:, 0], (expected * 32768).astype("<i2")[:, 0])


def test_stereo_antiphase_to_mono_warns_energy_loss_while_separate_sfx_keeps_mix_audible(tmp_path):
    """A near-cancelling stereo source folds to (near-)silence, but a separate nonzero
    sfx cue keeps the overall master audible - WARN with the >6dB fold warning, never
    a whole-mix silence FAIL and never a swallowed channel_conversion label."""
    antiphase = fixture(tmp_path / "antiphase.wav", "0.3*sin(2*PI*440*t)|-0.3*sin(2*PI*440*t)", seconds=2)
    sfx = fixture(tmp_path / "sfx.wav", "0.2*sin(2*PI*220*t)", seconds=2)
    s = spec(duration_seconds=2, channels=1,
             sources=[source_entry("voice", antiphase, role="music"), source_entry("sfx", sfx, role="sfx")],
             cues=[cue_entry("cv", "voice", 0, 0, 2), cue_entry("cs", "sfx", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "WARN", r
    assert r["source_measures"]["voice"]["channel_conversion"] == "stereo to mono: arithmetic mean"
    assert any("voice: stereo-to-mono fold loses >6 dB of energy" in w for w in r["warnings"])
    assert not r["measure"]["silence"]
    audio = pcm(r["master_path"])
    assert audio.any()


# ---------------------------------------------------------------------------
# Normalization: scalar constant gain, no second loudnorm pass / limiter
# ---------------------------------------------------------------------------

def test_normalization_dict_is_scalar_gain_with_no_limiter_or_filter_field(tmp_path):
    src = fixture(tmp_path / "quiet.wav", "0.05*sin(2*PI*440*t)", seconds=3)
    s = spec(duration_seconds=3, target_lufs=-18, true_peak_dbtp=-1.0,
             sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 3)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "PASS", r
    normalization = r["normalization"]
    assert normalization["status"] == "measured"
    assert set(normalization) == {"status", "first_pass", "gain_db", "method"}
    assert "filter" not in normalization
    assert "no limiter" in normalization["method"]
    assert isinstance(normalization["gain_db"], float)


def test_strong_transient_infeasible_loudness_peak_pair_fails_without_limiter(tmp_path):
    """A brief loud burst in mostly silence needs a large gain to reach the requested
    loudness, which would blow past the true-peak ceiling: the constant-gain scheme
    must FAIL rather than silently invoke a limiter, and the delivered PCM must stay
    byte-identical to the untouched pre-normalization candidate."""
    mod = module()
    src = fixture(tmp_path / "burst.wav", "if(lt(mod(t\\,1)\\,0.005)\\,0.4\\,0)", seconds=3)
    samples, _ = mod.media.decode(src, src.read_bytes())
    expected_measure = mod.media.measure(mod.media.write_wav(tmp_path / "expected.wav", samples.astype(np.float64)),
                                         "pcm_s16le")
    s = spec(duration_seconds=3, target_lufs=-14, true_peak_dbtp=-1.0,
             sources=[source_entry("tone", src)], cues=[cue_entry("main", "tone", 0, 0, 3)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "FAIL", r
    assert r["normalization"]["status"] == "FAIL"
    assert "constant gain cannot meet both loudness and true-peak targets" in r["normalization"]["reason"]
    assert "no limiter" in r["normalization"]["method"]
    assert any("constant gain cannot meet both loudness and true-peak targets" in f for f in r["failures"])
    assert r["measure"]["pcm_sha256"] == expected_measure["pcm_sha256"]


def test_sum_overrange_with_achievable_target_normalizes_into_range_and_warns(tmp_path):
    """Two full-level sources sum past full scale in float, but a modest target_lufs
    is achievable by a negative scalar gain: this is WARN (with the explicit
    before-normalization warning), never a silent pass and never a refused master."""
    src = fixture(tmp_path / "loud.wav", "0.7*sin(2*PI*440*t)", seconds=2)
    s = spec(duration_seconds=2, target_lufs=-20, true_peak_dbtp=-1.0,
             sources=[source_entry("a", src), source_entry("b", src)],
             cues=[cue_entry("ca", "a", 0, 0, 2), cue_entry("cb", "b", 0, 0, 2)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["status"] == "WARN", r
    assert r["pre_normalization_measure"]["out_of_range_count"] > 0
    assert any("floating-point sum exceeds full scale before approved constant-gain normalization"
               in w for w in r["warnings"])
    assert r["normalization"]["status"] == "measured"
    assert r["master"] is not None
    audio = pcm(r["master_path"]).astype(float)
    assert np.abs(audio).max() < 32768


def test_output_policy_recorded_exactly_as_approved(tmp_path):
    src = fixture(tmp_path / "tone.wav")
    s = spec(duration_seconds=2, target_lufs=-16, true_peak_dbtp=-2.5, sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    r = render(result, tmp_path / "take-01")
    assert r["output_policy"] == {"target_lufs": -16, "true_peak_dbtp": -2.5}


def test_render_with_normalization_target_still_reproduces_identical_pcm(tmp_path):
    src = fixture(tmp_path / "tone.wav", "0.05*sin(2*PI*440*t)", seconds=2)
    s = spec(duration_seconds=2, target_lufs=-18, true_peak_dbtp=-1.0, sources=[source_entry("tone", src)])
    result = propose(tmp_path, s, tmp_path / "proposal-v1")
    a = render(result, tmp_path / "take-a")
    b = render(result, tmp_path / "take-b")
    assert a["status"] == b["status"] == "PASS", (a, b)
    assert np.array_equal(pcm(a["master_path"]), pcm(b["master_path"]))
    assert a["measure"]["pcm_sha256"] == b["measure"]["pcm_sha256"]
    assert a["normalization"]["gain_db"] == b["normalization"]["gain_db"]
