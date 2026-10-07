"""Tests for the `create-pixel-art` leaf: front matter contract and the
`pixel.py` draw/check commands (profiles/image-creator/.../create/pixel-art)."""

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
PIPELINE = HERMES_ROOT / "profiles" / "image-creator" / "skills" / "image-creator-pipeline"
LEAF = PIPELINE / "create" / "pixel-art"
SKILL = LEAF / "SKILL.md"
SCRIPT = LEAF / "scripts" / "pixel.py"

_spec = importlib.util.spec_from_file_location(
    "validate_profile_skills", HERMES_ROOT / "scripts" / "validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VALIDATOR
_spec.loader.exec_module(VALIDATOR)

UV = shutil.which("uv")
needs_uv = pytest.mark.skipif(UV is None, reason="uv is required")

MAP = {"palette": {"a": "#ff0000", "b": "#0000ff"}, "rows": ["..aa", ".abb", "abba", "...."]}


def pixel(*args: str):
    return subprocess.run(
        [UV, "run", "--no-project", "--with", "Pillow", "python", str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def write_map(tmp_path: Path, data=MAP) -> Path:
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def draw(tmp_path: Path, out: str = "out", data=MAP, scale: str = "4"):
    return pixel("draw", "--map", str(write_map(tmp_path, data)), "--out", str(tmp_path / out), "--scale", scale)


def check(tmp_path: Path, *extra: str, out: str = "out", native=None, preview=None, palette=None):
    base = tmp_path / out
    return pixel(
        "check", "--native", str(native or base / "native.png"),
        "--preview", str(preview or base / "preview.png"),
        "--palette", str(palette or base / "palette.json"), *extra,
    )


def test_front_matter_closes_early_and_validates():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text[:3800]
    errors: list[str] = []
    VALIDATOR.validate_hands_leaves(PIPELINE, "image-creator", errors)
    assert [e for e in errors if "pixel" in e] == []
    meta = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(SKILL))
    assert meta["cost"] == "free" and meta["hands"] == "image-creator"
    form = meta["form"]
    assert {"what_for", "mode", "grid", "source", "subject", "palette", "background",
            "preview_scale", "note"} == set(form)
    assert [k for k, v in form.items() if v["required"]] == ["what_for", "mode", "grid"]
    assert form["mode"]["options"] == ["reduce", "draw"]
    assert "options" not in form["palette"]
    form_errors: list[str] = []
    VALIDATOR.validate_hands_form(form, LEAF, SKILL, form_errors)
    assert form_errors == []
    body = text.split("\n---\n", 1)[1]
    assert re.findall(r"^<(/?\w+)>$", body, re.M) == [
        "Procedure", "/Procedure", "QA", "/QA", "Report", "/Report"]


@needs_uv
def test_draw_then_check_passes(tmp_path):
    result = draw(tmp_path)
    assert result.returncode == 0, result.stderr
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == ["native.png", "palette.json", "preview.png"]
    assert json.loads((out / "palette.json").read_text())["colors"] == ["#0000ff", "#ff0000"]
    ok = check(tmp_path, "--scale", "4", "--alpha", "transparent")
    assert ok.returncode == 0, ok.stderr
    line = [l for l in ok.stdout.splitlines() if l.startswith("RESULT:")]
    assert len(line) == 1 and "PASS native=4x4 preview=16x16" in line[0]
    assert "out_of_palette=0" in line[0] and "uniform_blocks=yes" in line[0]


@needs_uv
def test_check_fails_off_palette(tmp_path):
    assert draw(tmp_path).returncode == 0
    palette = tmp_path / "other.json"
    palette.write_text(json.dumps({"colors": ["#ff0000"]}), encoding="utf-8")
    result = check(tmp_path, palette=palette)
    assert result.returncode != 0 and "out_of_palette=1" in result.stdout


@needs_uv
def test_check_fails_non_integer_scale(tmp_path):
    from PIL import Image

    assert draw(tmp_path).returncode == 0
    odd = tmp_path / "odd.png"
    Image.open(tmp_path / "out" / "preview.png").resize((18, 18), Image.Resampling.NEAREST).save(odd)
    result = check(tmp_path, preview=odd)
    assert result.returncode != 0 and "integer multiple" in result.stderr
    wrong = check(tmp_path, "--scale", "8")
    assert wrong.returncode != 0 and "expected 8" in wrong.stderr


@needs_uv
def test_check_fails_blurred_preview(tmp_path):
    from PIL import Image

    assert draw(tmp_path).returncode == 0
    blurred = tmp_path / "blur.png"
    Image.open(tmp_path / "out" / "native.png").resize((16, 16), Image.Resampling.BILINEAR).save(blurred)
    result = check(tmp_path, preview=blurred)
    assert result.returncode != 0 and "not uniform" in result.stderr


@needs_uv
def test_check_fails_partial_alpha_and_opaque_ask(tmp_path):
    assert draw(tmp_path).returncode == 0
    result = check(tmp_path, "--alpha", "opaque")
    assert result.returncode != 0 and "opaque result was asked" in result.stderr


@needs_uv
def test_draw_refuses_ragged_rows(tmp_path):
    bad = {"palette": MAP["palette"], "rows": ["aa", "a"]}
    result = draw(tmp_path, data=bad)
    assert result.returncode != 0 and "ragged" in result.stderr
    assert not (tmp_path / "out").exists()


@needs_uv
def test_draw_refuses_unknown_keys(tmp_path):
    bad = {"palette": MAP["palette"], "rows": ["aaz", "aaa"]}
    result = draw(tmp_path, data=bad)
    assert result.returncode != 0 and "unknown cell keys" in result.stderr
    extra = dict(MAP, extra=1)
    assert draw(tmp_path, data=extra).returncode != 0


@needs_uv
def test_draw_refuses_existing_out(tmp_path):
    (tmp_path / "out").mkdir()
    result = draw(tmp_path)
    assert result.returncode != 0 and "already exists" in result.stderr
