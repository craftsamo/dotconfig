"""Tests for analyze-ad's ad-evidence.py: bounded, local advertising review
evidence (sample-time math, output safety, and a real ffmpeg/Pillow extraction
round-trip). ad-evidence.py is loaded as a module (not run as a subprocess) so
`ad.sample_times` / `ad.collect` / `ad.sha256` are exercised directly, mirroring
test_create_ad.py's module-import pattern.

The `Collect*` tests that decode real frames need ffmpeg/ffprobe on PATH and
are skipped otherwise. Temp directories come from `tempfile` (never pytest's
`tmp_path`) and are resolved up front: on macOS `/tmp`/`/var` are symlinks into
`/private/...`, and ad-evidence.py's `source.resolve(strict=True)` follows
that symlink, so an un-resolved test root would make manifest["source"]
comparisons fail spuriously.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "profiles/video-creator/skills/video-creator-pipeline/analyze/ad"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ad = _load("ad_evidence", LEAF / "scripts" / "ad-evidence.py")

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
HAVE_FFMPEG = bool(FFMPEG and FFPROBE)
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not found")


def probe_info(duration=10.0, fps=30.0):
    return {"duration": duration, "fps": fps}


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as tmp:
        # Resolve up front: ad.collect()/ad.sha256() resolve the source path,
        # and macOS's /tmp -> /private/tmp symlink would otherwise desync an
        # un-resolved test root from the resolved paths the module returns.
        yield Path(tmp).resolve()


def make_clip(path, duration=1.0, size="64x64", fps=25, audio=True):
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", f"testsrc2=size={size}:rate={fps}:duration={duration}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    args.append(str(path))
    subprocess.run(args, check=True, capture_output=True, text=True)


# ── sample_times: overview first/last/ordered, <=60s ─────────────────────────

def test_sample_times_overview_first_last_ordered():
    result = ad.sample_times(probe_info(duration=10, fps=30), "overview", count=30)
    assert len(result) == 30
    assert result[0] == 0
    last = max(0, 10 - max(1 / 30, .05))
    assert result[-1] == pytest.approx(last)
    assert result == sorted(result)
    assert all(b > a for a, b in zip(result, result[1:]))


def test_sample_times_overview_rejects_over_60s():
    with pytest.raises(ValueError, match="60 seconds"):
        ad.sample_times(probe_info(duration=61), "overview", count=30)


@pytest.mark.parametrize("duration", [math.inf, math.nan, 0, -1])
def test_sample_times_overview_rejects_nonfinite_or_nonpositive_duration(duration):
    with pytest.raises(ValueError, match="60 seconds"):
        ad.sample_times(probe_info(duration=duration), "overview", count=30)


# ── sample_times: window bounds <=3s, count<=16 ───────────────────────────────

def test_sample_times_window_valid_bounds():
    result = ad.sample_times(probe_info(duration=10, fps=30), "window", count=8, start=1, duration=2)
    last = max(0, 10 - max(1 / 30, .05))
    end = min(1 + 2, last)
    assert len(result) == 8
    assert result[0] == pytest.approx(1)
    assert result[-1] == pytest.approx(end)


def test_sample_times_window_duration_over_3_rejected():
    with pytest.raises(ValueError, match="3 seconds"):
        ad.sample_times(probe_info(duration=10), "window", count=8, start=0, duration=4)


def test_sample_times_window_count_over_16_rejected():
    with pytest.raises(ValueError, match=r"3\.\.16"):
        ad.sample_times(probe_info(duration=10), "window", count=17, start=0, duration=2)


def test_sample_times_window_count_under_3_rejected():
    with pytest.raises(ValueError, match=r"3\.\.16"):
        ad.sample_times(probe_info(duration=10), "window", count=2, start=0, duration=2)


def test_sample_times_window_start_past_source_rejected():
    with pytest.raises(ValueError, match="3 seconds"):
        ad.sample_times(probe_info(duration=10, fps=30), "window", count=8, start=9.96, duration=2)


def test_sample_times_window_end_exceeds_total_rejected():
    with pytest.raises(ValueError, match="3 seconds"):
        ad.sample_times(probe_info(duration=10), "window", count=8, start=9, duration=2)


# ── sample_times: detail bounds, rejects nan ──────────────────────────────────

def test_sample_times_detail_valid():
    result = ad.sample_times(probe_info(duration=2, fps=25), "detail", at=0)
    assert result == [0]


@pytest.mark.parametrize("at", [math.nan, math.inf, -math.inf])
def test_sample_times_detail_rejects_nan(at):
    with pytest.raises(ValueError, match="decodable frame"):
        ad.sample_times(probe_info(duration=2, fps=25), "detail", at=at)


def test_sample_times_detail_rejects_out_of_range():
    last = max(0, 2 - max(1 / 25, .05))
    with pytest.raises(ValueError, match="decodable frame"):
        ad.sample_times(probe_info(duration=2, fps=25), "detail", at=last + .5)
    with pytest.raises(ValueError, match="decodable frame"):
        ad.sample_times(probe_info(duration=2, fps=25), "detail", at=-.1)


# ── collect: output must be new/exclusive, no traversal/symlinks ────────────

def collect_args(source, output, mode="overview", **overrides):
    base = dict(mode=mode, source=str(source), output=str(output),
                count=30, start=0, duration=2, at=0)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_collect_rejects_existing_output(workdir):
    source = workdir / "source.mp4"
    source.write_bytes(b"not a real video, but exists")
    out = workdir / "existing"
    out.mkdir()
    with pytest.raises(ValueError, match="must be new"):
        ad.collect(collect_args(source, out))


def test_collect_rejects_missing_parent(workdir):
    source = workdir / "source.mp4"
    source.write_bytes(b"placeholder")
    out = workdir / "missing" / "evidence"
    with pytest.raises(ValueError, match="existing absolute parent"):
        ad.collect(collect_args(source, out))


def test_collect_rejects_output_traversal(workdir):
    source = workdir / "source.mp4"
    source.write_bytes(b"placeholder")
    (workdir / "scratch").mkdir()
    out = workdir / "scratch" / ".." / "evil"
    with pytest.raises(ValueError, match="traversal"):
        ad.collect(collect_args(source, out))


def test_collect_rejects_symlinked_output_parent(workdir):
    source = workdir / "source.mp4"
    source.write_bytes(b"placeholder")
    real_dir = workdir / "real"
    real_dir.mkdir()
    link_dir = workdir / "link"
    link_dir.symlink_to(real_dir)
    out = link_dir / "evidence"
    with pytest.raises(ValueError, match="symlink"):
        ad.collect(collect_args(source, out))


# ── sha256: source hash captured, independent of ffmpeg ──────────────────────

def test_sha256_matches_hashlib(workdir):
    path = workdir / "data.bin"
    data = b"hello ad-evidence" * 100
    path.write_bytes(data)
    assert ad.sha256(path) == hashlib.sha256(data).hexdigest()


# ── collect (ffmpeg): overview probe sizes, source hash, no overwrite ───────

@needs_ffmpeg
@pytest.mark.parametrize("audio", [True, False])
def test_collect_overview_probe_and_hash(workdir, audio):
    source = workdir / "ad.mp4"
    make_clip(source, duration=2.0, audio=audio)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    out = workdir / "overview"

    result = ad.collect(collect_args(source, out, mode="overview", count=3))
    assert result["frames"] == 3
    assert result["sheets"] == 1
    assert result["evidence"] == str(out / "evidence.json")

    manifest = json.loads((out / "evidence.json").read_text())
    assert manifest["source"] == str(source.resolve())
    assert manifest["source_sha256"] == source_hash
    assert manifest["probe"]["audio"] is audio
    assert manifest["probe"]["display_width"] == 64
    assert manifest["probe"]["display_height"] == 64

    times = [row["seek_seconds"] for row in manifest["frames"]]
    assert times == ad.sample_times(manifest["probe"], "overview", count=3)
    assert times[0] == 0
    for row in manifest["frames"]:
        frame_path = out / row["file"]
        assert frame_path.is_file()
        assert row["sha256"] == ad.sha256(frame_path)

    # Source is never modified during extraction.
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


@needs_ffmpeg
def test_collect_no_overwrite_evidence(workdir):
    source = workdir / "ad.mp4"
    make_clip(source, duration=2.0)
    out = workdir / "overview"
    ad.collect(collect_args(source, out, mode="overview", count=3))
    with pytest.raises(ValueError, match="must be new"):
        ad.collect(collect_args(source, out, mode="overview", count=3))


@needs_ffmpeg
def test_collect_window_and_detail_modes(workdir):
    source = workdir / "ad.mp4"
    make_clip(source, duration=2.0)

    window_out = workdir / "window"
    result = ad.collect(collect_args(source, window_out, mode="window",
                                      count=8, start=0.2, duration=1.0))
    assert result["frames"] == 8
    manifest = json.loads((window_out / "evidence.json").read_text())
    times = [row["seek_seconds"] for row in manifest["frames"]]
    assert times[0] == pytest.approx(0.2)
    assert times[-1] <= 0.2 + 1.0 + 1e-6

    detail_out = workdir / "detail"
    result = ad.collect(collect_args(source, detail_out, mode="detail", at=0.5))
    assert result["frames"] == 1
    assert result["sheets"] == 1
    manifest = json.loads((detail_out / "evidence.json").read_text())
    assert manifest["frames"][0]["seek_seconds"] == 0.5


@needs_ffmpeg
def test_collect_sheets_capped_12_per_page(workdir):
    source = workdir / "ad.mp4"
    make_clip(source, duration=3.0)
    out = workdir / "window-full"
    # count=16 is the max allowed for "window" mode; 12+4 frames -> 2 sheets.
    result = ad.collect(collect_args(source, out, mode="window",
                                      count=16, start=0, duration=3))
    assert result["frames"] == 16
    assert result["sheets"] == 2

    manifest = json.loads((out / "evidence.json").read_text())
    assert len(manifest["sheets"]) == 2
    assert [row["seek_seconds"] for row in manifest["frames"]] == \
        ad.sample_times(manifest["probe"], "window", count=16, start=0, duration=3)

    with Image.open(out / manifest["sheets"][0]["file"]) as page:
        assert page.size == (240 * 4, 344 * 3)  # 12 tiles: 4 cols x 3 rows
    with Image.open(out / manifest["sheets"][1]["file"]) as page:
        assert page.size == (240 * 4, 344 * 1)  # 4 tiles: 4 cols x 1 row


# ── SKILL.md: static contract refs, note/remote_analysis flag validation ────

def test_skill_front_matter_references_and_flags():
    data = yaml.safe_load((LEAF / "SKILL.md").read_text().split("---")[1])
    assert data["name"] == "analyze-ad"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "hands" and meta["hands"] == "video-creator" and meta["cost"] == "free"

    form = meta["form"]
    assert form["source"]["required"] is True and form["source"]["type"] == "file"
    assert form["remote_analysis"]["required"] is True
    assert form["remote_analysis"]["options"] == ["yes", "no"]
    assert "note" in form
    assert not form["note"].get("required", False)

    assert (LEAF / "references" / "inspection.md").is_file()
