"""Real music proposal/approval integration; only inference is faked, never approval."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import shlex
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import wave

import pytest

HERMES = Path(__file__).resolve().parents[2]
SCRIPTS = HERMES / "profiles/audio-creator/skills/audio-creator-pipeline/scripts"
PLAN = SCRIPTS / "music_plan.py"
MEDIA = SCRIPTS / "music-media.py"
PLUGIN = HERMES / "plugins/audio_gen/music-gen/__init__.py"
PROMPT = "Instrumental glassy sine melody, sparse and steady, no vocals.\n"
ARRANGEMENT = "Play middle C for two quarter-note beats, then leave one second of silence.\n"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def plan():
    return load(PLAN, "music_plan_integration")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def prohibited(*args, **kwargs):
        pytest.fail("network access is forbidden in music plan tests")

    monkeypatch.setattr(socket.socket, "connect", prohibited)
    monkeypatch.setattr(socket.socket, "connect_ex", prohibited)
    monkeypatch.setattr(socket, "create_connection", prohibited)


@pytest.fixture
def inputs(tmp_path):
    def make(kind="create", **changes):
        root = tmp_path / f"input-{len(list(tmp_path.iterdir()))}"
        root.mkdir()
        form = {"what_for": "A title cue", "theme": "quiet discovery", "style": "minimal sine",
                "duration": 2 if kind == "create" else 5, **changes}
        score = {"version": 1, "bpm": 120, "meter": "4/4", "key": "C major",
                 "duration_seconds": 2, "tracks": [{"id": "lead", "instrument": "sine",
                     "notes": [{"pitch": 60, "start": 0, "duration": 2}]}]}
        form_file, arrangement_file = root / "form.json", root / "arrangement.txt"
        artifact = root / ("score.json" if kind == "create" else "prompt.txt")
        form_file.write_text(json.dumps(form), encoding="utf-8")
        arrangement_file.write_text(ARRANGEMENT, encoding="utf-8")
        # Noncanonical whitespace must survive approval and rendering byte-for-byte.
        artifact.write_bytes((json.dumps(score, indent=3) + "\r\n" if kind == "create" else PROMPT).encode())
        return {"kind": kind, "form_file": form_file, "arrangement_file": arrangement_file,
                "out": root / "proposal", ("score_file" if kind == "create" else "prompt_file"): artifact}

    return make


def approval(result):
    return {key: result[key] for key in ("approved_plan", "approval_sha256")}


def cli(script, *args):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True, timeout=30)
    lines = proc.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("RESULT: "), (proc.stdout, proc.stderr)
    result = json.loads(lines[0][8:])
    assert (proc.returncode != 0) == (result["status"] == "FAIL"), result
    if "error" in result:
        assert proc.returncode == 2
    return result


def create_args(result, out):
    return ["create", "--approved-plan", result["approved_plan"],
             "--approval-sha256", result["approval_sha256"], "--out", str(out)]


@pytest.mark.parametrize("kind", ["create", "generate"])
def test_guard_allows_real_proposal_under_mv_named_job(inputs, tmp_path, kind):
    """The real terminal guard precedes the real zero-media proposal command."""
    guard = load(HERMES / "plugins/skill-topology/__init__.py", "music_plan_guard")
    request = inputs(kind)
    parent = tmp_path / "character-mv-no-voice" / "music-plan"
    parent.mkdir(parents=True)
    args = ["propose", "--kind", kind, "--form-file", request["form_file"],
            "--arrangement-file", request["arrangement_file"], "--out", parent / "proposal-v1"]
    artifact = "score_file" if kind == "create" else "prompt_file"
    args.extend(["--" + artifact.replace("_", "-"), request[artifact]])
    command = shlex.join([sys.executable, str(PLAN), *map(str, args)])
    assert guard._guard_managed_skill_writes(
        tool_name="terminal", args={"command": command, "workdir": str(tmp_path)}) is None
    result = cli(PLAN, *args)
    assert result["status"] == "proposal-only"
    assert result["spend"] == 0 and result["audio_created"] is False
    assert Path(result["approved_plan"]).parent == parent / "proposal-v1"
    assert not list(parent.rglob("*.wav"))
    blocked = guard._guard_managed_skill_writes(
        tool_name="terminal", args={"command": command + " > " + shlex.quote(str(PLAN)),
                                    "workdir": str(tmp_path)})
    assert blocked["action"] == "block"


@pytest.fixture
def rig(monkeypatch, tmp_path):
    plugin = load(PLUGIN, "music_gen_plan_integration")
    runtime = SimpleNamespace(
        status=Mock(return_value={"available": True, "fingerprint": {"runtime_identity": "test-runtime"}}),
        is_busy=Mock(return_value=False),
    )

    def render(payload, bundle):
        state = json.loads((bundle.parent / "state.json").read_text())
        assert state["attempts"][-1]["status"] == "running"
        assert state["attempts"][-1]["payload"] == payload
        bundle.mkdir()
        frames = round(payload["duration_seconds"] * 44100)
        pcm = b"\x10\x00\xf0\xff" * frames
        with wave.open(str(bundle / "raw.wav"), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(44100)
            stream.writeframes(pcm)
        receipt = {"engine": plugin.LOCAL_ENGINE, "request": dict(payload),
                   "model": {"runtime_fingerprint": "test-runtime"},
                   "raw_wav": {"sha256_file": sha((bundle / "raw.wav").read_bytes()),
                               "sha256_pcm": sha(pcm), "frames": frames, "sample_rate": 44100,
                               "channels": 2, "sample_width_bytes": 2}}
        (bundle / "take.json").write_text(json.dumps(receipt))
        (bundle / "inference.log").write_text("Test fixture only; no inference performed.\n")
        return {"status": "raw-needs-qa", "receipt": receipt, "raw": str(bundle / "raw.wav")}

    runtime.render_music = Mock(side_effect=render)
    factory = Mock(return_value=runtime)
    monkeypatch.setattr(plugin, "_runtime", factory)
    return SimpleNamespace(plugin=plugin, runtime=runtime, factory=factory, job=tmp_path.resolve() / "job")


def generate(rig, action="start", **args):
    return json.loads(rig.plugin.generate({"action": action, "job_dir": str(rig.job), **args}))


@pytest.mark.parametrize("kind", ["create", "generate"])
def test_proposal_has_consistent_visible_manifest_exact_artifact_and_no_audio(plan, inputs, rig, monkeypatch, kind):
    request = inputs(kind)
    source = request.get("score_file", request.get("prompt_file"))
    original = source.read_bytes()
    spawn = Mock(side_effect=AssertionError("proposal must not invoke any subprocess/model"))
    monkeypatch.setattr(subprocess, "Popen", spawn)
    result = plan.propose(**request)
    assert result["status"] == "proposal-only"
    assert result["spend"] == 0 and result["audio_created"] is False
    raw = Path(result["approved_plan"]).read_bytes()
    assert result["approval_sha256"] == sha(raw)
    document = raw.decode()
    assert ARRANGEMENT.rstrip() in document
    visible = json.loads(document.split("```json\n", 1)[1].split("\n```", 1)[0])
    hidden = json.loads(document.split(plan.START, 1)[1].split(plan.END, 1)[0])
    assert visible == hidden
    assert visible["settings"] == result["settings"]
    assert visible["form"]["duration"] == result["settings"]["duration_seconds"]
    assert visible["form"]["direction"] == "steady"
    assert visible["form"]["ending"] == "resolve"
    assert visible["artifact"]["sha256"] == sha(original)
    assert Path(result["artifact"]).read_bytes() == source.read_bytes() == original
    checked = plan.load_approved(result["approved_plan"], result["approval_sha256"], kind)
    assert checked["artifact_text"].encode() == original
    assert checked["artifact_sha256"] == sha(original)
    assert checked["form"] == visible["form"] and checked["settings"] == visible["settings"]
    assert {p.name for p in request["out"].iterdir()} == {"proposal.md", visible["artifact"]["file"]}
    if kind == "create":
        assert visible["settings"] == {"duration_seconds": 2, "bpm": 120, "meter": "4/4", "key": "C major"}
        assert visible["form"]["tempo"] == "120 BPM"
    else:
        assert visible["settings"] == {"engine": plan.LOCAL, "duration_seconds": 5,
                                       "seed": 0, "max_calls": 3, "max_usd": None}
    spawn.assert_not_called()
    rig.factory.assert_not_called()
    rig.runtime.render_music.assert_not_called()


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe required for real rendering")
def test_cli_propose_check_and_real_create_repeat_exact_pcm(inputs, tmp_path):
    request = inputs()
    argv = ["propose"]
    for key, value in request.items():
        argv.extend(["--" + key.replace("_", "-"), str(value)])
    result = cli(PLAN, *argv)
    assert result["status"] == "proposal-only", result
    checked = cli(PLAN, "check", "--kind", "create", "--approved-plan", result["approved_plan"],
                  "--approval-sha256", result["approval_sha256"])
    assert checked["status"] == "PASS" and checked["settings"] == result["settings"]
    original = request["score_file"].read_bytes()
    samples = []
    reports = []
    for name in ("first", "second"):
        out = tmp_path / name
        rendered = cli(MEDIA, *create_args(result, out))
        assert rendered["status"] == "PASS", rendered
        assert rendered["approval_sha256"] == result["approval_sha256"]
        assert rendered["score_sha256"] == sha(original)
        assert (out / "score.json").read_bytes() == original
        evidence = json.loads((out / "approval.json").read_text())
        assert evidence["artifact_text"].encode() == original
        assert evidence["form"]["key"] == "C major"
        assert evidence["settings"] == result["settings"]
        assert rendered["score"] == json.loads(original)
        assert rendered["seed"] == 0 and "seed" not in rendered["score"]
        with wave.open(rendered["master"], "rb") as stream:
            assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (48000, 2, 2)
            assert stream.getnframes() == 96000
            pcm = stream.readframes(stream.getnframes())
        assert any(pcm[:48000 * 4]) and not any(pcm[48000 * 4:])
        assert rendered["render"]["notes"][0]["start_frame"] == 0
        assert rendered["render"]["notes"][0]["end_frame_exclusive"] == 48000
        assert rendered["auditory_quality"] == "unverified"
        samples.append(pcm)
        reports.append(rendered)
    assert samples[0] == samples[1]
    assert reports[0]["pcm_sha256"] == reports[1]["pcm_sha256"]
    assert reports[0]["environment_sha256"] == reports[1]["environment_sha256"]
    assert request["score_file"].read_bytes() == original
    first = tmp_path / "first"
    before = {path.name: path.read_bytes() for path in first.iterdir()}
    refused = cli(MEDIA, *create_args(result, first))
    assert refused["status"] == "FAIL" and "NEW directory" in refused["error"]
    assert {path.name: path.read_bytes() for path in first.iterdir()} == before


def test_real_generate_approval_start_resume_and_default_three_call_grant(plan, inputs, rig):
    result = plan.propose(**inputs("generate"))
    rig.factory.assert_not_called()
    started = generate(rig, **approval(result))
    assert started["success"] and started["status"] == "raw-needs-qa", started
    assert started["max_calls"] == 3 and started["calls"] == 1
    assert started["estimated_usd"] == 0 and started["perceptual_qa"] == "unverified"
    assert started["approval_sha256"] == result["approval_sha256"]
    assert rig.runtime.render_music.call_args.args[0] == {"text": PROMPT, "duration_seconds": 5, "seed": 0}
    assert Path(started["raw"]).is_file() and Path(started["take_json"]).is_file()
    before = (rig.job / "state.json").read_bytes()
    assert not generate(rig, **approval(result))["success"]
    assert (rig.job / "state.json").read_bytes() == before
    assert rig.runtime.render_music.call_count == 1
    assert generate(rig, "resume")["status"] == "raw-needs-qa"
    assert rig.runtime.render_music.call_count == 1
    assert generate(rig, "next")["calls"] == 2
    assert generate(rig, "next")["calls"] == 3
    assert not generate(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 3
    state = json.loads((rig.job / "state.json").read_text())
    assert state["frozen"]["settings"] == result["settings"]
    assert [take["payload"]["seed"] for take in state["attempts"]] == [0, 1, 2]


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_generate_one_attempt_grant_from_documented_internal_controls(plan, inputs, rig, outcome):
    """SKILL.md's 'Internal local one-attempt controls' example is a real max_calls: 1 grant."""
    skill = HERMES / "profiles/audio-creator/skills/audio-creator-pipeline/generate/music/SKILL.md"
    fenced = skill.read_text().split("Internal local one-attempt controls", 1)[1]
    controls = json.loads(fenced.split("```json", 1)[1].split("```", 1)[0])

    request = inputs("generate", **controls)
    argv = ["propose"]
    for key, value in request.items():
        argv.extend(["--" + key.replace("_", "-"), str(value)])
    result = cli(PLAN, *argv)
    assert result["status"] == "proposal-only"
    assert result["spend"] == 0 and result["audio_created"] is False
    document = Path(result["approved_plan"]).read_text()
    visible = json.loads(document.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert visible["settings"]["max_calls"] == 1 and visible["settings"]["max_usd"] is None
    assert "max_usd" not in visible["form"]
    checked = plan.load_approved(result["approved_plan"], result["approval_sha256"], "generate")
    assert checked["settings"] == visible["settings"]
    rig.factory.assert_not_called()

    if outcome == "failure":
        rig.runtime.render_music.side_effect = RuntimeError("synthetic inference failure")
    started = generate(rig, **approval(result))
    state = json.loads((rig.job / "state.json").read_text())
    assert len(state["attempts"]) == 1 and state["frozen"]["settings"] == result["settings"]
    if outcome == "failure":
        assert not started["success"] and state["attempts"][0]["status"] == "failed"
        assert not generate(rig, "resume")["success"]
    else:
        assert started["success"] and started["status"] == "raw-needs-qa"
        assert started["max_calls"] == 1 and started["calls"] == 1
        assert generate(rig, "resume")["status"] == "raw-needs-qa"
    assert not generate(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 1
    assert len(json.loads((rig.job / "state.json").read_text())["attempts"]) == 1


def test_real_approval_does_not_make_invalid_runtime_receipt_successful(plan, inputs, rig):
    result = plan.propose(**inputs("generate"))
    render = rig.runtime.render_music.side_effect

    def wrong_receipt(payload, bundle):
        rendered = render(payload, bundle)
        rendered["receipt"]["model"]["runtime_fingerprint"] = "different-runtime"
        (bundle / "take.json").write_text(json.dumps(rendered["receipt"]))
        return rendered

    rig.runtime.render_music.side_effect = wrong_receipt
    assert not generate(rig, **approval(result))["success"]
    state = json.loads((rig.job / "state.json").read_text())
    assert len(state["attempts"]) == 1 and state["attempts"][0]["status"] == "failed"
    assert not generate(rig, "resume")["success"]
    assert rig.runtime.render_music.call_count == 1


@pytest.mark.parametrize("kind", ["create", "generate"])
def test_approval_hash_covers_visible_effective_fields_not_only_hidden_manifest(plan, inputs, kind):
    result = plan.propose(**inputs(kind))
    path = Path(result["approved_plan"])
    raw = path.read_bytes()
    visible, marker, hidden = raw.partition(plan.START.encode())
    changed = visible.replace(b'"direction": "steady"', b'"direction": "chaotic"') + marker + hidden
    assert changed != raw and changed.partition(marker)[2] == hidden
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="proposal hash differs"):
        plan.load_approved(path, result["approval_sha256"], kind)


@pytest.mark.parametrize("kind", ["create", "generate"])
@pytest.mark.parametrize("damage", ["missing-hash", "missing-plan", "missing-both", "wrong-hash",
                                    "malformed-hash", "uppercase-hash", "body", "artifact", "reference", "kind"])
def test_actual_approval_failures_prevent_audio(plan, inputs, rig, tmp_path, monkeypatch, kind, damage):
    reference = tmp_path / "reference.wav"
    with wave.open(str(reference), "wb") as stream:
        stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 8000)
    request = inputs("generate" if kind == "create" and damage == "kind" else
                     "create" if kind == "generate" and damage == "kind" else kind,
                     reference_audio=str(reference), reference_focus="rhythmic density only")
    result = plan.propose(**request)
    args = approval(result)
    if damage == "missing-hash":
        del args["approval_sha256"]
    elif damage == "missing-plan":
        del args["approved_plan"]
    elif damage == "missing-both":
        args = {}
    elif damage in ("wrong-hash", "malformed-hash", "uppercase-hash"):
        args["approval_sha256"] = {"wrong-hash": "0" * 64, "malformed-hash": "approved",
                                   "uppercase-hash": result["approval_sha256"].upper()}[damage]
    elif damage == "body":
        path = Path(result["approved_plan"])
        path.write_bytes(path.read_bytes().replace(b"one second of silence", b"one second of cymbals"))
    elif damage == "artifact":
        path = Path(result["artifact"])
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "reference":
        raw = bytearray(reference.read_bytes())
        raw[-1] ^= 1
        reference.write_bytes(raw)
    if kind == "generate":
        failed = generate(rig, **args)
        assert not failed["success"], failed
        assert not rig.job.exists()
        rig.factory.assert_not_called()
        rig.runtime.render_music.assert_not_called()
    else:
        media = load(MEDIA, "music_media_approval_rejections")
        spawn = Mock(side_effect=AssertionError("invalid approval reached audio processing"))
        monkeypatch.setattr(subprocess, "Popen", spawn)
        argv = ["create", "--out", str(tmp_path / "audio")]
        for key, value in args.items():
            argv.extend(["--" + key.replace("_", "-"), value])
        with pytest.raises((ValueError, OSError)):
            media.execute(media.parser().parse_args(argv))
        assert not (tmp_path / "audio").exists()
        spawn.assert_not_called()


@pytest.mark.parametrize("kind,controls", [
    ("create", {"seed": 4}), ("create", {"engine": "local:stable-audio-3-medium"}),
    ("generate", {"loop": True}), ("generate", {"prompt_influence": .5}),
    ("generate", {"paid_approved": True}), ("generate", {"enable_prompt_expansion": True}),
    ("generate", {"output_format": "mp3"}), ("generate", {"model": "auto"}),
    ("generate", {"seed": -1}), ("generate", {"seed": 2**32}),
    ("generate", {"seed": True}), ("generate", {"seed": 1.5}), ("generate", {"seed": "1"}),
    ("generate", {"duration": 0}), ("generate", {"duration": .99}),
    ("generate", {"duration": 60.01}), ("generate", {"duration": True}),
    ("generate", {"duration": None}), ("generate", {"max_calls": 0}),
    ("generate", {"max_calls": 9}), ("generate", {"max_calls": True}),
    ("generate", {"max_calls": 1.5}), ("generate", {"max_usd": 0}),
    ("generate", {"max_usd": None}), ("generate", {"engine": "auto"}),
    ("generate", {"engine": "fal:stable-audio-3-medium"}),
    ("generate", {"engine": "fal:stable-audio-3-medium", "max_usd": 1}),
    ("generate", {"engine": "fal:stable-audio-3-medium", "max_calls": 3}),
    ("generate", {"engine": "fal:stable-audio-3-medium", "max_calls": 3, "max_usd": .0376}),
])
def test_unsupported_controls_refused_without_proposal(plan, inputs, rig, kind, controls):
    request = inputs(kind, **controls)
    with pytest.raises(ValueError):
        plan.propose(**request)
    assert not request["out"].exists()
    rig.factory.assert_not_called()


@pytest.mark.parametrize("field,value", [("tempo", "121 BPM"), ("tempo", "119.5"),
                                         ("duration", 3), ("key", "G major"), ("meter", "3/4")])
def test_create_form_must_match_exact_score_without_rewriting(plan, inputs, field, value):
    request = inputs(**{field: value})
    before = request["score_file"].read_bytes()
    with pytest.raises(ValueError, match="differs"):
        plan.propose(**request)
    assert request["score_file"].read_bytes() == before
    assert not request["out"].exists()


@pytest.mark.parametrize("mismatch", [False, True])
def test_user_supplied_score_must_match_and_is_hash_bound(plan, inputs, tmp_path, mismatch):
    supplied = tmp_path / "user-score.json"
    request = inputs(score=str(supplied))
    score = json.loads(request["score_file"].read_bytes())
    if mismatch:
        score["tracks"][0]["notes"][0]["pitch"] = 61
    supplied.write_text(json.dumps(score))
    original = supplied.read_bytes()
    if mismatch:
        with pytest.raises(ValueError, match="supplied score must match"):
            plan.propose(**request)
        assert not request["out"].exists()
    else:
        result = plan.propose(**request)
        manifest = plan.load_approved(result["approved_plan"], result["approval_sha256"], "create")
        assert manifest["inputs"] == [{"role": "score", "path": str(supplied),
                                       "sha256": sha(original), "bytes": len(original)}]
        supplied.write_bytes(original + b" ")
        with pytest.raises(ValueError, match="reference input changed"):
            plan.load_approved(result["approved_plan"], result["approval_sha256"], "create")
    assert request["score_file"].read_bytes().endswith(b"\r\n")


@pytest.mark.parametrize("kind", ["create", "generate"])
def test_artist_intent_and_free_custom_fields_retained_verbatim(plan, inputs, kind):
    fields = {"theme": "my own lunar observatory after closing", "style": "my handmade glass-and-static style",
              "theme_detail": "Artist intent: retain the uneasy pauses, not a genre preset.",
              "instrumentation": "sine color, no acoustic piano claim", "direction": "a single hesitant arrival",
              "must_keep": "the second half remains empty", "note": "Do not simplify my custom wording."}
    result = plan.propose(**inputs(kind, **fields))
    checked = plan.load_approved(result["approved_plan"], result["approval_sha256"], kind)
    for key, value in fields.items():
        assert checked["form"][key] == value
        assert value in Path(result["approved_plan"]).read_text()


@pytest.mark.parametrize("raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
                                  '{"x":1e999}', '{"nested":[1e999]}',
                                  '{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}'])
def test_json_parser_rejects_nonfinite_and_duplicate_keys(plan, raw):
    with pytest.raises(ValueError):
        plan.parse_json(raw)


@pytest.mark.parametrize("file", ["form_file", "score_file"])
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e999", "duplicate"])
def test_propose_rejects_bad_json_in_real_inputs(plan, inputs, file, value):
    request = inputs()
    path = request[file]
    raw = path.read_text()
    field = "duration" if file == "form_file" else "bpm"
    original = '"duration": 2' if file == "form_file" else '"bpm": 120'
    replacement = f'"{field}": {value}' if value != "duplicate" else f'{original}, {original}'
    path.write_text(raw.replace(original, replacement))
    with pytest.raises(ValueError):
        plan.propose(**request)
    assert not request["out"].exists()


@pytest.mark.parametrize("file", ["form_file", "arrangement_file", "score_file", "reference_audio"])
@pytest.mark.parametrize("unsafe", ["symlink", "fifo", "device", "directory"])
def test_propose_refuses_nonregular_inputs_without_hanging(plan, inputs, tmp_path, file, unsafe):
    request = inputs()
    path = tmp_path / "unsafe"
    if unsafe == "symlink":
        path.symlink_to(request["score_file"])
    elif unsafe == "fifo":
        os.mkfifo(path)
    elif unsafe == "device":
        path = Path("/dev/zero")
    else:
        path.mkdir()
    if file == "reference_audio":
        form = json.loads(request["form_file"].read_text())
        form.update(reference_audio=str(path), reference_focus="rhythm only")
        request["form_file"].write_text(json.dumps(form))
    else:
        request[file] = path
    with pytest.raises((ValueError, OSError)):
        plan.propose(**request)
    assert not request["out"].exists()


@pytest.mark.parametrize("target", ["plan", "artifact"])
def test_approval_refuses_replaced_symlink(plan, inputs, tmp_path, target):
    result = plan.propose(**inputs())
    path = Path(result["approved_plan" if target == "plan" else "artifact"])
    saved = tmp_path / "saved"
    path.rename(saved)
    path.symlink_to(saved)
    with pytest.raises(OSError):
        plan.load_approved(result["approved_plan"], result["approval_sha256"], "create")


@pytest.mark.parametrize("kind", ["empty", "populated", "file", "symlink", "dangling", "missing-parent"])
def test_proposal_never_overwrites_existing_output(plan, inputs, tmp_path, kind):
    request = inputs()
    out = request["out"]
    if kind in ("empty", "populated"):
        out.mkdir()
        if kind == "populated":
            (out / "keep").write_bytes(b"keep me")
    elif kind == "file":
        out.write_bytes(b"keep me")
    elif kind in ("symlink", "dangling"):
        out.symlink_to(request["score_file"] if kind == "symlink" else tmp_path / "missing")
    else:
        request["out"] = out / "missing" / "proposal"
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    original = request["score_file"].read_bytes()
    with pytest.raises(ValueError):
        plan.propose(**request)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before
    assert request["score_file"].read_bytes() == original
    if kind == "populated":
        assert (out / "keep").read_bytes() == b"keep me"
    elif kind == "file":
        assert out.read_bytes() == b"keep me"


@pytest.mark.parametrize("prompt", ["", "Instrumental piano only", "Piano, no vocals.",
                                    "Instrumental " + "x" * 430 + " no vocals."])
def test_prompt_requires_bounded_explicit_instrumental_no_vocals(plan, inputs, prompt):
    request = inputs("generate")
    request["prompt_file"].write_text(prompt)
    with pytest.raises(ValueError):
        plan.propose(**request)
    assert not request["out"].exists()
