"""Tests for the `create-pixel-animation` leaf: front matter contract, the
`cels.py` draw/sheet commands and an end-to-end encode + verify of a tiny loop
(profiles/video-creator/.../create/pixel-animation)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
LEAF = PIPELINE / "create" / "pixel-animation"
SKILL = LEAF / "SKILL.md"
CELS = LEAF / "scripts" / "cels.py"
ENCODE = LEAF / "scripts" / "encode-pixel-video.sh"
VERIFY = LEAF / "scripts" / "verify-pixel-video.py"

_spec = importlib.util.spec_from_file_location(
    "validate_profile_skills", HERMES_ROOT / "scripts" / "validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VALIDATOR
_spec.loader.exec_module(VALIDATOR)

UV = shutil.which("uv")
needs_uv = pytest.mark.skipif(UV is None, reason="uv is required")
needs_video = pytest.mark.skipif(
    UV is None or shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="uv, ffmpeg and ffprobe are required",
)

PALETTE = {"a": "#ff0000", "b": "#0000ff", "c": "#00ff00"}
FRAMES = [
    ["a...", "....", "....", "...b"],
    [".a..", "....", "....", "..b."],
    ["..a.", "....", "....", ".b.."],
]


def write_maps(root: Path, frames=FRAMES, palettes=None) -> Path:
    maps = root / "maps"
    maps.mkdir(exist_ok=True)
    for i, rows in enumerate(frames, start=1):
        palette = palettes[i - 1] if palettes else PALETTE
        (maps / f"frame_{i:04d}.json").write_text(
            json.dumps({"palette": palette, "rows": rows}), encoding="utf-8"
        )
    return maps


def cels(*args: str):
    return subprocess.run(
        [UV, "run", "--no-project", "--with", "Pillow", "python", str(CELS), *args],
        capture_output=True, text=True,
    )


def verify(video: Path, mode: str, *extra: str):
    return subprocess.run(
        [UV, "run", "--no-project", "--with", "Pillow", "--with", "numpy", "python", str(VERIFY),
         str(video), mode, "--grid", "4x4", "--scale", "4", "--palette-max", "4",
         "--effective-fps", "10", "--container-fps", "30", "--loop", *extra],
        capture_output=True, text=True,
    )


def test_front_matter_closes_early_and_validates():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text[:3800]
    errors: list[str] = []
    VALIDATOR.validate_hands_leaves(PIPELINE, "video-creator", errors)
    assert [e for e in errors if "pixel" in e] == []
    meta = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(SKILL))
    assert meta["cost"] == "free" and meta["hands"] == "video-creator"
    form = meta["form"]
    assert {"what_for", "motion", "grid", "source", "subject", "frames", "effective_fps",
            "duration", "loop", "scale", "gif", "note"} == set(form)
    assert [k for k, v in form.items() if v["required"]] == ["what_for", "motion", "grid"]
    assert form["motion"]["type"] == "text" and form["source"]["type"] == "file"
    assert "options" not in form["loop"] and "options" not in form["gif"]
    form_errors: list[str] = []
    VALIDATOR.validate_hands_form(form, LEAF, SKILL, form_errors)
    assert form_errors == []
    body = text.split("\n---\n", 1)[1]
    assert re.findall(r"^<(/?\w+)>$", body, re.M) == [
        "Procedure", "/Procedure", "QA", "/QA", "Report", "/Report"]


@needs_uv
def test_draw_renders_numbered_frames(tmp_path):
    from PIL import Image

    maps = write_maps(tmp_path)
    result = cels("draw", "--maps", str(maps), "--out", str(tmp_path / "frames"))
    assert result.returncode == 0, result.stderr
    assert "RESULT: drew frames=3 native=4x4" in result.stdout
    names = sorted(p.name for p in (tmp_path / "frames").iterdir())
    assert names == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    image = Image.open(tmp_path / "frames" / "frame_0002.png")
    assert image.size == (4, 4) and image.getpixel((1, 0)) == (255, 0, 0)
    assert image.getpixel((3, 0)) == (0, 0, 0)


@needs_uv
def test_draw_refuses_mixed_palette_size_and_existing_out(tmp_path):
    other = {"a": "#ff0000", "b": "#0000ff", "c": "#ffffff"}
    maps = write_maps(tmp_path, palettes=[PALETTE, PALETTE, other])
    result = cels("draw", "--maps", str(maps), "--out", str(tmp_path / "f1"))
    assert result.returncode != 0 and "palette differs" in result.stderr
    assert not (tmp_path / "f1").exists()

    shutil.rmtree(maps)
    maps = write_maps(tmp_path, frames=[FRAMES[0], FRAMES[1], ["a..", "...", "...", "..b"]])
    result = cels("draw", "--maps", str(maps), "--out", str(tmp_path / "f2"))
    assert result.returncode != 0 and "differs from 4x4" in result.stderr

    shutil.rmtree(maps)
    maps = write_maps(tmp_path)
    (tmp_path / "taken").mkdir()
    result = cels("draw", "--maps", str(maps), "--out", str(tmp_path / "taken"))
    assert result.returncode != 0 and "already exists" in result.stderr


@needs_uv
@pytest.mark.skipif(shutil.which("magick") is None, reason="magick is required")
def test_sheet_builds_png_and_refuses_existing_out(tmp_path):
    maps = write_maps(tmp_path)
    assert cels("draw", "--maps", str(maps), "--out", str(tmp_path / "frames")).returncode == 0
    sheet = tmp_path / "sheet.png"
    result = cels("sheet", "--frames", str(tmp_path / "frames"), "--out", str(sheet),
                  "--scale", "2", "--columns", "2")
    assert result.returncode == 0, result.stderr
    assert sheet.is_file()
    again = cels("sheet", "--frames", str(tmp_path / "frames"), "--out", str(sheet))
    assert again.returncode != 0 and "already exists" in again.stderr


def encode(tmp_path: Path):
    maps = write_maps(tmp_path)
    assert cels("draw", "--maps", str(maps), "--out", str(tmp_path / "frames")).returncode == 0
    master, compat = tmp_path / "m_master.mp4", tmp_path / "m.mp4"
    result = subprocess.run(
        [str(ENCODE), str(tmp_path / "frames" / "frame_%04d.png"), str(master),
         "--scale", "4", "--effective-fps", "10", "--container-fps", "30",
         "--compat", str(compat)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return master, compat


@needs_video
def test_encode_then_verify_master_and_compat(tmp_path):
    master, compat = encode(tmp_path)
    pattern = str(tmp_path / "frames" / "frame_*.png")
    ok = verify(master, "--master", "--source-pattern", pattern)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "source identity: 3/3 exact" in ok.stdout and "PASS" in ok.stdout
    ok = verify(compat, "--compat")
    assert ok.returncode == 0, ok.stdout + ok.stderr


@needs_video
def test_verify_fails_on_interpolated_frame(tmp_path):
    from PIL import Image, ImageFilter

    master, _ = encode(tmp_path)
    frames = tmp_path / "frames"
    blurred = Image.open(frames / "frame_0002.png").resize((16, 16), Image.Resampling.BILINEAR)
    blurred = blurred.filter(ImageFilter.GaussianBlur(3)).resize((4, 4), Image.Resampling.BILINEAR)
    blurred.save(frames / "frame_0002.png")
    bad = tmp_path / "bad_master.mp4"
    result = subprocess.run(
        [str(ENCODE), str(frames / "frame_%04d.png"), str(bad), "--scale", "4",
         "--effective-fps", "10", "--container-fps", "30"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    failed = verify(bad, "--master", "--source-pattern", str(tmp_path / "frames" / "frame_*.png"))
    assert failed.returncode != 0
    assert "palette max exceeded" in failed.stdout
