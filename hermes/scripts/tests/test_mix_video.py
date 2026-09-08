"""VideoCreator's Mix consumption: the preliminary `timing` freeze helper,
the STAGED-delivery validation that backs `create-ad`/`create-tour`'s opt-in
`audio_workflow: mix` (see hermes/AGENTS.md "audio_workflow"), and their
markup/plan-level integration. `mix_audio.py` never reimplements Audio Mix's
own hash/format/receipt checks - real bundles here are built through Audio
Mix's OWN `mix-media.py` `propose`/`render`, never hand-faked, except where a
test explicitly needs a genuinely-tampered/invalid receipt to prove a
rejection.
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIDEO_PIPELINE = ROOT.parent / "profiles/video-creator/skills/video-creator-pipeline"
AD_LEAF = VIDEO_PIPELINE / "create/ad"
TOUR_LEAF = VIDEO_PIPELINE / "create/tour"
AUDIO_MIX_SCRIPTS = ROOT.parent / "profiles/audio-creator/skills/audio-creator-pipeline/scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mix_audio = _load("mix_audio", VIDEO_PIPELINE / "scripts/mix_audio.py")
mix_media = _load("mix_media", AUDIO_MIX_SCRIPTS / "mix-media.py")
ad = _load("ad_render", AD_LEAF / "scripts/ad-render.py")
authored = _load("authored_tour", TOUR_LEAF / "scripts/authored.py")
ad_example = _load("create_ad_example", Path(__file__).parent / "fixtures/create-ad/example.py")


def _cue(id="intro", source="voice", start=0, source_start=0, duration=5):
    return {"id": id, "source": source, "start": start, "source_start": source_start,
            "duration": duration}


def valid_spec(**overrides):
    spec = {"version": 1, "duration_seconds": 20, "cues": [_cue()]}
    spec.update(overrides)
    return spec


def test_validate_timing_spec_accepts_a_well_formed_spec():
    spec = valid_spec()
    assert mix_audio.validate_timing_spec(spec) == spec


@pytest.mark.parametrize("mutate,message", [
    (lambda s: s.pop("version"), "exactly version"),
    (lambda s: s.__setitem__("version", 2), "version must be 1"),
    (lambda s: s.__setitem__("extra", 1), "exactly version"),
    (lambda s: s.__setitem__("duration_seconds", 0), "duration_seconds"),
    (lambda s: s.__setitem__("duration_seconds", 601), "duration_seconds"),
    (lambda s: s.__setitem__("duration_seconds", True), "finite number"),
    (lambda s: s.__setitem__("cues", []), "cues"),
    (lambda s: s.__setitem__("cues", [_cue()] * 33), "cues"),
])
def test_validate_timing_spec_rejects_bad_top_level_shape(mutate, message):
    spec = valid_spec()
    mutate(spec)
    with pytest.raises(ValueError, match=message):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_duplicate_cue_ids():
    spec = valid_spec(cues=[_cue(id="a"), _cue(id="a", start=10)])
    with pytest.raises(ValueError, match="duplicate cue id"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_a_cue_extending_past_the_timeline():
    spec = valid_spec(duration_seconds=10, cues=[_cue(start=8, duration=5)])
    with pytest.raises(ValueError, match="fit fully inside"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_zero_or_negative_duration():
    spec = valid_spec(cues=[_cue(duration=0)])
    with pytest.raises(ValueError, match="greater than zero"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_negative_start():
    spec = valid_spec(cues=[_cue(start=-1)])
    with pytest.raises(ValueError, match="must be within"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_boolean_times():
    # type(True) is bool, not int/float - a boolean must never pass as a
    # disguised 1/0 duration or start.
    spec = valid_spec(cues=[_cue(duration=True)])
    with pytest.raises(ValueError, match="finite number"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_missing_or_extra_cue_fields():
    cue = _cue()
    del cue["source_start"]
    with pytest.raises(ValueError, match="exactly id, source, start, source_start, duration"):
        mix_audio.validate_timing_spec(valid_spec(cues=[cue]))


def test_validate_timing_spec_rejects_a_bad_slug():
    with pytest.raises(ValueError, match="slug"):
        mix_audio.validate_timing_spec(valid_spec(cues=[_cue(id="Not_A_Slug")]))


def test_validate_timing_spec_rejects_a_cue_source_slug_reused_is_allowed():
    # Multiple cues MAY reference the same source slug (e.g. two placements
    # of one music bed); only cue ids must be unique.
    spec = valid_spec(duration_seconds=20,
                       cues=[_cue(id="a", source="music", start=0, duration=5),
                             _cue(id="b", source="music", start=10, duration=5)])
    assert mix_audio.validate_timing_spec(spec) == spec


def test_timing_cli_freezes_spec_and_reports_hash(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec = valid_spec()
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "out"
    result = mix_audio.timing(SimpleNamespace(spec_file=str(spec_path), out=str(out)))
    assert result["status"] == "timing-only"
    assert result["cues"] == 1
    assert result["duration_seconds"] == spec["duration_seconds"]
    frozen = out / "timing.json"
    assert frozen.is_file()
    assert json.loads(frozen.read_text(encoding="utf-8")) == spec
    import hashlib
    assert result["sha256"] == hashlib.sha256(frozen.read_bytes()).hexdigest()


def test_timing_cli_never_overwrites_an_existing_out_dir(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(valid_spec()), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="must not exist"):
        mix_audio.timing(SimpleNamespace(spec_file=str(spec_path), out=str(out)))


def test_timing_cli_rejects_an_invalid_spec_without_writing_anything(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(valid_spec(duration_seconds=0)), encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        mix_audio.timing(SimpleNamespace(spec_file=str(spec_path), out=str(out)))
    assert not out.exists()


def test_timing_cli_rejects_a_spec_file_outside_json_suffix(tmp_path):
    spec_path = tmp_path / "spec.txt"
    spec_path.write_text(json.dumps(valid_spec()), encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="local file or not"):
        mix_audio.timing(SimpleNamespace(spec_file=str(spec_path), out=str(out)))


# ── real Mix bundle fixtures, built through Audio Mix's OWN propose/render ──

def make_tone_wav(path, seconds=2.0, rate=48000, freq=440.0, amplitude=0.2, silent=False):
    import math
    n = round(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        if silent:
            handle.writeframes(b"\x00\x00" * n)
        else:
            frames = bytearray()
            for i in range(n):
                sample = int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / rate))
                frames += sample.to_bytes(2, "little", signed=True)
            handle.writeframes(bytes(frames))


def build_mix_bundle(tmp_path, duration=6.0, slug="mix", silent=False, timing=False):
    """Build a REAL, complete Mix bundle by calling Audio Mix's own
    `propose()`/`render()` directly - never a hand-typed take.json/receipt.
    `timing=True` embeds a matching, hash-frozen `timing.json` in the bundle."""
    src = tmp_path / "mix-src"
    src.mkdir()
    wav_path = src / "voice.wav"
    make_tone_wav(wav_path, seconds=duration, silent=silent)
    spec = {
        "version": 1, "what_for": "automated test bed", "direction": "steady tone",
        "duration_seconds": duration, "channels": 1, "target_lufs": None,
        "true_peak_dbtp": -1.0,
        "sources": [{"id": "voice", "path": str(wav_path), "role": "speech"}],
        "cues": [{"id": "voice", "source": "voice", "start": 0, "source_start": 0,
                  "duration": duration, "gain_db": 0, "fade_in": 0, "fade_out": 0,
                  "envelope": []}],
    }
    if timing:
        timing_path = src / "timing.json"
        timing_path.write_text(json.dumps({
            "version": 1, "duration_seconds": duration,
            "cues": [{"id": "voice", "source": "voice", "start": 0, "source_start": 0,
                      "duration": duration}],
        }), encoding="utf-8")
        spec["timing"] = str(timing_path)
    spec_path = src / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    desc_path = src / "description.md"
    desc_path.write_text("Automated test fixture: a single steady tone, never a real approved mix.",
                          encoding="utf-8")
    proposed = mix_media.propose(str(spec_path), str(desc_path), str(tmp_path / "proposal-v1"))
    rendered = mix_media.render(proposed["approved_plan"], proposed["approval_sha256"], "create",
                                 str(tmp_path / "take-01"), slug=slug)
    return Path(rendered["out"])


def stage_mix(bundle_dir, dest_assets_dir):
    """Copy the STAGED SUBSET (master + receipt, plus timing.json if the
    bundle has one) into `dest_assets_dir` - exactly what create-ad/
    create-tour do after `mix-media.py verify --bundle`. Returns the `mix`
    asset-path object and the loaded receipt."""
    dest_assets_dir.mkdir(parents=True, exist_ok=True)
    take = json.loads((bundle_dir / "mix.take.json").read_text(encoding="utf-8"))
    master_name = take["master"]["file"]
    shutil.copyfile(bundle_dir / master_name, dest_assets_dir / master_name)
    shutil.copyfile(bundle_dir / "mix.take.json", dest_assets_dir / "mix.take.json")
    mix = {"master": f"assets/{master_name}", "receipt": "assets/mix.take.json"}
    if "timing.json" in take.get("files", {}):
        shutil.copyfile(bundle_dir / "timing.json", dest_assets_dir / "timing.json")
        mix["timing"] = "assets/timing.json"
    return mix, take


def test_validate_staged_delivery_accepts_a_real_bundles_subset(tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=3.0)
    take = mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json",
                                               duration_seconds=None)
    assert take["status"] in ("PASS", "WARN")


def test_validate_staged_delivery_rejects_a_tampered_master(tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=3.0)
    master = bundle / "mix_mix.wav"
    data = bytearray(master.read_bytes())
    data[-2] ^= 0xFF
    master.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        mix_audio.validate_staged_delivery(master, bundle / "mix.take.json")


def test_validate_staged_delivery_rejects_a_fail_receipt(tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=3.0, silent=True)
    take = json.loads((bundle / "mix.take.json").read_text(encoding="utf-8"))
    assert take["status"] == "FAIL"
    with pytest.raises(ValueError, match="failed Mix cannot be delivered"):
        mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json")


def test_validate_staged_delivery_matches_timing_duration_to_the_video(tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=6.0, timing=True)
    take = mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json",
                                               timing_path=bundle / "timing.json", duration_seconds=6.0)
    assert take["status"] in ("PASS", "WARN")
    with pytest.raises(ValueError, match="does not match this video's total duration"):
        mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json",
                                            timing_path=bundle / "timing.json", duration_seconds=7.0)


def test_validate_staged_delivery_rejects_a_timing_file_the_receipt_never_recorded(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    bundle_without_timing = build_mix_bundle(tmp_path / "a", duration=3.0)
    bundle_with_timing = build_mix_bundle(tmp_path / "b", duration=3.0, timing=True)
    with pytest.raises(ValueError, match="records no timing.json"):
        mix_audio.validate_staged_delivery(bundle_without_timing / "mix_mix.wav",
                                            bundle_without_timing / "mix.take.json",
                                            timing_path=bundle_with_timing / "timing.json")


def test_verify_full_bundle_delegates_to_audio_mixs_own_verifier(tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=3.0)
    result = mix_audio.verify_full_bundle(bundle)
    assert result["take"]["status"] in ("PASS", "WARN")
    assert result["spec"]["duration_seconds"] == 3.0


# ── create-ad: opt-in audio_workflow: mix integration ───────────────────────

@pytest.fixture(autouse=True)
def _mock_ad_runtime_identity(monkeypatch):
    monkeypatch.setattr(ad, "runtime_identity",
                         lambda: {"executable": "/test/hyperframes", "version": "0.test"})


@pytest.fixture
def ad_job(tmp_path):
    root = tmp_path.resolve() / "ad-job"
    ad_example.fixture(root)
    return root


def freeze_ad(root, name="project"):
    plan_path = root / "plan.json"
    return ad.freeze(SimpleNamespace(source=str(root / "source"), plan=str(plan_path),
                                      approval_sha256=ad.digest(plan_path), project=str(root / name)))


def add_ad_asset(root, filename, content):
    path = root / "source/assets" / filename
    path.write_bytes(content)
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    plan["assets"][f"assets/{filename}"] = ad.digest(path)
    (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return plan


def splice_ad_root(root, snippet):
    html = (root / "source/index.html").read_text(encoding="utf-8")
    marker = "</div>\n<script>"
    assert html.count(marker) == 1
    (root / "source/index.html").write_text(html.replace(marker, f"{snippet}{marker}", 1), encoding="utf-8")


def wire_ad_mix(root, bundle_dir):
    mix, take = stage_mix(bundle_dir, root / "source/assets")
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    for relpath in mix.values():
        plan["assets"][relpath] = ad.digest(root / "source" / relpath)
    plan["mix"] = mix
    (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    splice_ad_root(root, f'<audio id="mix-master" data-start="0" data-duration="{plan["duration"]}" '
                         f'data-track-index="1" src="{mix["master"]}"></audio>')
    return plan, take


def test_ad_mix_freeze_accepts_a_valid_staged_master(ad_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION)
    wire_ad_mix(ad_job, bundle)
    result = freeze_ad(ad_job)
    assert result["duration"] == ad_example.DURATION


def test_ad_mix_accepts_staged_timing_matching_the_ad_duration(ad_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION, timing=True)
    wire_ad_mix(ad_job, bundle)
    result = freeze_ad(ad_job)
    assert result["duration"] == ad_example.DURATION


def test_ad_mix_forbids_a_second_wav_alongside_the_master(ad_job, tmp_path):
    """"source+mix double playback" must never both play: mix mode plays
    only the approved master, never a stem beside it."""
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION)
    wire_ad_mix(ad_job, bundle)
    extra = ad_job / "source/assets/extra.wav"
    make_tone_wav(extra, seconds=3)
    add_ad_asset(ad_job, "extra.wav", extra.read_bytes())
    splice_ad_root(ad_job, '<audio id="extra" data-start="0" data-duration="3" '
                           'data-track-index="2" src="assets/extra.wav"></audio>')
    with pytest.raises(ValueError, match="only declared WAV asset|placed exactly once"):
        freeze_ad(ad_job)


def test_ad_mix_rejects_a_tampered_master(ad_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION)
    plan, take = wire_ad_mix(ad_job, bundle)
    master_path = ad_job / "source" / plan["mix"]["master"]
    data = bytearray(master_path.read_bytes())
    data[-2] ^= 0xFF
    master_path.write_bytes(bytes(data))
    plan2 = json.loads((ad_job / "plan.json").read_text(encoding="utf-8"))
    plan2["assets"][plan["mix"]["master"]] = ad.digest(master_path)
    (ad_job / "plan.json").write_text(json.dumps(plan2), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        freeze_ad(ad_job)


def test_ad_mix_rejects_a_fail_status_receipt(ad_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION, silent=True)
    take = json.loads((bundle / "mix.take.json").read_text(encoding="utf-8"))
    assert take["status"] == "FAIL"
    wire_ad_mix(ad_job, bundle)
    with pytest.raises(ValueError, match="failed Mix cannot be delivered"):
        freeze_ad(ad_job)


def test_ad_mix_requires_full_duration_placement(ad_job, tmp_path):
    """Gain/time changes on the placement (here: a shortened placement) are
    a rejected defect, never silently accepted."""
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION)
    mix, take = stage_mix(bundle, ad_job / "source/assets")
    plan = json.loads((ad_job / "plan.json").read_text(encoding="utf-8"))
    for relpath in mix.values():
        plan["assets"][relpath] = ad.digest(ad_job / "source" / relpath)
    plan["mix"] = mix
    (ad_job / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    splice_ad_root(ad_job, f'<audio id="mix-master" data-start="0" data-duration="3" '
                           f'data-track-index="1" src="{mix["master"]}"></audio>')
    with pytest.raises(ValueError, match="full duration"):
        freeze_ad(ad_job)


def test_ad_mix_rejects_nonzero_start(ad_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=ad_example.DURATION)
    mix, take = stage_mix(bundle, ad_job / "source/assets")
    plan = json.loads((ad_job / "plan.json").read_text(encoding="utf-8"))
    for relpath in mix.values():
        plan["assets"][relpath] = ad.digest(ad_job / "source" / relpath)
    plan["mix"] = mix
    (ad_job / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    splice_ad_root(ad_job, f'<audio id="mix-master" data-start="1" '
                           f'data-duration="{plan["duration"] - 1}" '
                           f'data-track-index="1" src="{mix["master"]}"></audio>')
    with pytest.raises(ValueError, match="start at 0"):
        freeze_ad(ad_job)


def test_ad_legacy_plan_unaffected_by_mix_field_absence(ad_job):
    plan_before = json.loads((ad_job / "plan.json").read_text(encoding="utf-8"))
    assert "mix" not in plan_before
    result = freeze_ad(ad_job)
    assert result["duration"] == ad_example.DURATION


# ── create-tour: opt-in audio_workflow: mix integration ─────────────────────

tour_example = _load("authored_tour_example",
                      Path(__file__).resolve().parent / "fixtures/authored-tour/example.py")


@pytest.fixture
def tour_job(tmp_path):
    root = tmp_path.resolve() / "tour-job"
    tour_example.fixture(root, "none")
    return root


def freeze_tour(root, name="project"):
    return authored.freeze(SimpleNamespace(form=str(root / "form.json"), contract=str(root / "contract.json"),
                                            source=str(root / "source"), project=str(root / name)))


def splice_tour_root(root, snippet):
    html = (root / "source/index.html").read_text(encoding="utf-8")
    marker = "</div>\n<script>"
    assert html.count(marker) == 1
    (root / "source/index.html").write_text(html.replace(marker, f"{snippet}{marker}", 1), encoding="utf-8")


def wire_tour_mix(root, bundle_dir, duration, extra_attrs=""):
    mix, take = stage_mix(bundle_dir, root / "source/assets")
    form = json.loads((root / "form.json").read_text(encoding="utf-8"))
    form["audio_workflow"] = "mix"
    form["mix"] = mix
    (root / "form.json").write_text(json.dumps(form), encoding="utf-8")
    splice_tour_root(root, f'<audio id="mix-master" data-start="0" data-duration="{duration}" '
                          f'data-track-index="1" {extra_attrs} src="{mix["master"]}"></audio>')
    return form, take


def test_tour_mix_freeze_accepts_a_valid_staged_master(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0)
    wire_tour_mix(tour_job, bundle, duration=8)
    result = freeze_tour(tour_job)
    assert result["duration"] == 8


def test_tour_mix_requires_explicit_positive_track_index(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0)
    mix, take = stage_mix(bundle, tour_job / "source/assets")
    form = json.loads((tour_job / "form.json").read_text(encoding="utf-8"))
    form["audio_workflow"] = "mix"
    form["mix"] = mix
    (tour_job / "form.json").write_text(json.dumps(form), encoding="utf-8")
    splice_tour_root(tour_job, f'<audio id="mix-master" data-start="0" data-duration="8" '
                              f'src="{mix["master"]}"></audio>')
    with pytest.raises(ValueError, match="data-track-index"):
        freeze_tour(tour_job)


@pytest.mark.parametrize("offset", ["0", "0.1"])
def test_tour_mix_media_start_is_explicitly_zero_only(tour_job, tmp_path, offset):
    bundle = build_mix_bundle(tmp_path, duration=8.0)
    wire_tour_mix(tour_job, bundle, duration=8, extra_attrs=f'data-media-start="{offset}"')
    if offset == "0":
        assert freeze_tour(tour_job)["duration"] == 8
    else:
        with pytest.raises(ValueError, match="offset/retimed"):
            freeze_tour(tour_job)


def test_tour_mix_forbids_a_second_audio_element(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0)
    form, take = wire_tour_mix(tour_job, bundle, duration=8)
    splice_tour_root(tour_job, f'<audio id="extra" data-start="0" data-duration="1" '
                              f'data-track-index="2" src="{form["mix"]["master"]}"></audio>')
    with pytest.raises(ValueError, match="exactly one"):
        freeze_tour(tour_job)


def test_tour_mix_rejects_nonunity_volume(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0)
    wire_tour_mix(tour_job, bundle, duration=8, extra_attrs='data-volume="0.5"')
    with pytest.raises(ValueError, match="unity volume"):
        freeze_tour(tour_job)


def test_tour_mix_rejects_a_fail_status_receipt(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0, silent=True)
    wire_tour_mix(tour_job, bundle, duration=8)
    with pytest.raises(ValueError, match="failed Mix cannot be delivered"):
        freeze_tour(tour_job)


def test_tour_mix_accepts_staged_timing_matching_the_tour_duration(tour_job, tmp_path):
    bundle = build_mix_bundle(tmp_path, duration=8.0, timing=True)
    wire_tour_mix(tour_job, bundle, duration=8)
    result = freeze_tour(tour_job)
    assert result["duration"] == 8


def test_tour_legacy_form_unaffected_by_audio_workflow_default(tour_job):
    form_before = json.loads((tour_job / "form.json").read_text(encoding="utf-8"))
    assert "audio_workflow" not in form_before
    result = freeze_tour(tour_job)
    assert result["duration"] == 8


def test_tour_frozen_form_json_preserves_absence_of_audio_workflow_default(tour_job):
    """form_model must never inject a default 'audio_workflow' key: the FROZEN
    project/form.json (not just the input form.json) must still omit it for an
    old form that never named it."""
    freeze_tour(tour_job)
    frozen = json.loads((tour_job / "project/form.json").read_text(encoding="utf-8"))
    assert "audio_workflow" not in frozen
    assert "mix" not in frozen


# ── validate_timing_spec: additional strict-type/quantization coverage ──────

def test_validate_timing_spec_rejects_boolean_version():
    spec = valid_spec()
    spec["version"] = True
    with pytest.raises(ValueError, match="version must be 1"):
        mix_audio.validate_timing_spec(spec)


def test_validate_timing_spec_rejects_a_sub_sample_cue():
    """A cue duration below one sample (1/48000s) rounds to zero frames and must
    be refused, not silently treated as an empty/no-op cue."""
    spec = valid_spec(duration_seconds=1, cues=[_cue(duration=1e-7)])
    with pytest.raises(ValueError, match="cue does not fit after sample quantization"):
        mix_audio.validate_timing_spec(spec)


# ── check_final_audio: direct unit coverage ──────────────────────────────────

def _audio_stream(duration="8.03"):
    return {"codec_type": "audio", "duration": duration}


def test_check_final_audio_accepts_a_good_measurement():
    measured = {"input_i": -20.0, "input_tp": -1.15, "warnings": []}
    receipt = {"output_policy": {"target_lufs": -18, "true_peak_dbtp": -1.0}}
    result = mix_audio.check_final_audio(measured, receipt, [_audio_stream()], 8.0)
    assert result["approved_true_peak_dbtp"] == -1.0
    assert result["audio_duration_seconds"] == 8.03


@pytest.mark.parametrize("streams", [[], [_audio_stream(), _audio_stream()]])
def test_check_final_audio_requires_exactly_one_audio_stream(streams):
    measured = {"input_i": -20.0, "input_tp": -1.15, "warnings": []}
    receipt = {"output_policy": {"target_lufs": -18, "true_peak_dbtp": -1.0}}
    with pytest.raises(ValueError, match="exactly one audio stream"):
        mix_audio.check_final_audio(measured, receipt, streams, 8.0)


@pytest.mark.parametrize("peak", [0.0, .05, -1.0 + .2 + .01])
def test_check_final_audio_rejects_peak_at_or_over_zero_or_past_ceiling_tolerance(peak):
    measured = {"input_i": -20.0, "input_tp": peak, "warnings": []}
    receipt = {"output_policy": {"target_lufs": -18, "true_peak_dbtp": -1.0}}
    with pytest.raises(ValueError, match="true peak exceeds approved ceiling"):
        mix_audio.check_final_audio(measured, receipt, [_audio_stream()], 8.0)


def test_check_final_audio_accepts_the_exact_ceiling_plus_0_2db_tolerance_boundary():
    measured = {"input_i": -20.0, "input_tp": -1.0 + .2, "warnings": []}
    receipt = {"output_policy": {"target_lufs": -18, "true_peak_dbtp": -1.0}}
    result = mix_audio.check_final_audio(measured, receipt, [_audio_stream()], 8.0)
    assert result["input_tp"] == pytest.approx(-.8)


@pytest.mark.parametrize("duration,ok", [("8.09", True), ("7.91", True), ("8.11", False), ("7.5", False)])
def test_check_final_audio_duration_tolerance_is_plus_minus_0_1(duration, ok):
    measured = {"input_i": -20.0, "input_tp": -1.15, "warnings": []}
    receipt = {"output_policy": {"target_lufs": -18, "true_peak_dbtp": -1.0}}
    if ok:
        result = mix_audio.check_final_audio(measured, receipt, [_audio_stream(duration)], 8.0)
        assert result["audio_duration_seconds"] == float(duration)
    else:
        with pytest.raises(ValueError, match="duration mismatch"):
            mix_audio.check_final_audio(measured, receipt, [_audio_stream(duration)], 8.0)


# ── check_caption_markup: direct unit coverage ───────────────────────────────

def build_mix_bundle_with_captions(tmp_path, duration=4.0, words=(("hello", .5, 1.), ("there", 1.5, 2.))):
    """A real captions-producing Mix bundle: a speech source with a matching,
    hash-bound .words.json sidecar, built through Audio Mix's own propose/render."""
    src = tmp_path / "mix-src"
    src.mkdir()
    wav_path = src / "voice.wav"
    make_tone_wav(wav_path, seconds=duration)
    raw = wav_path.read_bytes()
    _, native = mix_media.media.decode(wav_path, raw)
    pcm_bytes = mix_media.media.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
                                     "-f", native["container"], "-i", str(wav_path), "-map", "0:a:0", "-ar", "48000",
                                     "-ac", "1", "-t", "600.01", "-f", "s16le", "pipe:1"]).stdout
    text = " ".join(w for w, *_ in words)
    doc = {"file": "voice.wav", "duration": native["decoded_duration_seconds"],
           "pcm_sha256": hashlib.sha256(pcm_bytes).hexdigest(),
           "words": [{"start": a, "end": b, "word": w} for w, a, b in words],
           "captions": [{"start": w[1], "end": w[2], "text": w[0]} for w in words],
           "segments": [{"start": words[0][1], "end": words[-1][2], "text": text}]}
    sidecar = src / "voice.words.json"
    sidecar.write_text(json.dumps(doc), encoding="utf-8")
    spec = {"version": 1, "what_for": "caption test bed", "direction": "steady tone",
            "duration_seconds": duration, "channels": 1, "target_lufs": None, "true_peak_dbtp": -1.0,
            "sources": [{"id": "voice", "path": str(wav_path), "role": "speech", "words": str(sidecar)}],
            "cues": [{"id": "voice", "source": "voice", "start": 0, "source_start": 0, "duration": duration,
                      "gain_db": 0, "fade_in": 0, "fade_out": 0, "envelope": []}]}
    spec_path = src / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    desc_path = src / "description.md"
    desc_path.write_text("Automated test fixture: a speech tone with captions.", encoding="utf-8")
    proposed = mix_media.propose(str(spec_path), str(desc_path), str(tmp_path / "proposal-v1"))
    rendered = mix_media.render(proposed["approved_plan"], proposed["approval_sha256"], "create",
                                 str(tmp_path / "take-01"))
    assert "captions.json" in rendered["files"], rendered
    return Path(rendered["out"])


def caption_index(items):
    """items: list of (id_suffix, class_attr, text) already-rendered spans, in order."""
    return "<div>" + "".join(items) + "</div>"


def caption_span(index, cue, klass="clip", text=None):
    return (f'<span id="mix-caption-{index}" class="{klass}" data-start="{cue["start"]}" '
            f'data-duration="{cue["end"] - cue["start"]}">{cue["text"] if text is None else text}</span>')


def test_check_caption_markup_accepts_matching_captions(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    cues = json.loads(captions_path.read_text(encoding="utf-8"))["captions"]
    index = tmp_path / "index.html"
    index.write_text(caption_index([caption_span(i, c) for i, c in enumerate(cues, 1)]), encoding="utf-8")
    mix_audio.check_caption_markup(index, captions_path)


def test_check_caption_markup_accepts_no_captions_and_no_elements(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("<div></div>", encoding="utf-8")
    mix_audio.check_caption_markup(index, None)


def test_check_caption_markup_rejects_a_dropped_caption_element(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    index = tmp_path / "index.html"
    index.write_text("<div></div>", encoding="utf-8")
    with pytest.raises(ValueError, match="must match the sidecar exactly"):
        mix_audio.check_caption_markup(index, captions_path)


def test_check_caption_markup_rejects_changed_text(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    cues = json.loads(captions_path.read_text(encoding="utf-8"))["captions"]
    index = tmp_path / "index.html"
    index.write_text(caption_index([caption_span(i, c, text="goodbye")
                                    for i, c in enumerate(cues, 1)]), encoding="utf-8")
    with pytest.raises(ValueError, match="Mix caption text changed"):
        mix_audio.check_caption_markup(index, captions_path)


def test_check_caption_markup_rejects_changed_timing(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    cues = json.loads(captions_path.read_text(encoding="utf-8"))["captions"]
    tampered = [{**c, "start": c["start"] + .3} for c in cues]
    index = tmp_path / "index.html"
    index.write_text(caption_index([caption_span(i, c) for i, c in enumerate(tampered, 1)]), encoding="utf-8")
    with pytest.raises(ValueError, match="Mix caption placement changed"):
        mix_audio.check_caption_markup(index, captions_path)


def test_check_caption_markup_requires_a_timed_clip_element(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    cues = json.loads(captions_path.read_text(encoding="utf-8"))["captions"]
    index = tmp_path / "index.html"
    index.write_text(caption_index([caption_span(i, c, klass="not-clip")
                                    for i, c in enumerate(cues, 1)]), encoding="utf-8")
    with pytest.raises(ValueError, match="require timed clip elements"):
        mix_audio.check_caption_markup(index, captions_path)


# ── validate_staged_delivery: receipt caption hash / duration / timing edges ─

def test_validate_staged_delivery_rejects_a_tampered_staged_captions_sidecar(tmp_path):
    bundle = build_mix_bundle_with_captions(tmp_path)
    captions_path = bundle / "captions.json"
    data = json.loads(captions_path.read_text(encoding="utf-8"))
    data["captions"][0]["text"] = "tampered"
    captions_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="captions hash mismatch"):
        mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json",
                                           captions_path=captions_path)


def test_validate_staged_delivery_rejects_duration_mismatch_even_without_timing(tmp_path):
    """A staged master whose OWN recorded duration does not match the video's declared
    duration must be rejected purely by the master-frame cross-check, independent of
    whether timing.json was ever supplied."""
    bundle = build_mix_bundle(tmp_path, duration=10.0)
    with pytest.raises(ValueError, match="does not match this video's total duration"):
        mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json",
                                           duration_seconds=8.0)


def test_validate_staged_delivery_rejects_an_omitted_timing_the_receipt_recorded(tmp_path):
    """The inverse of 'invented timing': a receipt that DOES record timing.json must not
    have that timing evidence silently dropped by omitting timing_path."""
    bundle = build_mix_bundle(tmp_path, duration=3.0, timing=True)
    with pytest.raises(ValueError, match="must not be dropped"):
        mix_audio.validate_staged_delivery(bundle / "mix_mix.wav", bundle / "mix.take.json")
