"""Tests for the official path of the `source-icon` leaf: front matter contract
and the `brand-check.py` render/provenance commands
(profiles/image-creator/.../source/icon)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "image-creator" / "skills" / "image-creator-pipeline"
LEAF = PIPELINE / "source" / "icon"
SKILL = LEAF / "SKILL.md"
SCRIPT = LEAF / "scripts" / "brand-check.py"

_spec = importlib.util.spec_from_file_location(
    "validate_profile_skills", HERMES_ROOT / "scripts" / "validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VALIDATOR
_spec.loader.exec_module(VALIDATOR)

needs_render = pytest.mark.skipif(
    shutil.which("rsvg-convert") is None or shutil.which("magick") is None,
    reason="rsvg-convert and magick are required",
)

CIRCLE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
          '<circle cx="32" cy="32" r="24" fill="{fill}"/></svg>')


def brand_check(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
    )


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_front_matter_closes_early_and_validates():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text[:3800]
    errors: list[str] = []
    VALIDATOR.validate_hands_leaves(PIPELINE, "image-creator", errors)
    assert [e for e in errors if "icon" in e] == []
    meta = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(SKILL))
    assert meta["cost"] == "free" and meta["hands"] == "image-creator"
    form = meta["form"]
    assert {"official", "vendor", "variant", "backdrop"} <= set(form)
    assert {"icon", "color", "size", "background"} <= set(form)
    assert [k for k, v in form.items() if v["required"]] == []
    form_errors: list[str] = []
    VALIDATOR.validate_hands_form(form, LEAF, SKILL, form_errors)
    assert form_errors == []
    body = text.split("\n---\n", 1)[1]
    assert re.findall(r"^<(/?\w+)>$", body, re.M) == [
        "Procedure", "/Procedure", "QA", "/QA", "Report", "/Report"]


def test_procedure_keeps_iconify_path_and_adds_official_path():
    body = SKILL.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    procedure = body.split("<Procedure>", 1)[1].split("</Procedure>", 1)[0]
    assert "**Iconify path**" in procedure and "icon-fetch.sh --icon" in procedure
    assert "**Official path**" in procedure
    assert "never redraw" in procedure
    assert "brand-check.py render" in procedure and "brand-check.py provenance" in procedure
    for reference in ("vendor-findings.md", "fetching-gated-brand-pages.md"):
        assert reference in procedure
        assert (LEAF / "references" / reference).is_file()


@needs_render
def test_render_passes_black_and_white_marks(tmp_path):
    black = write(tmp_path, "black.svg", CIRCLE.format(fill="#000000"))
    white = write(tmp_path, "white.svg", CIRCLE.format(fill="#ffffff"))
    result = brand_check("render", str(black), str(white))
    assert result.returncode == 0, result.stdout + result.stderr
    lines = [l for l in result.stdout.splitlines() if l.startswith("RESULT:")]
    assert len(lines) == 2 and all(l.startswith("RESULT: PASS") for l in lines)
    assert all("viewbox=0 0 64 64" in l for l in lines)


@needs_render
def test_render_fails_blank_svg(tmp_path):
    empty = write(tmp_path, "empty.svg",
                  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"></svg>')
    result = brand_check("render", str(empty))
    assert result.returncode == 1
    assert "RESULT: FAIL" in result.stdout and "renders blank" in result.stdout


@needs_render
def test_render_fails_without_viewbox(tmp_path):
    bare = write(tmp_path, "bare.svg",
                 '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
                 '<circle cx="32" cy="32" r="24"/></svg>')
    result = brand_check("render", str(bare))
    assert result.returncode == 1
    assert "RESULT: FAIL" in result.stdout and "no viewBox" in result.stdout


def kit(tmp_path: Path) -> tuple[Path, Path, Path]:
    mark = CIRCLE.format(fill="#000000").encode()
    archive = tmp_path / "kit.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("logos/mark-dark.svg", mark)
    delivered = tmp_path / "mark-dark.svg"
    delivered.write_bytes(mark)
    terms = write(tmp_path, "terms.txt", "Nominative use only; do not alter the mark.\n")
    return archive, delivered, terms


def provenance(archive: Path, delivered: Path, terms: Path, out: Path):
    return brand_check(
        "provenance", "--file", str(delivered), "--source-url", "https://example.com/brand",
        "--archive", str(archive), "--member", "logos/mark-dark.svg",
        "--terms", str(terms), "--out", str(out),
    )


def test_provenance_passes_identical_member(tmp_path):
    archive, delivered, terms = kit(tmp_path)
    out = tmp_path / "provenance.json"
    result = provenance(archive, delivered, terms, out)
    assert result.returncode == 0, result.stderr
    assert "RESULT: PASS" in result.stdout and "identical_to_member=true" in result.stdout
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["identical_to_member"] is True and record["archive_test"] == "ok"
    assert record["modified"] is False and record["member"] == "logos/mark-dark.svg"
    assert re.fullmatch(r"[0-9a-f]{64}", record["file_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", record["archive_sha256"])
    assert record["terms"].startswith("Nominative use only")


def test_provenance_fails_modified_file(tmp_path):
    archive, delivered, terms = kit(tmp_path)
    delivered.write_bytes(CIRCLE.format(fill="#ff0000").encode())
    out = tmp_path / "provenance.json"
    result = provenance(archive, delivered, terms, out)
    assert result.returncode != 0 and "modified" in result.stderr
    assert not out.exists()


def test_provenance_refuses_existing_out(tmp_path):
    archive, delivered, terms = kit(tmp_path)
    out = write(tmp_path, "provenance.json", "{}\n")
    result = provenance(archive, delivered, terms, out)
    assert result.returncode != 0 and "never overwritten" in result.stderr
    assert out.read_text(encoding="utf-8") == "{}\n"
