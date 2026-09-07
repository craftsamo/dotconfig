"""create-ad plan/freeze safety and semantic contracts; hf() is mocked for
snapshot/render (no headless-browser HyperFrames render needed), but the
surrounding ffprobe/ffmpeg decode/validation logic runs for real."""
import importlib.util
import json
import re
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "profiles/video-creator/skills/video-creator-pipeline/create/ad"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ad = _load("ad_render", LEAF / "scripts" / "ad-render.py")
example = _load("create_ad_example", Path(__file__).parent / "fixtures/create-ad/example.py")

# Captured before any fixture patches ad.runtime_identity, so the dedicated
# runtime_identity unit tests below can restore and exercise the real thing.
REAL_RUNTIME_IDENTITY = ad.runtime_identity


@pytest.fixture(autouse=True)
def mock_runtime_identity(monkeypatch):
    """The ordinary suite must not require an installed hyperframes CLI:
    pin a fake, stable runtime identity for every test by default."""
    monkeypatch.setattr(ad, "runtime_identity",
                         lambda: {"executable": "/test/hyperframes", "version": "0.test"})


@pytest.fixture
def job(tmp_path):
    root = tmp_path.resolve() / "job"
    example.fixture(root)
    return root


def freeze(root, name="project"):
    plan_path = root / "plan.json"
    return ad.freeze(SimpleNamespace(source=str(root / "source"), plan=str(plan_path),
                                     approval_sha256=ad.digest(plan_path), project=str(root / name)))


def load_plan(root):
    return json.loads((root / "plan.json").read_text(encoding="utf-8"))


def save_plan(root, plan):
    (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")


def add_asset(job, filename, content):
    """Write a new asset file and declare it in plan.json's asset map."""
    path = job / "source/assets" / filename
    path.write_bytes(content)
    plan = load_plan(job)
    plan["assets"][f"assets/{filename}"] = ad.digest(path)
    save_plan(job, plan)
    return path


def splice_into_root(job, snippet):
    """Insert an HTML snippet as the last child of #root, before the timeline <script>."""
    html = (job / "source/index.html").read_text(encoding="utf-8")
    marker = "</div>\n<script>"
    assert html.count(marker) == 1
    (job / "source/index.html").write_text(html.replace(marker, f"{snippet}{marker}", 1), encoding="utf-8")


def add_media(job, tag, filename, content, attrs):
    """Write a real media asset, declare it, and place it with an <audio>/<video> tag."""
    add_asset(job, filename, content)
    attr_str = " ".join(k if v is True else f'{k}="{v}"' for k, v in attrs.items())
    splice_into_root(job, f'<{tag} {attr_str} src="assets/{filename}"></{tag}>')


def make_wav(path, seconds=3.0, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def make_mp4(path, width=640, height=480, seconds=2, extra=()):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"color=c=blue:s={width}x{height}:d={seconds}:r=30",
                    *extra, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(path)],
                   check=True, capture_output=True)


def fake_hf(project, args, evidence):
    """Stands in for the hyperframes CLI: real ffmpeg/ffprobe still run on
    its output, only the HTML->frames/video step is faked."""
    plan = json.loads((project / "approved-plan.json").read_text(encoding="utf-8"))
    if args[0] == "check":
        evidence.write_text(json.dumps({"ok": True, "contrast": {"enabled": True, "checked": 2, "passed": 2}}),
                             encoding="utf-8")
    elif args[0] == "snapshot":
        times = args[args.index("--at") + 1].split(",")
        frames_dir = Path(args[args.index("-o") + 1])
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i in range(len(times)):
            Image.new("RGB", (plan["width"], plan["height"]), (i * 7 % 256, 0, 0)).save(frames_dir / f"{i:02}.png")
        evidence.write_text("snapshot ok", encoding="utf-8")
    elif args[0] == "render":
        movie = Path(args[args.index("--output") + 1])
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                        "-i", f"color=c=black:s={plan['width']}x{plan['height']}:d={plan['duration']}:r=30",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(movie)],
                       check=True, capture_output=True)
        evidence.write_text("render ok", encoding="utf-8")
    else:
        raise AssertionError(f"unexpected hf command: {args[0]}")


def preview_fixture(job, monkeypatch):
    freeze(job)
    monkeypatch.setattr(ad, "hf", fake_hf)
    return ad.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))


# ── plan validation: range/count, copy, CTA, unknown/duplicate fields ───────

@pytest.mark.parametrize("fault", [
    "duration-low", "duration-high", "wrong-width", "wrong-fps",
    "missing-message-row", "cta-text-mismatch", "cta-too-short",
    "duplicate-copy-id", "bad-copy-role", "claim-without-claims",
    "unordered-samples", "missing-first-sample", "missing-last-sample",
    "no-sample-in-claim-hold", "unknown-field", "wrong-version", "extra-copy-key",
    "empty-copy", "empty-samples", "too-few-samples", "too-many-samples",
    "sample-at-equals-duration", "bool-version", "bool-width", "message-too-long",
    "unknown-aspect", "bool-aspect", "list-aspect", "dict-aspect",
    "aspect-dims-mismatch", "arbitrary-dims-no-aspect",
])
def test_invalid_plan_rejected(job, fault):
    plan = load_plan(job)
    if fault == "duration-low":
        plan["duration"] = 5
    elif fault == "duration-high":
        plan["duration"] = 31
    elif fault == "wrong-width":
        plan["width"] = 1920
    elif fault == "wrong-fps":
        plan["fps"] = 24
    elif fault == "missing-message-row":
        plan["copy"] = [r for r in plan["copy"] if r["role"] != "message"]
    elif fault == "cta-text-mismatch":
        for row in plan["copy"]:
            if row["role"] == "cta":
                row["text"] = "Something else entirely"
    elif fault == "cta-too-short":
        for row in plan["copy"]:
            if row["role"] == "cta":
                row["end"] = row["start"] + 1
    elif fault == "duplicate-copy-id":
        plan["copy"][1]["id"] = plan["copy"][0]["id"]
    elif fault == "bad-copy-role":
        plan["copy"][0]["role"] = "headline"
    elif fault == "claim-without-claims":
        plan["claims"] = ""
    elif fault == "unordered-samples":
        plan["samples"][0], plan["samples"][1] = plan["samples"][1], plan["samples"][0]
    elif fault == "missing-first-sample":
        plan["samples"] = plan["samples"][1:]
    elif fault == "missing-last-sample":
        plan["samples"] = plan["samples"][:-1]
    elif fault == "no-sample-in-claim-hold":
        plan["samples"] = [s for s in plan["samples"] if not (6 < s["at"] < 10)]
    elif fault == "unknown-field":
        plan["extra"] = "nope"
    elif fault == "wrong-version":
        plan["version"] = 2
    elif fault == "extra-copy-key":
        plan["copy"][0]["extra"] = "x"
    elif fault == "empty-copy":
        plan["copy"] = []
    elif fault == "empty-samples":
        plan["samples"] = []
    elif fault == "too-few-samples":
        plan["samples"] = plan["samples"][:2]
    elif fault == "too-many-samples":
        base = plan["samples"][-1]
        plan["samples"] = [{"at": i * 0.01, "expect": "pad"} for i in range(41)]
        plan["samples"][0] = {"at": 0, "expect": "first"}
        plan["samples"][-1] = base
    elif fault == "sample-at-equals-duration":
        # There is no frame *at* `duration`; the last representable frame is
        # duration - 1/fps. A sample at exactly `duration` must be rejected,
        # not silently accepted as "the end".
        plan["samples"][-1] = {"at": plan["duration"], "expect": "past the last frame"}
    elif fault == "bool-version":
        plan["version"] = True  # True == 1 in Python; must not silently pass
    elif fault == "bool-width":
        plan["width"] = True
    elif fault == "message-too-long":
        # Longer than the 2000-char copy-row cap: no copy row could ever
        # match it, so this must be rejected as a length error, not surface
        # as a confusing "copy must include a message row" failure later.
        plan["message"] = "x" * 2500
    elif fault == "unknown-aspect":
        plan["aspect"] = "21:9"
    elif fault == "bool-aspect":
        plan["aspect"] = True  # must not be treated as a valid string ratio
    elif fault == "list-aspect":
        # Unhashable: isinstance must be checked (and fail) before any `in
        # ASPECT_SIZES` membership test that would otherwise raise TypeError.
        plan["aspect"] = ["9:16"]
    elif fault == "dict-aspect":
        plan["aspect"] = {"ratio": "9:16"}
    elif fault == "aspect-dims-mismatch":
        # A known ratio string whose declared width/height do not match its
        # fixed dims must still be rejected, not silently coerced.
        plan["aspect"] = "16:9"
    elif fault == "arbitrary-dims-no-aspect":
        # No `aspect` means only the original 9:16 1080x1920 dims validate;
        # an arbitrary size must not silently pass just because it is square.
        plan["width"] = 500
        plan["height"] = 500
    with pytest.raises(ValueError):
        ad.plan_model(plan)


def test_valid_plan_model_round_trips(job):
    plan = load_plan(job)
    model = ad.plan_model(plan)
    assert model["duration"] == 15
    assert (model["width"], model["height"], model["fps"]) == (1080, 1920, 30)


# ── aspect ratio support ─────────────────────────────────────────────────────

def test_plan_model_absent_aspect_stays_absent_and_resolves_916(job):
    """Old, pre-aspect plans never carried this field. Validation must still
    resolve them against the original 9:16 dims, and the default must never
    be written back into a plan that never had it (no default insertion)."""
    plan = load_plan(job)
    plan.pop("aspect", None)
    model = ad.plan_model(plan)
    assert "aspect" not in model
    assert (model["width"], model["height"]) == (1080, 1920)


@pytest.mark.parametrize("aspect", sorted(ad.ASPECT_SIZES))
def test_valid_aspect_freeze_snapshot_render(tmp_path, monkeypatch, aspect):
    root = (tmp_path / f"job-{aspect.replace(':', '-')}").resolve()
    example.fixture(root, aspect)
    width, height = ad.ASPECT_SIZES[aspect]
    result = freeze(root)
    assert result["duration"] == 15
    monkeypatch.setattr(ad, "hf", fake_hf)
    preview = ad.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
    for frame in sorted((root / "preview/frames").glob("*.png")):
        assert Image.open(frame).size == (width, height)
    report = ad.render(SimpleNamespace(project=str(root / "project"), approved_preview=str(root / "preview"),
                                       approval_sha256=preview["preview_sha256"], out=str(root / "final")))
    assert (report["width"], report["height"]) == (width, height)


def test_preview_cannot_authorize_a_different_aspect_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ad, "hf", fake_hf)
    root_a = (tmp_path / "job-a").resolve()
    root_b = (tmp_path / "job-b").resolve()
    example.fixture(root_a, "9:16")
    example.fixture(root_b, "16:9")
    freeze(root_a)
    freeze(root_b)
    preview = ad.snapshot(SimpleNamespace(project=str(root_a / "project"), out=str(root_a / "preview")))
    with pytest.raises(ValueError, match="approved preview belongs to another project"):
        ad.render(SimpleNamespace(project=str(root_b / "project"), approved_preview=str(root_a / "preview"),
                                  approval_sha256=preview["preview_sha256"], out=str(root_b / "final")))
    assert not (root_b / "final").exists()


def test_tampering_frozen_plan_aspect_detected(job):
    """Changing the frozen `approved-plan.json`'s aspect after freeze must be
    caught as a project integrity violation, not silently re-rendered at a
    different canvas."""
    freeze(job)
    plan = json.loads((job / "project/approved-plan.json").read_text(encoding="utf-8"))
    plan["aspect"] = "16:9"
    (job / "project/approved-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="changed since freeze"):
        ad.project_model(str(job / "project"))


# ── freeze: assets, symlinks, traversal, approval hash ──────────────────────

def test_valid_freeze(job):
    result = freeze(job)
    assert Path(result["project"]) == job / "project"
    assert result["duration"] == 15
    assert (job / "project/approved-plan.json").is_file()
    assert (job / "project/integrity.json").is_file()


def test_freeze_output_must_not_exist(job):
    freeze(job)
    with pytest.raises(ValueError, match="must not exist"):
        freeze(job)


def test_freeze_rejects_missing_declared_asset(job):
    (job / "source/assets/gsap-provenance.json").unlink()
    with pytest.raises(ValueError, match="differ from the approved plan"):
        freeze(job)
    assert not (job / "project").exists()


def test_freeze_rejects_asset_hash_mismatch(job):
    (job / "source/assets/GSAP-LICENSE.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from the approved plan"):
        freeze(job)


def test_freeze_rejects_undeclared_extra_asset(job):
    (job / "source/assets/extra.png").write_bytes(b"not a declared asset")
    with pytest.raises(ValueError, match="differ from the approved plan"):
        freeze(job)


def test_freeze_rejects_symlink(job):
    (job / "source/assets/link.js").symlink_to(job / "source/assets/gsap.min.js")
    with pytest.raises(ValueError, match="symlink"):
        freeze(job)
    assert not (job / "project").exists()


def test_freeze_rejects_traversal_project_path(job):
    (job / "scratch").mkdir()
    with pytest.raises(ValueError):
        freeze(job, "scratch/../project")
    assert not (job / "project").exists()


def test_freeze_rejects_wrong_approval_hash(job):
    plan_path = job / "plan.json"
    with pytest.raises(ValueError, match="changed since approval"):
        ad.freeze(SimpleNamespace(source=str(job / "source"), plan=str(plan_path),
                                  approval_sha256="0" * 64, project=str(job / "project")))
    assert not (job / "project").exists()


def test_freeze_rejects_malformed_approval_hash(job):
    plan_path = job / "plan.json"
    with pytest.raises(ValueError, match="approval sha256 required"):
        ad.freeze(SimpleNamespace(source=str(job / "source"), plan=str(plan_path),
                                  approval_sha256="not-a-hash", project=str(job / "project")))


# ── copy ledger against the real fixture: exact text, no silent additions ───

def test_freeze_rejects_copy_text_mismatch(job):
    html = (job / "source/index.html").read_text(encoding="utf-8")
    (job / "source/index.html").write_text(
        html.replace(example.MESSAGE, "A different message entirely"), encoding="utf-8")
    with pytest.raises(ValueError, match="text mismatch"):
        freeze(job)


def test_freeze_rejects_uncovered_visible_text(job):
    html = (job / "source/index.html").read_text(encoding="utf-8")
    html = html.replace("</body>", '<div id="extra">Undeclared visible copy</div></body>')
    (job / "source/index.html").write_text(html, encoding="utf-8")
    with pytest.raises(ValueError, match="silent additions"):
        freeze(job)


def test_freeze_rejects_missing_composition_id(job):
    html = (job / "source/index.html").read_text(encoding="utf-8")
    (job / "source/index.html").write_text(html.replace('data-composition-id="ad"', ''), encoding="utf-8")
    with pytest.raises(ValueError, match="one standalone composition root"):
        freeze(job)


# ── copy ledger parser unit tests: void tags, nesting, whitespace ───────────

def test_copy_check_handles_void_tags_without_leaking_text(tmp_path):
    (tmp_path / "index.html").write_text(
        '<html><body><div id="message">Before<img src="x.png"><meta charset="utf-8">After</div>'
        '<div id="cta">Go<br>Now</div></body></html>', encoding="utf-8")
    plan = {"copy": [
        {"id": "message", "text": "BeforeAfter", "role": "message", "start": 0, "end": 1},
        {"id": "cta", "text": "GoNow", "role": "cta", "start": 1, "end": 2},
    ]}
    ad.copy_check(tmp_path, plan)  # must not raise


def test_copy_check_void_tag_does_not_leak_stack_and_hide_uncovered_text(tmp_path):
    """Regression: an unbalanced push for a void <img> (no end tag ever
    arrives) used to leave a stale "active id" on the stack, silently
    absorbing later stray text into that id's buffer instead of flagging it."""
    (tmp_path / "index.html").write_text(
        '<html><body><div id="message">A<img src="x.png"></div>'
        '<span>LEAKED</span><div id="cta">B</div></body></html>', encoding="utf-8")
    plan = {"copy": [
        {"id": "message", "text": "A", "role": "message", "start": 0, "end": 1},
        {"id": "cta", "text": "B", "role": "cta", "start": 1, "end": 2},
    ]}
    with pytest.raises(ValueError, match="silent additions"):
        ad.copy_check(tmp_path, plan)


def test_copy_check_rejects_nested_ledger_ids(tmp_path):
    (tmp_path / "index.html").write_text(
        '<html><body><div id="message">Outer<span id="cta">Inner</span></div></body></html>', encoding="utf-8")
    plan = {"copy": [
        {"id": "message", "text": "OuterInner", "role": "message", "start": 0, "end": 1},
        {"id": "cta", "text": "Inner", "role": "cta", "start": 1, "end": 2},
    ]}
    with pytest.raises(ValueError, match="must not nest"):
        ad.copy_check(tmp_path, plan)


def test_copy_check_normalizes_both_sides_but_preserves_word_separation(tmp_path):
    (tmp_path / "index.html").write_text(
        '<html><body><div id="message">Hello   World</div></body></html>', encoding="utf-8")
    ad.copy_check(tmp_path, {"copy": [{"id": "message", "text": "Hello World", "role": "message",
                                       "start": 0, "end": 1}]})  # source-side extra spaces normalize
    ad.copy_check(tmp_path, {"copy": [{"id": "message", "text": "Hello   World", "role": "message",
                                       "start": 0, "end": 1}]})  # plan-side extra spaces normalize too
    with pytest.raises(ValueError, match="text mismatch"):
        ad.copy_check(tmp_path, {"copy": [{"id": "message", "text": "HelloWorld", "role": "message",
                                           "start": 0, "end": 1}]})  # normalization must not merge words


# ── image assets: decode before freeze, not a suffix-only guess ─────────────

def test_freeze_rejects_renamed_non_image_asset(job):
    add_asset(job, "logo.png", b"this is not a PNG file at all")
    splice_into_root(job, '<img id="logo" src="assets/logo.png">')
    with pytest.raises((ValueError, OSError)):
        freeze(job)
    assert not (job / "project").exists()


def test_freeze_rejects_oversized_image_asset(job):
    path = add_asset(job, "logo.png", b"")
    # 4100x4100 = 16,810,000px > the 16,000,000px cap; each side stays <=8192.
    Image.new("RGB", (4100, 4100), "red").save(path, "PNG")
    plan = load_plan(job)
    plan["assets"]["assets/logo.png"] = ad.digest(path)
    save_plan(job, plan)
    splice_into_root(job, '<img id="logo" src="assets/logo.png">')
    with pytest.raises(ValueError, match="pixel bounds"):
        freeze(job)


def test_freeze_rejects_animated_image_asset(job):
    path = add_asset(job, "logo.png", b"")
    frame1 = Image.new("RGB", (64, 64), "red")
    frame2 = Image.new("RGB", (64, 64), "blue")
    frame1.save(path, "PNG", save_all=True, append_images=[frame2], duration=100, loop=0)
    plan = load_plan(job)
    plan["assets"]["assets/logo.png"] = ad.digest(path)
    save_plan(job, plan)
    splice_into_root(job, '<img id="logo" src="assets/logo.png">')
    with pytest.raises(ValueError, match="static"):
        freeze(job)


def test_freeze_accepts_valid_static_image_asset(job):
    path = add_asset(job, "logo.png", b"")
    Image.new("RGB", (200, 200), "green").save(path, "PNG")
    plan = load_plan(job)
    plan["assets"]["assets/logo.png"] = ad.digest(path)
    save_plan(job, plan)
    splice_into_root(job, '<img id="logo" src="assets/logo.png">')
    freeze(job)


# ── media (audio/video) attrs, ids, probing, placement rules ────────────────

def test_freeze_rejects_unsupported_media_attribute(job):
    path = job / "source/assets/audio.wav"
    make_wav(path, seconds=3)
    add_media(job, "audio", "audio.wav", path.read_bytes(),
              {"id": "a1", "autoplay": True, "data-start": "1", "data-duration": "1"})
    with pytest.raises(ValueError, match="unsupported audio attributes"):
        freeze(job)


def test_freeze_rejects_media_missing_id(job):
    path = job / "source/assets/audio.wav"
    make_wav(path, seconds=3)
    add_media(job, "audio", "audio.wav", path.read_bytes(), {"data-start": "1", "data-duration": "1"})
    with pytest.raises(ValueError, match="requires a unique id"):
        freeze(job)


def test_freeze_rejects_duplicate_media_id(job):
    wav1, wav2 = job / "source/assets/a1.wav", job / "source/assets/a2.wav"
    make_wav(wav1, seconds=3)
    make_wav(wav2, seconds=3)
    add_media(job, "audio", "a1.wav", wav1.read_bytes(),
              {"id": "dup", "data-start": "1", "data-duration": "1"})
    add_media(job, "audio", "a2.wav", wav2.read_bytes(),
              {"id": "dup", "data-start": "5", "data-duration": "1"})
    with pytest.raises(ValueError, match="duplicate media id"):
        freeze(job)


def test_freeze_rejects_second_audio_track(job):
    wav1, wav2 = job / "source/assets/a1.wav", job / "source/assets/a2.wav"
    make_wav(wav1, seconds=3)
    make_wav(wav2, seconds=3)
    add_media(job, "audio", "a1.wav", wav1.read_bytes(),
              {"id": "a1", "data-start": "1", "data-duration": "1"})
    add_media(job, "audio", "a2.wav", wav2.read_bytes(),
              {"id": "a2", "data-start": "5", "data-duration": "1"})
    with pytest.raises(ValueError, match="at most one audio track"):
        freeze(job)


def test_freeze_rejects_data_media_start_nonzero(job):
    path = job / "source/assets/audio.wav"
    make_wav(path, seconds=3)
    add_media(job, "audio", "audio.wav", path.read_bytes(),
              {"id": "a1", "data-start": "1", "data-duration": "1", "data-media-start": "0.5"})
    with pytest.raises(ValueError, match="prepared media start must be zero"):
        freeze(job)


def test_freeze_rejects_unplaced_wav_asset(job):
    """A WAV present in assets/ but never referenced by an <audio> element
    is "surprise audio": declared, hashed, but silently never on screen."""
    path = job / "source/assets/orphan.wav"
    make_wav(path, seconds=1)
    add_asset(job, "orphan.wav", path.read_bytes())
    with pytest.raises(ValueError, match="placed by exactly one"):
        freeze(job)


def test_freeze_rejects_audio_duration_insufficient(job):
    path = job / "source/assets/audio.wav"
    make_wav(path, seconds=1)  # shorter than its declared 3s placement
    add_media(job, "audio", "audio.wav", path.read_bytes(),
              {"id": "a1", "data-start": "1", "data-duration": "3"})
    with pytest.raises(ValueError, match="audio file duration does not cover its placement"):
        freeze(job)


def test_freeze_accepts_single_placed_wav_asset(job):
    path = job / "source/assets/audio.wav"
    make_wav(path, seconds=4)
    add_media(job, "audio", "audio.wav", path.read_bytes(),
              {"id": "a1", "data-start": "1", "data-duration": "3"})
    freeze(job)


def test_freeze_rejects_video_duration_insufficient(job):
    path = job / "source/assets/clip.mp4"
    make_mp4(path, seconds=1)  # shorter than its declared 3s placement
    add_media(job, "video", "clip.mp4", path.read_bytes(),
              {"id": "v1", "muted": True, "playsinline": True, "data-start": "1", "data-duration": "3"})
    with pytest.raises(ValueError, match="video source duration does not cover its placement"):
        freeze(job)


def test_freeze_rejects_video_oversized_dimensions(job):
    path = job / "source/assets/clip.mp4"
    make_mp4(path, width=4200, height=4200, seconds=1)  # side > 4096 and area > 9,000,000
    add_media(job, "video", "clip.mp4", path.read_bytes(),
              {"id": "v1", "muted": True, "data-start": "1", "data-duration": "1"})
    with pytest.raises(ValueError, match="pixel bounds"):
        freeze(job)


def test_freeze_rejects_unmuted_video(job):
    path = job / "source/assets/clip.mp4"
    make_mp4(path, seconds=2)
    add_media(job, "video", "clip.mp4", path.read_bytes(),
              {"id": "v1", "data-start": "1", "data-duration": "1"})
    with pytest.raises(ValueError, match="video must be muted"):
        freeze(job)


def test_freeze_accepts_valid_video_asset(job):
    path = job / "source/assets/clip.mp4"
    make_mp4(path, seconds=3)
    add_media(job, "video", "clip.mp4", path.read_bytes(),
              {"id": "v1", "muted": True, "playsinline": True, "data-start": "1", "data-duration": "2"})
    freeze(job)


def test_freeze_rejects_js_volume_mutation(job):
    html = (job / "source/index.html").read_text(encoding="utf-8")
    html = html.replace("window.__timelines.ad=tl;",
                        "window.__timelines.ad=tl;\ndocument.querySelector('audio').volume=1;")
    (job / "source/index.html").write_text(html, encoding="utf-8")
    with pytest.raises(ValueError, match="audio automation requires a separately approved finishing path"):
        freeze(job)


# ── project immutability / tamper detection ──────────────────────────────────

def test_original_source_survives_and_frozen_edits_fail(job):
    original = (job / "source/index.html").read_bytes()
    freeze(job)
    (job / "project/index.html").write_text("changed", encoding="utf-8")
    assert (job / "source/index.html").read_bytes() == original
    with pytest.raises(ValueError, match="changed since freeze"):
        ad.project_model(str(job / "project"))


def test_new_file_in_project_detected(job):
    freeze(job)
    (job / "project/extra.js").write_text("const extra=1;")
    with pytest.raises(ValueError, match="changed since freeze"):
        ad.project_model(str(job / "project"))


def test_freeze_detects_corrupted_copy(job, monkeypatch):
    """The copy step itself must be verified, not merely trusted: a copy
    that silently landed with the wrong bytes must be caught before it is
    ever published as the frozen project."""
    original_copyfile = ad.shutil.copyfile

    def corrupting_copy(src, dst):
        original_copyfile(src, dst)
        if Path(dst).name == "index.html":
            Path(dst).write_bytes(b"corrupted-during-copy")

    monkeypatch.setattr(ad.shutil, "copyfile", corrupting_copy)
    with pytest.raises(ValueError, match="do not match the validated source inventory"):
        freeze(job)
    assert not (job / "project").exists() or not (job / "project/integrity.json").exists()


def test_freeze_detects_plan_mutation_after_serialization(job, monkeypatch):
    """The frozen plan snapshot must be re-validated immediately after being
    written, catching any drift between what was checked and what landed on
    disk as `approved-plan.json`."""
    original_write = ad.write

    def mutating_write(path, value):
        if Path(path).name == "approved-plan.json":
            value = {**value, "product": value["product"] + " (mutated)"}
        original_write(path, value)

    monkeypatch.setattr(ad, "write", mutating_write)
    with pytest.raises(ValueError, match="changed shape after serialization"):
        freeze(job)


# ── render requires actual approval, no bypass ───────────────────────────────

def test_render_requires_approval_args(job):
    freeze(job)
    with pytest.raises(ValueError, match="requires --approved-preview"):
        ad.render(SimpleNamespace(project=str(job / "project"), out=str(job / "final"),
                                  approved_preview=None, approval_sha256=None))
    assert not (job / "final").exists()


def test_render_requires_wellformed_approval_hash(job, monkeypatch):
    freeze(job)
    monkeypatch.setattr(ad, "hf", fake_hf)
    ad.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    with pytest.raises(ValueError, match="approval sha256 required"):
        ad.render(SimpleNamespace(project=str(job / "project"), out=str(job / "final"),
                                  approved_preview=str(job / "preview"), approval_sha256="not-a-hash"))
    assert not (job / "final").exists()


# ── mock snapshot/render interfaces (hf mocked; ffprobe/ffmpeg real) ────────

def test_explicit_null_aspect_is_not_a_legacy_omission(job):
    plan = load_plan(job)
    plan["aspect"] = None
    with pytest.raises(ValueError, match="aspect must be a known ratio"):
        ad.plan_model(plan)


def test_legacy_aspectless_plan_preview_render_preserves_bytes(job, monkeypatch):
    plan = load_plan(job)
    plan.pop("aspect")
    save_plan(job, plan)
    freeze(job)
    monkeypatch.setattr(ad, "hf", fake_hf)
    preview = ad.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    frozen_files = [p for root in (job / "project", job / "preview") for p in root.rglob("*") if p.is_file()]
    before = {p: ad.digest(p) for p in frozen_files}
    report = ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(job / "preview"),
                                      approval_sha256=preview["preview_sha256"], out=str(job / "final")))
    assert (report["width"], report["height"]) == (1080, 1920)
    assert "aspect" not in json.loads((job / "project/approved-plan.json").read_text())
    assert {p: ad.digest(p) for p in frozen_files} == before


def test_mock_snapshot_and_render_interfaces(job, monkeypatch):
    freeze(job)
    monkeypatch.setattr(ad, "hf", fake_hf)
    result = ad.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    assert result["frames"] == 5 and result["rendered_mp4"] is False
    assert result["preview_sha256"] == ad.digest(job / "preview/preview.json")

    report = ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(job / "preview"),
                                       approval_sha256=result["preview_sha256"], out=str(job / "final")))
    assert (report["width"], report["height"]) == (1080, 1920)
    assert abs(report["duration"] - 15) <= .1
    assert report["media_generation"] == 0
    assert report["temporal_review"] == "sampled only"
    assert report["audio_listening"] == "unverified"
    assert "pending" in report["semantic_review"]
    assert (job / "final/poster.png").is_file()
    assert (job / "final/qa.json").is_file()
    assert (job / "final/qa.md").is_file()


@pytest.mark.parametrize("fault", ["project", "integrity", "times", "frame", "check", "count"])
def test_render_rejects_changed_preview(job, monkeypatch, fault):
    result = preview_fixture(job, monkeypatch)
    preview_dir = job / "preview"
    if fault in ("project", "integrity", "times", "count"):
        data = json.loads((preview_dir / "preview.json").read_text(encoding="utf-8"))
        if fault == "project":
            data["project"] = "different"
        if fault == "integrity":
            data["integrity"] = "0" * 64
        if fault == "times":
            data["times"] = []
        if fault == "count":
            data["frames"].pop(next(iter(data["frames"])))
        (preview_dir / "preview.json").write_text(json.dumps(data), encoding="utf-8")
    if fault == "frame":
        (preview_dir / "frames" / "00.png").write_bytes(b"changed")
    if fault == "check":
        (preview_dir / "check.json").write_text(json.dumps({"ok": False}), encoding="utf-8")
    with pytest.raises(ValueError):
        ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(preview_dir),
                                  approval_sha256=result["preview_sha256"], out=str(job / f"final-{fault}")))
    assert not (job / f"final-{fault}").exists()


def test_render_rejects_runtime_changed_since_preview(job, monkeypatch):
    """A preview approved against one hyperframes runtime must not silently
    render against a different one later."""
    result = preview_fixture(job, monkeypatch)
    monkeypatch.setattr(ad, "runtime_identity",
                         lambda: {"executable": "/test/hyperframes", "version": "1.other"})
    with pytest.raises(ValueError, match="runtime changed since preview"):
        ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(job / "preview"),
                                  approval_sha256=result["preview_sha256"], out=str(job / "final")))
    assert not (job / "final").exists()


def test_render_accepts_unchanged_runtime_since_preview(job, monkeypatch):
    """The counterpart to the rejection above: an unchanged runtime between
    preview and render must not be blocked."""
    result = preview_fixture(job, monkeypatch)
    report = ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(job / "preview"),
                                       approval_sha256=result["preview_sha256"], out=str(job / "final")))
    assert (job / "final/ad.mp4").is_file()
    assert report["project"] == str(job / "project")


# ── runtime_identity(): the real function, command/shutil mocked ────────────

def test_runtime_identity_reports_resolved_binary_and_version(monkeypatch):
    monkeypatch.setattr(ad, "runtime_identity", REAL_RUNTIME_IDENTITY)
    monkeypatch.setattr(ad.shutil, "which", lambda name: "/usr/local/bin/hyperframes")
    monkeypatch.setattr(ad, "command", lambda args: "1.2.3\n")
    result = ad.runtime_identity()
    assert result == {"executable": str(Path("/usr/local/bin/hyperframes").resolve()), "version": "1.2.3"}


def test_runtime_identity_rejects_missing_hyperframes_binary(monkeypatch):
    monkeypatch.setattr(ad, "runtime_identity", REAL_RUNTIME_IDENTITY)
    monkeypatch.setattr(ad.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="hyperframes CLI missing"):
        ad.runtime_identity()


def test_snapshot_output_cannot_nest_inside_project(job):
    freeze(job)
    with pytest.raises(ValueError, match="outside source/project/preview"):
        ad.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "project" / "preview")))


def test_render_output_cannot_nest_inside_preview(job, monkeypatch):
    result = preview_fixture(job, monkeypatch)
    with pytest.raises(ValueError, match="outside source/project/preview"):
        ad.render(SimpleNamespace(project=str(job / "project"), approved_preview=str(job / "preview"),
                                  approval_sha256=result["preview_sha256"], out=str(job / "preview" / "final")))


# ── CLI-level exception handling (item 6) ────────────────────────────────────

@pytest.mark.parametrize("exc_type", [wave.Error, EOFError, subprocess.TimeoutExpired,
                                       PILImage.DecompressionBombError])
def test_main_catches_and_reports_known_exceptions(monkeypatch, capsys, exc_type):
    def boom(args):
        if exc_type is subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)
        raise exc_type("synthetic failure")

    monkeypatch.setattr(ad, "freeze", boom)
    monkeypatch.setattr(sys, "argv", ["ad-render.py", "freeze", "--source", "/x", "--plan", "/x",
                                      "--approval-sha256", "0" * 64, "--project", "/y"])
    with pytest.raises(SystemExit) as exc_info:
        ad.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "ad-render:" in captured.err
    assert exc_type.__name__ in captured.err


# ── docs: Pillow runtime convention, no "assets can be empty" claim (item 7) ─

def test_docs_use_pillow_runtime_and_no_empty_assets_claim():
    skill = (LEAF / "SKILL.md").read_text(encoding="utf-8")
    authoring = (LEAF / "references/authoring.md").read_text(encoding="utf-8")
    assert "uv run --no-project --with Pillow python" in skill
    assert "uv run --no-project --with Pillow python" in authoring
    assert "may be empty for a text-only ad" not in skill
    assert "may be `{}`" not in authoring
    assert "never `{}`" in authoring


# ── fixture content: explicitly fictional test evidence (item 8) ────────────

def test_fixture_is_explicitly_fictional_test_evidence(job):
    plan = load_plan(job)
    assert "TEST FIXTURE" in example.CLAIM
    assert "fictional" in example.CLAIM.lower()
    assert not re.search(r"\d+%", example.CLAIM)
    assert "no.1" not in example.CLAIM.lower() and "no1" not in example.CLAIM.lower().replace(".", "")
    assert "fictional" in plan["claims"].lower()
    html = (job / "source/index.html").read_text(encoding="utf-8")
    assert "<br" not in html.lower()  # HF lint disallows <br>; kept out of the real fixture
    assert "fictional" in html.lower()


def test_fixture_ledger_covers_all_visible_text_including_footnote(job):
    # copy_check succeeding on the real fixture (exercised by test_valid_freeze)
    # already proves every visible text node, including the footnote marker,
    # is accounted for in the ledger; this asserts the marker is actually there.
    plan = load_plan(job)
    claim_row = next(r for r in plan["copy"] if r["role"] == "claim")
    assert claim_row["text"].endswith("*")


# ── SKILL.md front matter: reference-backed options, closed leaf shape ──────

def test_reference_options_are_backed_by_files():
    data = yaml.safe_load((LEAF / "SKILL.md").read_text().split("---")[1])
    assert data["name"] == "create-ad"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "hands" and meta["hands"] == "video-creator" and meta["cost"] == "free"
    form = meta["form"]
    assert "note" in form
    for key, folder in (("theme", "themes"), ("style", "styles"), ("direction", "direction")):
        assert form[key]["other"] is True
        assert not form[key]["required"]
        for option in form[key]["options"]:
            assert (LEAF / "references" / folder / (option + ".md")).is_file()
    for required_key in ("product", "audience", "message", "cta", "assets"):
        assert form[required_key]["required"] is True
    assert form["assets"]["type"] == "path"
