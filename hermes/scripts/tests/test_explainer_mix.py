"""Real Mix consumption with synthetic test-only speech timing, never ASR/TTS.

Only the HyperFrames boundary is faked; Mix DSP, approvals, copy checks and
final ffmpeg decode/peak checks are real. This is not a native renderer test.
"""

import copy
import hashlib
import html
import importlib.util
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

EXAMPLE = Path(__file__).parent / "fixtures/explainer-video/example.py"
_spec = importlib.util.spec_from_file_location("explainer_mix_example", EXAMPLE)
example = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = example
_spec.loader.exec_module(example)
explainer = example.explainer

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe required",
)


@pytest.fixture
def mix_job(tmp_path):
    root = tmp_path.resolve() / "job"
    spec = example.fixture(root)
    voice = root / "inputs/tone.wav"
    with wave.open(str(voice), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    # Hand-authored timing is valid only for this synthetic test, not speech proof.
    captions, words = [], []
    for unit in spec["units"]:
        start = unit["start"] + .4
        captions.append({"start": start, "end": start + 1, "text": unit["narration"]})
        words.extend({"start": start + i * .3, "end": start + i * .3 + .2, "word": word}
                     for i, word in enumerate(unit["narration"].split()))
    sidecar = root / "inputs/tone.words.json"
    explainer.write(sidecar, {
        "file": voice.name, "duration": example.DURATION,
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "words": words, "captions": captions, "segments": captions,
    })
    cue = {"id": "voice", "source": "voice", "start": 0,
           "source_start": 0, "duration": example.DURATION}
    timing = root / "inputs/timing.json"
    explainer.write(timing, {"version": 1, "duration_seconds": example.DURATION, "cues": [cue]})
    mix_spec = root / "mix-spec.json"
    explainer.write(mix_spec, {
        "version": 1, "what_for": "Explainer integration test", "direction": "Synthetic test tone only",
        "duration_seconds": example.DURATION, "channels": 1,
        "target_lufs": None, "true_peak_dbtp": -9,
        "sources": [{"id": "voice", "path": str(voice), "role": "speech", "words": str(sidecar)}],
        "cues": [{**cue, "gain_db": -3, "fade_in": 0, "fade_out": 0, "envelope": []}],
        "timing": str(timing),
    })
    description = root / "mix-description.md"
    description.write_text("Synthetic fixture approval only; no production speech or listening claim.", encoding="utf-8")
    mix_media = explainer.mix_audio.load_mix_media()
    proposal = mix_media.propose(str(mix_spec), str(description), str(root / "mix-proposal-v1"))
    rendered = mix_media.render(proposal["approved_plan"], proposal["approval_sha256"],
                                "create", str(root / "mix-bundle"), slug="fixture")
    assert rendered["status"] in ("PASS", "WARN"), rendered
    bundle = Path(rendered["out"])
    assert explainer.mix_audio.verify_full_bundle(bundle)["take"]["status"] in ("PASS", "WARN")
    receipt = explainer.load(bundle / "mix.take.json")
    master = receipt["master"]["file"]
    spec["assets"].pop("assets/tone.wav")
    for name in (master, "mix.take.json", "captions.json", "timing.json"):
        spec["assets"]["assets/" + name] = str(bundle / name)
    spec["audio"].update(mode="mix", master="assets/" + master, receipt="assets/mix.take.json",
                         captions="assets/captions.json", timing="assets/timing.json")
    captions = explainer.load(bundle / "captions.json")["captions"]
    spec["copy"].extend({"id": f"mix-caption-{i}", "text": caption["text"],
                         "start": caption["start"], "end": caption["end"]}
                        for i, caption in enumerate(captions, 1))
    return SimpleNamespace(root=root, spec=spec, bundle=bundle, receipt=receipt, voice=voice)


def prepare(job, version=1):
    spec_path = job.root / f"explainer-spec-v{version}.json"
    explainer.write(spec_path, job.spec)
    proposal = explainer.propose(SimpleNamespace(
        spec=str(spec_path), out=str(job.root / f"proposal-v{version}")))
    assert proposal["status"] == "awaiting-approval" and proposal["media_generation"] == 0
    author = job.root / f"author-v{version}"
    author.mkdir()
    source = example.author_source(author, proposal)
    captions = explainer.load(source / job.spec["audio"]["captions"])["captions"]
    spans = "\n".join(
        f'<span id="mix-caption-{i}" class="clip" data-start="{cue["start"]}" '
        f'data-duration="{cue["end"] - cue["start"]}" data-track-index="4">{html.escape(cue["text"])}</span>'
        for i, cue in enumerate(captions, 1)
    )
    index = source / "index.html"
    code = index.read_text(encoding="utf-8")
    marker = "</div>\n<script>"
    assert code.count(marker) == 1
    index.write_text(code.replace(marker, spans + "\n" + marker), encoding="utf-8")
    return SimpleNamespace(approved_plan=proposal["proposal"], approval_sha256=proposal["approval_sha256"],
                           source=str(source), project=str(job.root / f"project-v{version}"))


def test_real_mix_propose_freeze_preserves_original_bundle_subset(mix_job):
    args = prepare(mix_job)
    result = explainer.freeze(args)
    assert result["rendered_mp4"] is False
    project, plan = explainer.project_model(args.project)
    assert plan["audio"] == mix_job.spec["audio"]
    assert plan["copy"] == mix_job.spec["copy"]
    assert [r["id"] for r in plan["copy"] if r["id"].startswith("mix-caption-")] == [
        "mix-caption-1", "mix-caption-2", "mix-caption-3",
    ]
    assert Path(plan["audio"]["master"]).name == mix_job.receipt["master"]["file"]
    for field in ("master", "receipt", "captions", "timing"):
        staged = project / plan["audio"][field]
        assert staged.read_bytes() == (mix_job.bundle / staged.name).read_bytes()
    assert (project / plan["audio"]["script"]).read_text(encoding="utf-8") == example.SCRIPT
    assert not (project / "assets/tone.wav").exists()


def test_mix_proposal_rejects_master_receipt_hash_and_filename_mismatch(mix_job):
    spec = copy.deepcopy(mix_job.spec)
    master = spec["audio"]["master"]
    for version, defect in enumerate(("hash", "filename"), 1):
        invalid = copy.deepcopy(spec)
        if defect == "hash":
            # Valid same-duration PCM, but not the gain-adjusted master in the receipt.
            invalid["assets"][master] = str(mix_job.voice)
        else:
            invalid["audio"]["master"] = "assets/renamed.wav"
            invalid["assets"]["assets/renamed.wav"] = invalid["assets"].pop(master)
        spec_path = mix_job.root / f"invalid-spec-v{version}.json"
        explainer.write(spec_path, invalid)
        with pytest.raises(ValueError, match=f"Mix master {defect} mismatch"):
            explainer.propose(SimpleNamespace(spec=str(spec_path),
                                              out=str(mix_job.root / f"proposal-v{version}")))


def test_mix_caption_copy_conflicts_are_rejected_before_approval(mix_job):
    original = copy.deepcopy(mix_job.spec)
    for version, defect in enumerate(("missing-ledger", "changed-text", "changed-time"), 1):
        mix_job.spec = copy.deepcopy(original)
        if defect == "missing-ledger":
            mix_job.spec["copy"] = [r for r in mix_job.spec["copy"] if not r["id"].startswith("mix-caption-")]
        elif defect == "changed-text":
            mix_job.spec["copy"][-3]["text"] = "Changed caption."
        else:
            mix_job.spec["copy"][-3]["start"] += .1
        with pytest.raises(ValueError, match="Mix caption copy ledger"):
            prepare(mix_job, version)
        assert not (mix_job.root / f"proposal-v{version}/proposal.md").exists()


def test_mix_caption_markup_cannot_change_after_approval(mix_job):
    args = prepare(mix_job)
    index = Path(args.source) / "index.html"
    code = index.read_text(encoding="utf-8")
    assert code.count(">Check the cache.</span>") == 1
    index.write_text(code.replace(">Check the cache.</span>", ">Changed caption.</span>"), encoding="utf-8")
    with pytest.raises(ValueError, match="text mismatch"):
        explainer.freeze(args)
    assert not Path(args.project).exists()


def test_mix_freeze_forbids_dry_source_playing_beside_master(mix_job):
    mix_job.spec["assets"]["assets/tone.wav"] = str(mix_job.voice)
    args = prepare(mix_job)
    index = Path(args.source) / "index.html"
    code = index.read_text(encoding="utf-8")
    dry = ('<audio id="dry-voice" class="clip" src="assets/tone.wav" '
           'data-start="0" data-duration="6" data-track-index="5"></audio>')
    index.write_text(code.replace("</div>\n<script>", dry + "</div>\n<script>"), encoding="utf-8")
    with pytest.raises(ValueError, match="only the approved master may play"):
        explainer.freeze(args)
    assert not Path(args.project).exists()


def test_mix_postrender_measures_real_audio_and_rejects_peak_over_receipt(mix_job, monkeypatch):
    args = prepare(mix_job)
    explainer.freeze(args)
    gain = 1
    calls = []

    def fake_hf(root, argv, log):
        calls.append(argv[0])
        plan = explainer.load(root / "plan.json")
        if argv[0] == "check":
            explainer.write(log, {"ok": True, "contrast": {"enabled": True, "checked": 1}})
        elif argv[0] == "snapshot":
            frames = Path(argv[argv.index("-o") + 1])
            frames.mkdir()
            for i, _ in enumerate(plan["samples"]):
                Image.new("RGB", explainer.SIZES[plan["aspect"]], "#102030").save(frames / f"{i:02}.png")
            log.write_text("Synthetic frames; no native HyperFrames execution.\n", encoding="utf-8")
        elif argv[0] == "render":
            movie = argv[argv.index("--output") + 1]
            subprocess.run([
                "ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                f"color=c=0x102030:s=1280x720:r=30:d={plan['duration']}",
                "-i", str(root / plan["audio"]["master"]), "-map", "0:v:0", "-map", "1:a:0",
                "-af", f"volume={gain}", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", movie,
            ], capture_output=True, check=True, timeout=120)
            log.write_text("Synthetic ffmpeg video; no native HyperFrames execution.\n", encoding="utf-8")
        else:
            pytest.fail(f"unexpected HyperFrames command: {argv}")

    monkeypatch.setattr(explainer, "hf", fake_hf)
    monkeypatch.setattr(explainer, "runtime_identity", lambda: {"path": "test-only-hyperframes", "version": "test"})
    preview = explainer.snapshot(SimpleNamespace(project=args.project, out=str(mix_job.root / "preview")))
    render_args = SimpleNamespace(project=args.project, approved_preview=preview["preview"],
                                  approval_sha256=preview["preview_sha256"], out=str(mix_job.root / "final"))
    result = explainer.render(render_args)
    assert result["decoded"] is True and result["media_generation"] == 0
    assert result["audio"]["approved_true_peak_dbtp"] == -9
    assert result["audio"]["audio_duration_seconds"] == pytest.approx(example.DURATION, abs=.1)
    assert result["audio"]["input_tp"] <= -8.8
    assert result["listening"] == "unverified" and result["semantic_review"] == "pending"
    gain = 12
    render_args.out = str(mix_job.root / "too-loud")
    with pytest.raises(ValueError, match="final Mix true peak exceeds approved ceiling"):
        explainer.render(render_args)
    measured = explainer.mix_audio.measure_audio(Path(render_args.out) / "explainer.mp4")
    assert -8.8 < measured["input_tp"] < 0  # Below clipping, above this Mix's approved ceiling.
    assert not (Path(render_args.out) / "qa.json").exists()
    assert calls == ["check", "snapshot", "check", "render", "check", "render"]
