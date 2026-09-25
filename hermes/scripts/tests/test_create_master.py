"""create-master: join/mux/caption helper contract and Creator routing.

Synthetic lavfi fixtures only; they prove the plumbing, not a client film.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
LEAF = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline/create/master"
CREATOR = HERMES_ROOT / "profiles/creator/skills/creator-pipeline"

spec = importlib.util.spec_from_file_location("create_master", LEAF / "scripts/master.py")
master = importlib.util.module_from_spec(spec)
spec.loader.exec_module(master)

_mix_spec = importlib.util.spec_from_file_location("create_master_mix_fixture", Path(__file__).parent / "test_explainer_mix.py")
_mix = importlib.util.module_from_spec(_mix_spec)
sys.modules[_mix_spec.name] = _mix
_mix_spec.loader.exec_module(_mix)
mix_job = _mix.mix_job

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg/ffprobe required")


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def video(path: Path, seconds: float, size="320x240", rate=30, source="testsrc2", sound=False):
    inputs = ["-f", "lavfi", "-i", f"{source}=size={size}:rate={rate}"]
    if sound:
        inputs += ["-f", "lavfi", "-i", "sine=f=440:r=48000"]
    ffmpeg(*inputs, "-t", seconds, "-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if sound else []), path)
    return path


def wav(path: Path, seconds: float):
    ffmpeg("-f", "lavfi", "-i", f"sine=f=330:r=48000:d={seconds},volume=0.3", "-c:a", "pcm_s16le", path)
    return path


def build(tmp_path: Path, *extra: str) -> tuple[int, dict | None, Path]:
    out = tmp_path / "out"
    args = ["build", "--out", str(out), "--slug", "demo", *extra]
    code = master.main(args)
    result = json.loads((out / "master.json").read_text()) if (out / "master.json").exists() else None
    return code, result, out


def test_form_is_one_leaf_within_the_discovery_window():
    text = (LEAF / "SKILL.md").read_text(encoding="utf-8")
    end = text.index("\n---\n", 3) + len("\n---\n")
    assert end <= 3800
    meta = yaml.safe_load(text[3:end - 5])
    assert meta["name"] == "create-master"
    hermes = meta["metadata"]["hermes"]
    assert (hermes["hands"], hermes["cost"]) == ("video-creator", "free")
    form = hermes["form"]
    assert form["segments"]["required"] is True
    assert form["transition"]["options"] == ["cut", "dissolve"]
    assert form["burn_captions"]["options"] == ["yes", "no"]
    assert {"audio", "mix_bundle", "captions", "note"} <= set(form)
    body = " ".join(text[end:].split())
    assert 'kind="work"' in body
    assert "never trims, reorders, retimes" in body


@needs_ffmpeg
def test_cut_join_lays_the_wav_and_drops_segment_sound(tmp_path):
    a = video(tmp_path / "a.mp4", 1.0, sound=True)
    b = video(tmp_path / "b.mp4", 1.5, source="smptebars")
    track = wav(tmp_path / "track.wav", 2.5)
    code, result, out = build(tmp_path, "--segments", f"{a},{b}", "--audio", str(track))
    assert code == 0, result
    assert result["status"] == "PASS" and result["media_generation"] == 0
    assert result["total_seconds"] == 2.5
    assert result["probe"]["audio_streams"] == 1
    assert result["checks"]["true_peak_below_0"]
    assert result["segment_audio_dropped"] == [1]
    assert (out / "master_demo.mp4").is_file() and (out / "sheet.png").is_file()
    assert [j["at"] for j in result["review"]["joins"]] == [1.0]
    assert result["captions_srt"] is None


@needs_ffmpeg
def test_dissolve_shortens_the_picture_and_the_audio_must_match(tmp_path):
    a = video(tmp_path / "a.mp4", 2.0)
    b = video(tmp_path / "b.mp4", 2.0, source="smptebars")
    long_track = wav(tmp_path / "long.wav", 4.0)
    code, result, out = build(tmp_path, "--segments", f"{a},{b}", "--transition", "dissolve",
                              "--transition-seconds", "0.5", "--audio", str(long_track))
    assert code == 1 and result is None and not out.exists()
    track = wav(tmp_path / "track.wav", 3.5)
    code, result, out = build(tmp_path, "--segments", f"{a},{b}", "--transition", "dissolve",
                              "--transition-seconds", "0.5", "--audio", str(track))
    assert code == 0, result
    assert result["total_seconds"] == 3.5
    assert [j["at"] for j in result["review"]["joins"]] == [1.75]


@needs_ffmpeg
def test_mismatches_are_dependency_requests_not_silent_fixes(tmp_path, capsys):
    a = video(tmp_path / "a.mp4", 1.0)
    wide = video(tmp_path / "wide.mp4", 1.0, size="640x360")
    code, _, out = build(tmp_path, "--segments", f"{a},{wide}")
    assert code == 1 and not out.exists()
    assert "edit-clip" in capsys.readouterr().err
    track = wav(tmp_path / "short.wav", 0.5)
    code, _, _ = build(tmp_path, "--segments", str(a), "--audio", str(track))
    assert code == 1
    assert "edit-music" in capsys.readouterr().err
    code, _, _ = build(tmp_path, "--segments", str(a), "--transition", "dissolve")
    assert code == 1
    (tmp_path / "out").mkdir()
    code, _, _ = build(tmp_path, "--segments", str(a))
    assert code == 1
    assert "new directory" in capsys.readouterr().err


@needs_ffmpeg
def test_captions_are_checked_and_attached_as_srt(tmp_path, capsys):
    a = video(tmp_path / "a.mp4", 2.0)
    srt = tmp_path / "c.srt"
    srt.write_text("1\n00:00:00,100 --> 00:00:01,000\nこんにちは\n\n2\n00:00:01,200 --> 00:00:01,900\nSecond\n",
                   encoding="utf-8")
    code, result, out = build(tmp_path, "--segments", str(a), "--captions", str(srt), "--burn-captions", "no")
    assert code == 0, result
    assert result["inputs"]["captions"]["burned"] is False
    assert "こんにちは" in (out / "master_demo.srt").read_text(encoding="utf-8")
    late = tmp_path / "late.srt"
    late.write_text("1\n00:00:01,000 --> 00:00:05,000\nToo long\n", encoding="utf-8")
    shutil.rmtree(out)
    code, _, _ = build(tmp_path, "--segments", str(a), "--captions", str(late), "--burn-captions", "no")
    assert code == 1 and "ends after the master" in capsys.readouterr().err
    overlap = tmp_path / "overlap.srt"
    overlap.write_text("1\n00:00:00,000 --> 00:00:01,000\nA\n\n2\n00:00:00,500 --> 00:00:01,500\nB\n", encoding="utf-8")
    code, _, _ = build(tmp_path, "--segments", str(a), "--captions", str(overlap), "--burn-captions", "no")
    assert code == 1 and "overlaps" in capsys.readouterr().err


@needs_ffmpeg
def test_mix_bundle_supplies_audio_and_default_captions(mix_job, tmp_path):
    a = video(tmp_path / "a.mp4", 3.0)
    b = video(tmp_path / "b.mp4", 3.0, source="smptebars")
    code, result, out = build(tmp_path, "--segments", f"{a},{b}", "--mix-bundle", str(mix_job.bundle),
                              "--burn-captions", "no")
    assert code == 0, result
    assert result["checks"]["mix_audio_within_receipt"]
    assert result["inputs"]["captions"]["path"].endswith("captions.json")
    assert (out / "master_demo.srt").is_file()


@pytest.mark.skipif(os.environ.get("MASTER_RENDER_SMOKE") != "1" or not shutil.which("hyperframes"),
                    reason="burned-in caption render is opt-in (MASTER_RENDER_SMOKE=1) and needs hyperframes")
def test_burned_captions_render_through_hyperframes(tmp_path):
    a = video(tmp_path / "a.mp4", 2.0, size="720x1280")
    srt = tmp_path / "c.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n字幕の焼き込みテスト\n", encoding="utf-8")
    code, result, out = build(tmp_path, "--segments", str(a), "--captions", str(srt))
    assert code == 0, result
    assert result["inputs"]["captions"]["burned"] is True
    assert result["probe"]["width"] == 720 and result["probe"]["height"] == 1280


def test_creator_routes_finishing_to_create_master_first():
    table = (CREATOR / "references/capabilities.md").read_text(encoding="utf-8")
    assert "| video-creator: create-master |" in table
    rules = " ".join(table.split())
    assert "selects create-master before `creator-media-assembly`" in rules
    for phase in ("plan-creator", "build-creator", "qa-creator"):
        assert (CREATOR / phase / "references/video-creator/master.md").is_file()
        assert "[master](references/video-creator/master.md)" in (CREATOR / phase / "SKILL.md").read_text()
    prompt = yaml.safe_load((CREATOR.parents[1] / "config.yaml").read_text())["agent"]["system_prompt"]
    assert "create-master and create-story" in prompt
    legacy = (CREATOR.parents[0] / "technic/creator-media-assembly/SKILL.md").read_text(encoding="utf-8")
    assert "video-creator's `create-master`" in " ".join(legacy.split())
    mv_build = (CREATOR / "build-creator/references/video-creator/music-video.md").read_text(encoding="utf-8")
    assert "[create-master](master.md)" in mv_build
