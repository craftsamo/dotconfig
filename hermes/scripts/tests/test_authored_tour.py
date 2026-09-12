"""Authored v2 safety/semantic contracts; no model calls, capture or uploads."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "profiles/video-creator/skills/video-creator-pipeline/create/tour"
sys.path.insert(0, str(LEAF / "scripts"))
import authored

spec = importlib.util.spec_from_file_location("authored_example", Path(__file__).parent / "fixtures/authored-tour/example.py")
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


@pytest.fixture
def job(tmp_path):
    root = tmp_path.resolve() / "job"
    example.fixture(root)
    return root


def freeze(root, name="project"):
    return authored.freeze(SimpleNamespace(form=str(root / "form.json"), contract=str(root / "contract.json"),
                                           source=str(root / "source"), project=str(root / name)))


def save(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_defaults_are_on_and_need_no_screenshots():
    form = authored.form_model({"what_for": "show a setting", "audience": "beginners"})
    assert form["intro"] == "title-reveal" and form["outro"] == "result-hold"
    assert "steps" not in form and "reference" not in form


@pytest.mark.parametrize("key,value", [("intro", ""), ("outro", None), ("intro", False),
    ("duration", True), ("duration", float("nan")), ("duration", 61), ("duration", 0),
    ("fidelity", "invent"), ("preview", False), ("what_for", ""), ("audience", "")])
def test_invalid_form_does_not_default(key, value):
    with pytest.raises(ValueError):
        authored.form_model({"what_for": "task", "audience": "novices", key: value})


def test_legacy_forms_not_reinterpreted():
    with pytest.raises(ValueError, match="v1"):
        authored.form_model({"task": "old", "steps": "steps.json"})


@pytest.mark.parametrize("variant", ["main", "overview", "result", "custom", "none"])
def test_every_choice_and_free_text_freezes_without_dispatch(tmp_path, variant):
    root = tmp_path.resolve() / variant
    form, contract = example.fixture(root, variant)
    freeze(root)
    _, actual, proof = authored.project_model(str(root / "project"))
    assert actual["intro"] == form["intro"] and actual["outro"] == form["outro"]
    assert proof == contract
    assert (root / "source/index.html").read_bytes() == (root / "project/index.html").read_bytes()
    if variant == "custom":
        assert actual["intro"] == example.CUSTOM_INTRO
        assert actual["outro"] == example.CUSTOM_OUTRO
    if variant == "none":
        assert proof["intro"]["end"] == 0 and proof["outro"]["start"] == 8


@pytest.mark.parametrize("replacement", ["title-reveal", "ui-overview", "result-first", "none"])
def test_custom_direction_cannot_silently_fall_back(tmp_path, replacement):
    form, contract = example.fixture(tmp_path.resolve() / "custom", "custom")
    contract["intro"]["direction"] = replacement
    with pytest.raises(ValueError, match="no silent fallback"):
        authored.contract_model(contract, form)


@pytest.mark.parametrize("fault", ["missing-first", "missing-final", "unordered", "no-intro-proof", "overlap", "empty-beat", "duration", "extra-key"])
def test_semantic_proof_contract(job, fault):
    form = authored.form_model(authored.load(job / "form.json"))
    contract = authored.load(job / "contract.json")
    if fault == "missing-first": contract["samples"].pop(0)
    if fault == "missing-final": contract["samples"].pop()
    if fault == "unordered": contract["samples"][1]["at"] = 0
    if fault == "no-intro-proof": contract["samples"] = [s for s in contract["samples"] if s["at"] == 0 or s["at"] > 3]
    if fault == "overlap": contract["intro"]["end"] = 18
    if fault == "empty-beat": contract["intro"]["description"] = ""
    if fault == "duration": contract["duration"] = 21
    if fault == "extra-key": contract["steps"] = []
    with pytest.raises(ValueError): authored.contract_model(contract, form)


def test_none_requires_no_beat(tmp_path):
    form, contract = example.fixture(tmp_path.resolve() / "none", "none")
    contract["intro"]["description"] = "still a title"
    with pytest.raises(ValueError, match="none must be explicit"): authored.contract_model(contract, form)


def test_new_files_mutation_and_existing_outputs_rejected(job):
    freeze(job)
    with pytest.raises(ValueError, match="must not exist"): freeze(job)
    (job / "project/extra.js").write_text("const extra=1;")
    with pytest.raises(ValueError, match="changed since freeze"): authored.project_model(str(job / "project"))


def test_original_source_survives_and_frozen_edits_fail(job):
    original = (job / "source/index.html").read_bytes()
    freeze(job)
    (job / "project/index.html").write_text("changed")
    assert (job / "source/index.html").read_bytes() == original
    with pytest.raises(ValueError, match="changed since freeze"): authored.project_model(str(job / "project"))


def test_backdrop_source_may_disappear_after_freeze(job):
    image = job / "original.png"
    Image.new("RGB", (64, 64), "blue").save(image)
    (job / "source/assets/backdrop.png").write_bytes(image.read_bytes())
    form = authored.load(job / "form.json")
    form["backdrop"] = str(image)
    save(job / "form.json", form)
    freeze(job)
    image.rename(job / "moved-original.png")
    authored.project_model(str(job / "project"))


def test_paths_symlinks_and_traversal(job):
    freeze(job)
    (job / "scratch").mkdir()
    for path in (job / "project/final", job / "scratch/../project/final"):
        with pytest.raises(ValueError): authored.output_dir(str(path), job / "project")
        assert not (job / "project/final").exists()
    (job / "source/assets/link.js").symlink_to(job / "source/assets/gsap.min.js")
    with pytest.raises(ValueError, match="symlink"): freeze(job, "project2")
    assert not (job / "project2").exists()


def test_freeze_traversal_and_nested_source(job):
    (job / "scratch").mkdir()
    for name in ("scratch/../source/project", "source/project"):
        with pytest.raises(ValueError): freeze(job, name)
    assert not (job / "source/project").exists()


def test_symlinked_destination_ancestor_rejected_before_copy(job):
    (job / "alias").symlink_to(job / "source", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"): freeze(job, "alias/project")
    assert not (job / "source/project").exists()


def test_payload_cap_excludes_generated_freeze_records(job):
    count = len(authored.source_files(job / "source"))
    for i in range(200-count):
        (job / "source/assets" / f"note-{i}.txt").write_text("fixture")
    freeze(job)
    authored.project_model(str(job / "project"))
    (job / "source/assets/too-many.txt").write_text("overflow")
    with pytest.raises(ValueError, match="200 files"): freeze(job, "project2")


@pytest.mark.parametrize("clock", ["new Date().toLocaleTimeString()", "Date()", "Date.now()"])
def test_clock_scan_covers_noncanonical_gsap_basename(job, clock):
    (job / "source/assets/vendor").mkdir()
    (job / "source/assets/vendor/gsap.min.js").write_text(clock)
    with pytest.raises(ValueError, match=r"assets/vendor/gsap.min.js: network/clocks"): freeze(job)


def test_visible_date_label_is_not_executable_code(job):
    with (job / "source/index.html").open("a") as f:
        f.write('<div>Start Date (YYYY-MM-DD)</div>')
    freeze(job)


@pytest.mark.parametrize("bad", ['<img src="https://example.com/x.png">', '<img src="assets/../x.png">',
    '<script>fetch("/data")</script>', '<iframe src="assets/frame.html"></iframe>', '<div onclick="play()"></div>'])
def test_active_or_remote_source_rejected_before_output(job, bad):
    with (job / "source/index.html").open("a") as f: f.write(bad)
    with pytest.raises(ValueError): freeze(job)
    assert not (job / "project").exists()


def preview_fixture(job):
    freeze(job)
    preview = job / "preview"
    (preview / "frames").mkdir(parents=True)
    contract = authored.load(job / "contract.json")
    frames = {}
    for i in range(len(contract["samples"])):
        frame = preview / "frames" / f"{i:02}.png"
        Image.new("RGB", (32, 32), (i, 0, 0)).save(frame)
        frames[frame.name] = authored.digest(frame)
    save(preview / "check.json", {"ok": True})
    data = {"project": str(job / "project"), "integrity": authored.digest(job / "project/integrity.json"),
            "times": [s["at"] for s in contract["samples"]], "frames": frames, "check": authored.digest(preview / "check.json")}
    save(preview / "preview.json", data)
    return data, contract


@pytest.mark.parametrize("fault", ["project", "integrity", "times", "frame", "check", "path", "count"])
def test_approval_tampering(job, fault):
    data, contract = preview_fixture(job)
    authored.approved_preview(str(job / "preview"), job / "project", contract)
    if fault in ("project", "integrity"): data[fault] = "different"
    if fault == "times": data["times"] = []
    if fault == "frame": (job / "preview/frames/00.png").write_bytes(b"changed")
    if fault == "check": save(job / "preview/check.json", {"ok": False})
    if fault == "path": data["frames"]["../00.png"] = data["frames"].pop("00.png")
    if fault == "count": data["frames"].pop("00.png")
    save(job / "preview/preview.json", data)
    with pytest.raises(ValueError): authored.approved_preview(str(job / "preview"), job / "project", contract)


def test_render_requires_actual_approval_before_creating_output(job):
    freeze(job)
    with pytest.raises(ValueError, match="requires --approved-preview"):
        authored.render(SimpleNamespace(project=str(job / "project"), out=str(job / "final"), approved_preview=None))
    assert not (job / "final").exists()


def test_reference_fields_are_open_ended():
    data = yaml.safe_load((LEAF / "SKILL.md").read_text().split("---")[1])
    form = data["metadata"]["hermes"]["form"]
    assert "steps" not in form
    for key in ("intro", "outro", "style"):
        assert form[key]["other"] is True
        assert not form[key]["required"]
        folder = "styles" if key == "style" else key
        for option in form[key]["options"]:
            assert (LEAF / "references" / folder / (option + ".md")).is_file()
    config = yaml.safe_load((ROOT / "profiles/video-creator/config.yaml").read_text())
    assert "task-local" in config["agent"]["system_prompt"]
    assert "explicit none" in config["agent"]["system_prompt"]


def test_creator_routes_authored_tours():
    config = yaml.safe_load((ROOT / "profiles/creator/config.yaml").read_text())
    assert "task-local" in config["agent"]["system_prompt"]
    assert "explicit none" in config["agent"]["system_prompt"]
    for path in ("build-creator/references/video-creator/tour.md",
                 "plan-creator/references/video-creator/tour.md",
                 "references/capabilities.md"):
        contents = (ROOT / "profiles/creator/skills/creator-pipeline" / path).read_text()
        assert "create-tour" in contents
        assert 'kind="work"' in contents


def test_reference_validator_catches_deleted_whole_reference_directory(tmp_path):
    spec = importlib.util.spec_from_file_location("profile_validator", ROOT / "scripts/validate-profile-skills.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    errors = []
    validator.validate_hands_form({"note": {"required": False}, "intro": {"required": False,
        "options": ["title-reveal"], "references": "references/intro/*.md", "other": True}}, tmp_path, tmp_path / "SKILL.md", errors)
    assert any("intro option title-reveal" in e for e in errors)
