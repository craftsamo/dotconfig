"""Tests for the `create-diagram` leaf: front matter contract and the
`diagram.py render` checks (profiles/image-creator/.../create/diagram)."""

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
LEAF = PIPELINE / "create" / "diagram"
SKILL = LEAF / "SKILL.md"
SCRIPT = LEAF / "scripts" / "diagram.py"

_spec = importlib.util.spec_from_file_location(
    "validate_profile_skills", HERMES_ROOT / "scripts" / "validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VALIDATOR
_spec.loader.exec_module(VALIDATOR)

HAVE_RENDER = shutil.which("agent-browser") is not None and shutil.which("magick") is not None

GOOD = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    "html,body{margin:0;background:#fff}</style></head><body>"
    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160" viewBox="0 0 320 160">'
    '<rect x="10" y="50" width="100" height="60" fill="#eef" stroke="#336"/>'
    '<text x="20" y="85" font-family="sans-serif" font-size="16">Client</text>'
    '<rect x="210" y="50" width="100" height="60" fill="#eef" stroke="#336"/>'
    '<text x="220" y="85" font-family="sans-serif" font-size="16"><tspan>API  Gateway</tspan></text>'
    '<line x1="110" y1="80" x2="210" y2="80" stroke="#336"/></svg></body></html>'
)
LABELS = ["Client", "API Gateway"]


def render(tmp_path: Path, html: str, labels=LABELS, out: str = "out", size: str = "320x160"):
    page, label_file = tmp_path / "d.html", tmp_path / "labels.json"
    page.write_text(html, encoding="utf-8")
    label_file.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--html", str(page), "--labels", str(label_file),
         "--size", size, "--out", str(tmp_path / out)],
        capture_output=True, text=True,
    )


def test_front_matter_closes_early_and_validates():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text[:3800]
    errors: list[str] = []
    VALIDATOR.validate_hands_leaves(PIPELINE, "image-creator", errors)
    assert [e for e in errors if "diagram" in e] == []
    meta = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(SKILL))
    assert meta["cost"] == "free" and meta["hands"] == "image-creator"
    form = meta["form"]
    assert {"what_for", "kind", "content", "size", "theme", "reference", "note"} == set(form)
    assert [k for k, v in form.items() if v["required"]] == ["what_for", "kind", "content"]
    form_errors: list[str] = []
    VALIDATOR.validate_hands_form(form, LEAF, SKILL, form_errors)
    assert form_errors == []
    assert not (LEAF / "references" / "kind").exists()
    assert not (LEAF / "references" / "themes").exists()
    body = text.split("\n---\n", 1)[1]
    assert re.findall(r"^<(\w+)>$", body, re.M) == ["Procedure", "QA", "Report"] or \
        re.findall(r"^<(/?\w+)>$", body, re.M) == ["Procedure", "/Procedure", "QA", "/QA", "Report", "/Report"]


def test_rejects_remote_url(tmp_path):
    html = GOOD.replace("<line", '<image href="https://example.com/a.png" width="5" height="5"/><line')
    result = render(tmp_path, html)
    assert result.returncode != 0 and "not self-contained" in result.stderr
    assert not (tmp_path / "out").exists()


def test_rejects_protocol_relative_and_css_url(tmp_path):
    result = render(tmp_path, GOOD.replace("</style>", "body{background:url(//cdn.example/x.png)}</style>"))
    assert result.returncode != 0 and "not self-contained" in result.stderr


def test_rejects_script(tmp_path):
    result = render(tmp_path, GOOD.replace("</body>", "<script>1</script></body>"))
    assert result.returncode != 0 and "<script>" in result.stderr


def test_rejects_stylesheet_link(tmp_path):
    result = render(tmp_path, GOOD.replace("</head>", '<link rel="stylesheet" href="a.css"></head>'))
    assert result.returncode != 0 and "stylesheet" in result.stderr


def test_rejects_missing_label(tmp_path):
    result = render(tmp_path, GOOD, labels=["Client", "Database"])
    assert result.returncode != 0 and "Database" in result.stderr


def test_rejects_existing_out(tmp_path):
    (tmp_path / "out").mkdir()
    result = render(tmp_path, GOOD)
    assert result.returncode != 0 and "already exists" in result.stderr


@pytest.mark.skipif(not HAVE_RENDER, reason="agent-browser and magick are required")
def test_renders_tiny_diagram(tmp_path):
    result = render(tmp_path, GOOD)
    assert result.returncode == 0, result.stderr
    line = [l for l in result.stdout.splitlines() if l.startswith("RESULT:")]
    assert len(line) == 1
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == ["diagram.png", "diagram@2x.png", "render.json", "sheet.png"]
    report = json.loads((out / "render.json").read_text(encoding="utf-8"))
    assert report["files"]["diagram.png"] == [320, 160]
    assert report["files"]["diagram@2x.png"] == [640, 320]
    assert report["files"]["sheet.png"][0] == 1200
    assert report["labels_ok"] and report["self_contained"] and report["stable"]
    again = render(tmp_path, GOOD, out="out2")
    assert again.returncode == 0, again.stderr
    assert (out / "diagram.png").read_bytes() == (tmp_path / "out2" / "diagram.png").read_bytes()
