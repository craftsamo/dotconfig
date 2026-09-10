"""Explainer integrity/gating tests. Only fake HF renders run automatically.

Real PNG/WAV/MP4 inputs are synthetic. Tone/cues prove timing plumbing, never
speech, viseme correctness, character fidelity or semantic learning outcomes.
"""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

FIXTURE = Path(__file__).parent / "fixtures/explainer-video/example.py"
SPEC = importlib.util.spec_from_file_location("explainer_test_example", FIXTURE)
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)
ex = example.explainer
LEAF = example.LEAF


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def propose(job, spec=None, name="proposal-v1"):
    if spec is not None:
        save(job / "spec.json", spec)
    return ex.propose(SimpleNamespace(spec=str(job / "spec.json"), out=str(job / name)))


def freeze(job, proposal=None, target=None):
    proposal = proposal or propose(job)
    if not (job / "source").exists():
        example.author_source(job, proposal)
    return ex.freeze(SimpleNamespace(approved_plan=proposal["proposal"], approval_sha256=proposal["approval_sha256"],
                     source=str(job / "source"), project=str(target or job / "project")))


def hashed(spec):
    plan = copy.deepcopy(spec)
    plan["assets"] = {name: ex.digest(Path(path)) for name, path in spec["assets"].items()}
    return plan


@pytest.fixture(autouse=True)
def no_native_hyperframes(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Ordinary tests must not invoke native HyperFrames")
    monkeypatch.setattr(ex, "hf", forbidden)


@pytest.fixture
def job(tmp_path):
    root = tmp_path.resolve() / "job"
    example.fixture(root, audio=False)
    return root


@pytest.fixture
def cue_job(tmp_path):
    root = tmp_path.resolve() / "cue-job"
    example.fixture(root, framing="bust", performance="puppet")
    return root


@pytest.mark.parametrize("missing", ["master", "script", "body", "cues", "mouths", "runtime", "dependency"])
def test_missing_required_inputs_remain_pending_without_render(cue_job, missing):
    spec = ex.load(cue_job / "spec.json")
    if missing in ("master", "script"):
        spec["audio"][missing] = None
    elif missing == "runtime":
        spec["renderer"] = "motion-canvas"
    elif missing == "dependency":
        spec["pending"] = ["AudioCreator: supplied technical timing input pending"]
    else:
        spec["character"][missing] = {} if missing == "mouths" else None
    result = propose(cue_job, spec)
    assert result["status"] == "pending-inputs"
    assert result["can_render"] is False and result["media_generation"] == 0 and result["missing"]
    assert not list(cue_job.glob("**/*.mp4"))
    with pytest.raises(ValueError, match="pending-inputs"):
        ex.approved_proposal(result["proposal"], result["approval_sha256"])


@pytest.mark.parametrize("missing", ["video", "sync"])
def test_missing_animated_inputs_remain_pending_without_downgrade(tmp_path, missing):
    job = tmp_path.resolve() / "animated-pending"
    spec = example.fixture(job, framing="full", performance="animated")
    spec["character"][missing] = None
    result = propose(job, spec)
    plan = ex.load(Path(result["proposal"]).parent / "plan.json")
    assert result["status"] == "pending-inputs" and not result["can_render"]
    assert plan["character"]["performance"] == "animated" and plan["character"]["lip_sync"] == "baked"
    with pytest.raises(ValueError, match="pending-inputs"):
        ex.approved_proposal(result["proposal"], result["approval_sha256"])


def test_listed_missing_file_hard_fails_not_pending(job):
    spec = ex.load(job / "spec.json")
    spec["assets"]["assets/missing.png"] = str(job / "not-there.png")
    spec["pending"] = ["ImageCreator: missing image"]
    with pytest.raises(ValueError, match="missing local file"):
        propose(job, spec)
    assert not (job / "proposal-v1").exists()


def test_proposal_freezes_original_assets_and_vendored_gsap(cue_job):
    inputs = ex.load(cue_job / "spec.json")["assets"]
    result = propose(cue_job)
    root = Path(result["proposal"]).parent
    plan = ex.load(root / "plan.json")
    assert result["status"] == "awaiting-approval" and result["can_render"]
    for name, original in inputs.items():
        assert (root / name).read_bytes() == Path(original).read_bytes()
        assert plan["assets"][name] == ex.digest(Path(original))
    for name in ex.VENDOR_FILES:
        assert (root / "assets" / name).read_bytes() == (ex.VENDOR / name).read_bytes()
    assert plan["assets"][ex.MOUTH_TRACK] == ex.digest(root / ex.MOUTH_TRACK)
    assert (root / ex.MOUTH_TRACK).read_text() == ex.mouth_track(root, plan)
    assert result["approval_sha256"] == ex.digest(root / "proposal.md")
    assert plan["units"][0]["narration"] == "Check the cache."
    assert plan["copy"][1]["text"] == example.NOTICE


@pytest.mark.parametrize("mutation", ["document", "payload", "asset", "old-hash"])
def test_proposal_mutations_and_stale_approval_rejected(cue_job, mutation):
    result = propose(cue_job)
    root = Path(result["proposal"]).parent
    sha = result["approval_sha256"]
    if mutation == "document":
        with (root / "proposal.md").open("a") as out:
            out.write("Changed direction\n")
    elif mutation == "payload":
        plan = ex.load(root / "plan.json")
        plan["topic"] = "Different topic"
        save(root / "plan.json", plan)
    elif mutation == "asset":
        (root / "assets/script.txt").write_text("Different words")
    else:
        sha = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch|asset changed"):
        ex.approved_proposal(result["proposal"], sha)


def test_ready_approval_cannot_release_pending_revision(cue_job):
    ready = propose(cue_job)
    spec = ex.load(cue_job / "spec.json")
    spec["audio"]["master"] = None
    pending = propose(cue_job, spec, "proposal-v2")
    with pytest.raises(ValueError, match="hash mismatch"):
        ex.approved_proposal(pending["proposal"], ready["approval_sha256"])
    with pytest.raises(ValueError, match="pending-inputs"):
        freeze(cue_job, pending)
    assert not (cue_job / "project").exists()


@pytest.mark.parametrize("path,value", [
    (("version",), True), (("version",), 0), (("duration",), 0), (("duration",), 181),
    (("duration",), True), (("duration",), float("nan")), (("aspect",), "1:1"),
    (("width",), 1920), (("fps",), 60), (("units",), []), (("copy",), []),
    (("units", 0, "start"), .1), (("units", 1, "start"), 1), (("units", 1, "start"), 3),
    (("units", 2, "end"), 5), (("units", 1, "id"), "lookup"),
    (("units", 0, "narration"), "Silent mode must not drop this"),
    (("copy", 0, "end"), 0), (("copy", 0, "start"), -1), (("copy", 0, "end"), 7),
    (("copy", 1, "id"), "title"), (("copy", 0, "text"), "x" * 2001),
    (("samples",), []), (("samples", 0, "at"), .1), (("samples", 4, "at"), 6),
    (("samples", 2, "at"), 1), (("samples", 2, "at"), 4),
])
def test_model_rejects_bounds_gaps_duplicates_and_unreviewed_holds(job, path, value):
    plan = hashed(ex.load(job / "spec.json"))
    target = plan
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ex.model(plan)


@pytest.mark.parametrize("framing,performance,lip_sync,audio,aspect", [
    ("none", "still", "off", False, "16:9"), ("none", "still", "off", True, "9:16"),
    ("bust", "still", "off", False, "9:16"), ("bust", "still", "cues", True, "16:9"),
    ("bust", "puppet", "cues", True, "9:16"), ("full", "still", "off", False, "16:9"),
    ("full", "puppet", "cues", True, "16:9"), ("full", "animated", "baked", True, "9:16"),
])
def test_supported_variants_freeze_unchanged(tmp_path, framing, performance, lip_sync, audio, aspect):
    root = tmp_path.resolve() / "variant"
    example.fixture(root, framing, performance, lip_sync, audio, aspect)
    result = freeze(root)
    project, plan = ex.project_model(result["project"])
    assert plan["character"]["framing"] == framing
    assert plan["character"]["performance"] == performance
    assert plan["character"]["lip_sync"] == lip_sync
    assert plan["aspect"] == aspect and not result["rendered_mp4"]
    assert (project / "index.html").read_bytes() == (root / "source/index.html").read_bytes()


@pytest.mark.parametrize("old,new", [
    ('data-width="1280"', 'data-width="720"'), ('data-fps="30"', 'data-fps="24"'),
    ('data-duration="6"', 'data-duration="7"'), ('data-composition-id="explainer"', 'data-composition-id="tour"'),
    ('Cache flow</h1>', 'Changed words</h1>'), ('</h1>', '</h1><p>Undeclared copy</p>'),
    ('id="title"', 'id="other"'), ('window.__timelines["explainer"] = tl;', 'fetch("https://invalid.example");'),
])
def test_authored_dimensions_copy_and_network_contract(job, old, new):
    proposal = propose(job)
    source = example.author_source(job, proposal)
    path = source / "index.html"
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ValueError):
        freeze(job, proposal)
    assert not (job / "project").exists()


@pytest.mark.parametrize("script", ["Check the cache. Store the answer. Reuse the result.",
                                    "Check the cache. Store the result. Reuse the result!",
                                    "Checkthe cache. Store the result. Reuse the result."])
def test_script_words_and_punctuation_must_match_exactly(cue_job, script):
    (cue_job / "inputs/script.txt").write_text(script)
    with pytest.raises(ValueError, match="script exactly"):
        propose(cue_job)


@pytest.mark.parametrize("name", ["../escape.png", "assets/../escape.png", "/assets/image.png",
                                 "assets//image.png", "assets/./image.png", "https://invalid.example/image.png"])
def test_asset_destination_traversal_rejected(job, name):
    spec = ex.load(job / "spec.json")
    sentinel = job / "untouched.png"
    Image.new("RGB", (32, 32)).save(sentinel)
    before = sentinel.read_bytes()
    spec["assets"][name] = str(sentinel)
    with pytest.raises(ValueError):
        propose(job, spec)
    assert sentinel.read_bytes() == before
    assert not (job / "proposal-v1").exists()


@pytest.mark.parametrize("kind", ["input", "source", "output"])
def test_symlink_paths_rejected_without_touching_target(job, kind):
    target = job / "target"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("untouched")
    link = job / "link"
    link.symlink_to(target, target_is_directory=True)
    proposal = None
    if kind == "input":
        spec = ex.load(job / "spec.json")
        spec["assets"]["assets/input.txt"] = str(link / "keep.txt")
        with pytest.raises(ValueError, match="symlink"):
            propose(job, spec)
    else:
        proposal = propose(job)
        example.author_source(job, proposal)
        if kind == "source":
            (job / "source/linked.txt").symlink_to(sentinel)
        with pytest.raises(ValueError, match="symlink"):
            freeze(job, proposal, link / "project" if kind == "output" else None)
    assert sentinel.read_text() == "untouched"
    assert list(target.iterdir()) == [sentinel]


def test_source_input_parent_traversal_is_rejected(cue_job):
    spec = ex.load(cue_job / "spec.json")
    spec["assets"]["assets/script.txt"] = str(cue_job / "inputs/../inputs/script.txt")
    with pytest.raises(ValueError, match="traversal|canonical"):
        propose(cue_job, spec)


def test_output_parent_traversal_is_rejected(job):
    (job / "child").mkdir()
    with pytest.raises(ValueError, match="traversal|canonical"):
        propose(job, name="child/../proposal-v1")
    assert not (job / "proposal-v1").exists()


def test_existing_proposal_and_project_never_overwritten(job):
    proposal = propose(job)
    before = ex.source_files(job / "proposal-v1", version=3)
    with pytest.raises(ValueError, match="must not exist"):
        propose(job)
    freeze(job, proposal)
    frozen = ex.source_files(job / "project", version=3)
    with pytest.raises(ValueError, match="must not exist"):
        freeze(job, proposal)
    assert before == ex.source_files(job / "proposal-v1", version=3)
    assert frozen == ex.source_files(job / "project", version=3)


def test_public_proposal_does_not_embed_source_root_or_source_basename(cue_job):
    spec = ex.load(cue_job / "spec.json")
    original = cue_job / "inputs/body.png"
    # Synthetic sentinel only: never inspect an actual private directory.
    hidden = cue_job / "synthetic-private-root"
    hidden.mkdir()
    named = hidden / "synthetic-private-identity.png"
    shutil.copyfile(original, named)
    spec["assets"]["assets/body.png"] = str(named)
    proposal = propose(cue_job, spec)
    for path in (Path(proposal["proposal"]), Path(proposal["proposal"]).parent / "plan.json"):
        content = path.read_text()
        assert str(cue_job) not in content
        assert hidden.name not in content and named.name not in content


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra", "generated-track"])
def test_source_assets_must_match_approved_manifest(cue_job, mutation):
    proposal = propose(cue_job)
    source = example.author_source(cue_job, proposal)
    if mutation == "changed":
        (source / "assets/script.txt").write_text("Changed")
    elif mutation == "missing":
        (source / "assets/body.png").unlink()
    elif mutation == "extra":
        (source / "assets/extra.txt").write_text("Unapproved")
    else:
        with (source / ex.MOUTH_TRACK).open("a") as out:
            out.write("// altered\n")
    with pytest.raises(ValueError, match="source assets differ"):
        freeze(cue_job, proposal)
    assert not (cue_job / "project").exists()


def test_generated_mouth_track_must_equal_compiled_cues_even_with_rehashed_plan(cue_job):
    proposal = propose(cue_job)
    root = Path(proposal["proposal"]).parent
    plan = ex.load(root / "plan.json")
    original_plan_hash = ex.digest(root / "plan.json")
    track = root / ex.MOUTH_TRACK
    track.write_text(track.read_text() + '\ntl.set("#character-mouth-open", {opacity: 1}, 0);\n')
    plan["assets"][ex.MOUTH_TRACK] = ex.digest(track)
    save(root / "plan.json", plan)
    document = root / "proposal.md"
    document.write_text(document.read_text().replace(original_plan_hash, ex.digest(root / "plan.json")))
    with pytest.raises(ValueError, match="mouth track changed"):
        ex.approved_proposal(str(document), ex.digest(document))


def test_original_inputs_are_not_reread_after_proposal(cue_job):
    proposal = propose(cue_job)
    shutil.rmtree(cue_job / "inputs")
    result = freeze(cue_job, proposal)
    _, plan = ex.project_model(result["project"])
    assert plan["character"]["lip_sync"] == "cues"


@pytest.mark.parametrize("name", [ex.MOUTH_TRACK, "assets/gsap.min.js", "assets/GSAP-LICENSE.txt", "assets/gsap-provenance.json"])
def test_callers_cannot_supply_reserved_generated_assets(job, name):
    source = job / Path(name).name
    source.write_text("Untrusted replacement")
    spec = ex.load(job / "spec.json")
    spec["assets"][name] = str(source)
    with pytest.raises(ValueError, match="generated only|GSAP is supplied"):
        propose(job, spec)


@pytest.mark.parametrize("mutation", ["master", "voice-hash", "unknown-voice", "offset", "negative", "past-end",
                                      "overlap", "zero-hold", "unknown-shape", "empty", "oversize"])
def test_mouth_cues_fail_closed(cue_job, mutation):
    path = cue_job / "inputs/cues.json"
    cues = ex.load(path)
    if mutation == "master":
        cues["master_sha256"] = "0" * 64
    elif mutation == "voice-hash":
        cues["voice_sha256"] = "0" * 64
    elif mutation == "unknown-voice":
        cues["voice"] = "assets/unknown.wav"
    elif mutation == "offset":
        cues["offset"] = 1
    elif mutation == "negative":
        cues["events"][0]["start"] = -.1
    elif mutation == "past-end":
        cues["events"][-1]["end"] = 7
    elif mutation == "overlap":
        cues["events"][1]["start"] = .5
    elif mutation == "zero-hold":
        cues["events"][0]["end"] = .4
    elif mutation == "unknown-shape":
        cues["events"][0]["mouth"] = "unknown"
    elif mutation == "empty":
        cues["events"] = []
    else:
        cues["events"] *= 1400
    save(path, cues)
    with pytest.raises(ValueError):
        propose(cue_job)


def test_mouth_canvas_alignment_and_master_duration(cue_job):
    Image.new("RGBA", (80, 120)).save(cue_job / "inputs/open.png")
    with pytest.raises(ValueError, match="aligned canvas"):
        propose(cue_job)
    Image.new("RGBA", (160, 240)).save(cue_job / "inputs/open.png")
    example.tone(cue_job / "inputs/tone.wav", seconds=5)
    with pytest.raises(ValueError, match="master duration"):
        propose(cue_job, name="proposal-v2")


@pytest.mark.parametrize("rate", [8000, 44100])
def test_audio_requires_finished_48khz_pcm(cue_job, rate):
    example.tone(cue_job / "inputs/tone.wav", rate=rate)
    with pytest.raises(ValueError, match="48 kHz"):
        propose(cue_job)


def test_cues_bind_separate_supplied_voice_not_only_master(cue_job):
    spec = ex.load(cue_job / "spec.json")
    voice = cue_job / "inputs/voice.wav"
    example.tone(voice, seconds=2)
    spec["assets"]["assets/voice.wav"] = str(voice)
    cues = ex.load(cue_job / "inputs/cues.json")
    cues.update(voice="assets/voice.wav", voice_sha256=ex.digest(voice), offset=2,
                events=[{"start": .2, "end": .6, "mouth": "open"}])
    save(cue_job / "inputs/cues.json", cues)
    proposal = propose(cue_job, spec)
    root = Path(proposal["proposal"]).parent
    track = (root / ex.MOUTH_TRACK).read_text()
    assert 'opacity: 1}, 2.2)' in track
    example.tone(voice, seconds=1)
    with pytest.raises(ValueError, match="voice hash mismatch"):
        propose(cue_job, name="proposal-v2")


def test_mouth_asset_loads_before_scene_without_registry_access(cue_job):
    proposal = propose(cue_job)
    track = (Path(proposal["proposal"]).parent / ex.MOUTH_TRACK).read_text()
    script = """
const vm = require('node:vm');
const context = {};
vm.runInNewContext(JSON.parse(require('node:fs').readFileSync(0, 'utf8')), context);
if (typeof context.addExplainerMouthTrack !== 'function') throw Error('missing declaration');
const events = [];
context.addExplainerMouthTrack({set: (...args) => events.push(args)});
if (events.length !== 12) throw Error('track not built');
if (events[0][2] !== 0.4 || events.at(-1)[2] !== 4.8) throw Error('wrong timing');
"""
    result = subprocess.run(["node", "-e", script], input=json.dumps(track), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_frame_zero_cue_is_the_authored_initial_mouth(tmp_path):
    job = tmp_path.resolve() / "first-frame-cue"
    example.fixture(job, framing="bust", performance="puppet", cue_at_zero=True)
    proposal = propose(job)
    source = example.author_source(job, proposal)
    html = (source / "index.html").read_text()
    assert 'id="character-mouth-rest" src="assets/rest.png" style="opacity: 0"' in html
    assert 'id="character-mouth-open" src="assets/open.png" style="opacity: 1"' in html
    track = (source / ex.MOUTH_TRACK).read_text()
    assert 'tl.set("#character-mouth-open", {opacity: 1}, 0)' in track
    assert 'gsap.set' not in track
    freeze(job, proposal)
    path = source / "index.html"
    path.write_text(html.replace('id="character-mouth-open" src="assets/open.png" style="opacity: 1"',
                                 'id="character-mouth-open" src="assets/open.png" style="opacity: 0"'))
    with pytest.raises(ValueError, match="initial opacity"):
        ex.markup_check(source, ex.load(job / "project/plan.json"))


@pytest.mark.parametrize("at_zero", [False, True])
def test_mouth_tracks_are_seek_order_independent(cue_job, at_zero):
    spec = ex.load(cue_job / "spec.json")
    wide = cue_job / "inputs/wide.png"
    shutil.copyfile(cue_job / "inputs/open.png", wide)
    spec["assets"]["assets/wide.png"] = str(wide)
    spec["character"]["mouths"]["wide"] = "assets/wide.png"
    cues = ex.load(cue_job / "inputs/cues.json")
    cues["events"] = [
        {"start": 0 if at_zero else .4, "end": .8, "mouth": "open"},
        {"start": .8, "end": 1.2, "mouth": "wide"},
        {"start": 1.2, "end": 1.6, "mouth": "wide"},
        {"start": 2.4, "end": 2.8, "mouth": "open"},
    ]
    save(cue_job / "inputs/cues.json", cues)
    proposal = propose(cue_job, spec)
    track = (Path(proposal["proposal"]).parent / ex.MOUTH_TRACK).read_text()
    script = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const data = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const {gsap} = require(data.vendor);
const expected = t => data.events.find(e => e.start <= t && t < e.end)?.mouth ?? 'rest';
const times = [...new Set([0, 5.967, ...data.events.flatMap(e =>
  [e.start, e.start + .001, (e.start + e.end) / 2, e.end - .001, e.end, e.end + .001])])].sort((a,b) => a-b);
const context = {};
vm.runInNewContext(data.track, context);
for (const sequence of [times, [...times].reverse(), times.flatMap(t => [5.967, t, t + .001])]) {
  const states = Object.fromEntries(['rest', 'open', 'wide'].map(m => [m, {opacity: +(m === expected(0))}]));
  const tl = gsap.timeline({paused: true}).to({clock: 0}, {clock: 1, duration: 6}, 0);
  context.addExplainerMouthTrack({set: (selector, props, at) => {
    tl.set(selector.split(',').map(s => states[s.replace('#character-mouth-', '')]), props, at);
  }});
  for (const t of sequence) {
    tl.seek(t, false);
    for (const [mouth, state] of Object.entries(states))
      assert.equal(state.opacity, +(mouth === expected(t)), `${t}: ${mouth}`);
  }
  tl.kill();
}
gsap.ticker.sleep();
"""
    result = subprocess.run(["node", "-e", script], input=json.dumps({"track": track,
        "events": cues["events"], "vendor": str(ex.VENDOR / "gsap.min.js")}), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "late"])
def test_mouth_track_requires_scene_call_after_declaration(cue_job, mutation):
    proposal = propose(cue_job)
    source = example.author_source(cue_job, proposal)
    path = source / "index.html"
    code = path.read_text()
    if mutation == "missing":
        code = code.replace("addExplainerMouthTrack(tl);", "")
    elif mutation == "duplicate":
        code = code.replace("addExplainerMouthTrack(tl);", "addExplainerMouthTrack(tl);addExplainerMouthTrack(tl);")
    else:
        declaration = '<script src="assets/mouth-track.js"></script>'
        code = code.replace(declaration, "").replace("</body>", declaration + "</body>")
    path.write_text(code)
    with pytest.raises(ValueError, match="declaration"):
        freeze(cue_job, proposal)


def test_baked_sync_binds_both_real_files(tmp_path):
    job = tmp_path.resolve() / "animated"
    example.fixture(job, framing="full", performance="animated")
    path = job / "inputs/sync.json"
    sync = ex.load(path)
    for index, key in enumerate(("master_sha256", "video_sha256"), 1):
        save(path, {**sync, key: "0" * 64})
        with pytest.raises(ValueError, match="sync receipt mismatch"):
            propose(job, name=f"proposal-v{index}")


@pytest.mark.parametrize("mutation", ["silent-cues", "none-body", "none-puppet", "still-baked", "animated-cues"])
def test_no_audio_and_character_performance_contradictions(cue_job, mutation):
    plan = hashed(ex.load(cue_job / "spec.json"))
    if mutation == "silent-cues":
        plan["audio"] = dict(mode="none", master=None, script=None, receipt=None, captions=None, timing=None)
    elif mutation == "none-body":
        plan["character"]["framing"] = "none"
    elif mutation == "none-puppet":
        plan["character"].update(framing="none", body=None, mouths={}, cues=None, lip_sync="off")
    elif mutation == "still-baked":
        plan["character"]["lip_sync"] = "baked"
    else:
        plan["character"]["performance"] = "animated"
    with pytest.raises(ValueError):
        ex.model(plan)


@pytest.mark.parametrize("mutation", ["extra-audio", "retimed", "gain", "missing-master", "unmuted-video", "mouth-opacity"])
def test_markup_media_contradictions(cue_job, mutation):
    proposal = propose(cue_job)
    source = example.author_source(cue_job, proposal)
    path = source / "index.html"
    html = path.read_text()
    if mutation == "extra-audio":
        html = html.replace('</body>', '<audio id="second" src="assets/tone.wav"></audio></body>')
    elif mutation == "retimed":
        html = html.replace('id="master"', 'id="master" data-media-start="1"')
    elif mutation == "gain":
        html = html.replace('id="master"', 'id="master" data-volume="0.5"')
    elif mutation == "missing-master":
        html = html.replace('<audio ', '<div ').replace('</audio>', '</div>')
    elif mutation == "unmuted-video":
        html = html.replace('</body>', '<video id="extra" src="assets/body.png" data-start="0" data-duration="6"></video></body>')
    else:
        html = html.replace('style="opacity: 1"', 'style="opacity: 0"')
    path.write_text(html)
    with pytest.raises(ValueError):
        freeze(cue_job, proposal)


def fake_hf(project, args, evidence, fault=None):
    """Fake only HTML rendering; use real image/audio codecs and decode checks."""
    plan = ex.load(project / "plan.json")
    width, height = ex.SIZES[plan["aspect"]]
    if args[0] == "check":
        save(evidence, {"ok": True, "contrast": {"enabled": True, "checked": 5}})
    elif args[0] == "snapshot":
        frames = Path(args[args.index("-o") + 1])
        frames.mkdir()
        for index, _ in enumerate(plan["samples"]):
            Image.new("RGB", (width, height), (16, 32, 48)).save(frames / f"{index:02}.png")
        evidence.write_text("Synthetic snapshot, not HTML rendering proof")
    elif args[0] == "render":
        assert "--strict" in args and "--no-best-effort" in args
        if fault == "dimensions":
            width = 320
        duration = 1 if fault == "duration" else plan["duration"]
        fps = 24 if fault == "fps" else 30
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
               f"color=c=0x102030:s={width}x{height}:d={duration}:r={fps}"]
        if plan["audio"]["master"] and fault != "missing-audio":
            cmd += ["-i", str(project / plan["audio"]["master"]), "-c:a", "aac"]
        if fault == "extra-audio":
            cmd += ["-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000", "-c:a", "aac"]
        if fault == "extra-video":
            cmd += ["-map", "0:v", "-map", "0:v"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-t", str(duration), args[args.index("--output") + 1]]
        subprocess.run(cmd, check=True, capture_output=True)
        evidence.write_text("Synthetic media, not HTML rendering proof")
    else:
        pytest.fail(f"Unexpected HF operation: {args}")


def preview(job, monkeypatch):
    freeze(job)
    monkeypatch.setattr(ex, "hf", fake_hf)
    monkeypatch.setattr(ex, "runtime_identity", lambda: {"path": "/synthetic/hyperframes", "version": "fixture-1"})
    return ex.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))


def render(job, receipt, out="final"):
    return ex.render(SimpleNamespace(project=str(job / "project"), approved_preview=receipt["preview"],
                     approval_sha256=receipt["preview_sha256"], out=str(job / out)))


@pytest.mark.parametrize("audio,aspect", [(False, "16:9"), (True, "9:16")])
def test_fake_hf_end_to_end_real_stream_invariants(tmp_path, monkeypatch, audio, aspect):
    job = tmp_path.resolve() / "integration"
    example.fixture(job, audio=audio, aspect=aspect)
    receipt = preview(job, monkeypatch)
    result = render(job, receipt)
    assert result["decoded"] is True
    assert (result["width"], result["height"]) == ex.SIZES[aspect]
    assert result["fps"] == 30 and abs(result["duration"] - example.DURATION) <= .1
    assert (result["audio"] is not None) == audio
    assert result["listening"] == "unverified" and result["semantic_review"] == "pending"
    assert result["media_generation"] == 0
    assert len(list((job / "final/review").glob("*.png"))) == 5
    assert Image.open(job / "final/poster.png").size == ex.SIZES[aspect]
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", result["mp4"]],
                                    check=True, capture_output=True, text=True).stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    assert video["avg_frame_rate"] == "30/1"
    assert sum(s["codec_type"] == "audio" for s in info["streams"]) == int(audio)
    with pytest.raises(ValueError, match="must not exist"):
        render(job, receipt)


@pytest.mark.parametrize("fault,audio", [("dimensions", False), ("fps", False), ("duration", False),
                                       ("extra-audio", False), ("missing-audio", True), ("extra-video", False)])
def test_final_stream_mismatch_never_publishes_passing_qa(tmp_path, monkeypatch, fault, audio):
    job = tmp_path.resolve() / "bad-render"
    example.fixture(job, audio=audio)
    receipt = preview(job, monkeypatch)
    monkeypatch.setattr(ex, "hf", lambda root, args, evidence: fake_hf(root, args, evidence, fault))
    with pytest.raises(ValueError, match="final .*mismatch|one final video"):
        render(job, receipt)
    assert not (job / "final/qa.json").exists()


def test_rendered_cue_fixture_does_not_claim_speech_or_lip_sync_proof(cue_job, monkeypatch):
    result = render(cue_job, preview(cue_job, monkeypatch))
    assert result["lip_sync"] == "unverified"
    assert result["listening"] == "unverified"
    assert result["semantic_review"] == "pending"
    assert "speech/viseme quality and listening remain unverified" in (cue_job / "final/qa.md").read_text()


def test_missing_decoded_review_frame_does_not_publish_qa(job, monkeypatch):
    receipt = preview(job, monkeypatch)
    original = ex.command

    def skip_last_frame(args, **kwargs):
        if args[0] == "ffmpeg" and "-frames:v" in args and args[-1].endswith("/review/04.png"):
            return ""
        return original(args, **kwargs)

    monkeypatch.setattr(ex, "command", skip_last_frame)
    with pytest.raises(ValueError, match="review frame extraction incomplete"):
        render(job, receipt)
    assert not (job / "final/qa.json").exists()


@pytest.mark.parametrize("mutation", ["hash", "frame", "check", "project", "runtime", "times", "traversal"])
def test_render_requires_unchanged_approved_preview(job, monkeypatch, mutation):
    receipt = preview(job, monkeypatch)
    if mutation == "hash":
        receipt["preview_sha256"] = "0" * 64
    elif mutation == "frame":
        Image.new("RGB", (32, 32)).save(job / "preview/frames/00.png")
    elif mutation == "check":
        (job / "preview/check.json").write_text("{}")
    elif mutation == "project":
        with (job / "project/index.html").open("a") as out:
            out.write("<!-- changed -->")
    elif mutation == "runtime":
        monkeypatch.setattr(ex, "runtime_identity", lambda: {"path": "/synthetic/hyperframes", "version": "fixture-2"})
    else:
        path = job / "preview/preview.json"
        data = ex.load(path)
        if mutation == "times":
            data["times"][1] = 1.1
        else:
            data["frames"]["../00.png"] = data["frames"].pop("00.png")
        save(path, data)
        receipt["preview_sha256"] = ex.digest(path)
    with pytest.raises(ValueError):
        render(job, receipt)
    assert not (job / "final").exists()


@pytest.mark.parametrize("stage", ["snapshot", "render"])
def test_preview_and_render_reject_output_parent_traversal(job, monkeypatch, stage):
    receipt = preview(job, monkeypatch)
    (job / "child").mkdir()
    destination = job / "child/../escaped-output"
    with pytest.raises(ValueError, match="traversal|canonical"):
        if stage == "snapshot":
            ex.snapshot(SimpleNamespace(project=str(job / "project"), out=str(destination)))
        else:
            render(job, receipt, out="child/../escaped-output")
    assert not (job / "escaped-output").exists()


@pytest.mark.parametrize("fault", ["dimensions", "count", "runtime"])
def test_preview_requires_full_sized_samples_and_stable_runtime(job, monkeypatch, fault):
    freeze(job)
    identities = iter([{"version": "fixture-1"}, {"version": "fixture-2" if fault == "runtime" else "fixture-1"}])
    monkeypatch.setattr(ex, "runtime_identity", lambda: next(identities))

    def bad_snapshot(root, args, evidence):
        fake_hf(root, args, evidence)
        if args[0] == "snapshot":
            frame = job / "preview/frames/00.png"
            if fault == "dimensions":
                Image.new("RGB", (32, 32)).save(frame)
            elif fault == "count":
                frame.unlink()

    monkeypatch.setattr(ex, "hf", bad_snapshot)
    with pytest.raises(ValueError, match="preview frames|runtime changed"):
        ex.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    assert not (job / "preview/preview.json").exists()


def test_runtime_change_during_render_does_not_publish_qa(job, monkeypatch):
    receipt = preview(job, monkeypatch)
    identities = iter([{"path": "/synthetic/hyperframes", "version": "fixture-1"},
                       {"path": "/synthetic/hyperframes", "version": "fixture-2"}])
    monkeypatch.setattr(ex, "runtime_identity", lambda: next(identities))
    with pytest.raises(ValueError, match="runtime changed during render"):
        render(job, receipt)
    assert not (job / "final/qa.json").exists()


@pytest.mark.parametrize("audit", [
    {"ok": False, "contrast": {"enabled": True, "checked": 1}},
    {"ok": True, "contrast": {"enabled": False, "checked": 1}},
    {"ok": True, "contrast": {"enabled": True, "checked": 0}},
])
def test_skipped_or_failed_audit_cannot_authorize_preview(job, monkeypatch, audit):
    freeze(job)
    monkeypatch.setattr(ex, "runtime_identity", lambda: {"version": "fixture"})
    monkeypatch.setattr(ex, "hf", lambda root, args, evidence: save(evidence, audit))
    with pytest.raises(ValueError, match="audit failed or skipped"):
        ex.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    assert not (job / "preview/preview.json").exists()


def test_missing_runtime_fails_without_install(monkeypatch):
    monkeypatch.setattr(ex.shutil, "which", lambda _: None)
    monkeypatch.setattr(ex, "command", lambda *args, **kwargs: pytest.fail("must not install or invoke a missing runtime"))
    with pytest.raises(ValueError, match="no automatic install"):
        ex.runtime_identity()


def test_fixture_cli_native_render_requires_explicit_synthetic_approval(tmp_path):
    root = tmp_path / "not-created"
    result = subprocess.run([sys.executable, str(FIXTURE), "--root", str(root), "--render"],
                            capture_output=True, text=True)
    assert result.returncode == 2 and "--approve-synthetic" in result.stderr
    assert not root.exists()


def test_fixture_cli_default_only_proposes_and_authors_source(tmp_path):
    root = tmp_path.resolve() / "cli-fixture"
    result = subprocess.run([sys.executable, str(FIXTURE), "--root", str(root), "--framing", "full",
                             "--performance", "puppet"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["native_rendered"] is False and report["proof"] == example.NOTICE
    assert report["proposal"]["status"] == "awaiting-approval"
    assert (root / "source/index.html").is_file()
    assert not (root / "project").exists() and not list(root.glob("**/*.mp4"))


def test_skill_frontmatter_and_real_hermes_discovery(monkeypatch):
    from agent import skill_utils
    from tools import skills_tool

    text = (LEAF / "SKILL.md").read_text(encoding="utf-8")
    assert text.index("\n---\n", 3) + len("\n---\n") <= 3800
    full, _ = skill_utils.parse_frontmatter(text)
    prefix, _ = skill_utils.parse_frontmatter(text[:4000])
    assert full == prefix and prefix["name"] == "create-explainer-video"
    assert full["metadata"]["hermes"]["form"]["lip_sync"]["options"] == ["off", "cues", "baked"]
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", LEAF.parents[1])
    monkeypatch.setattr(skills_tool, "_SKILLS_CACHE", {})
    monkeypatch.setattr(skill_utils, "get_external_skills_dirs", lambda: [])
    monkeypatch.setattr(skill_utils, "get_project_skills_dirs", lambda: [])
    names = [item["name"] for item in skills_tool._find_all_skills(skip_disabled=True)]
    assert names.count("create-explainer-video") == 1
    assert "explainer-video" not in names
