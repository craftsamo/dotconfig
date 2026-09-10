"""Core contract checks, not an automated judge of Japanese naturalness."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "agents/curated/japanese-writing"


def test_core_does_not_route_to_legacy_workflows():
    text = (SKILL / "SKILL.md").read_text()
    assert "name: japanese-writing\n" in text
    assert "references/" not in text
    assert "scripts/" not in text
    assert not re.search(r"<(Workflow|Verification|Layers|Patterns|Router)>", text)


def test_five_selected_defaults_remain():
    text = (SKILL / "SKILL.md").read_text()
    headings = re.findall(r"^### (.+)$", text, re.MULTILINE)
    assert headings == ["和欧混植", "かな書き", "送り仮名", "ダッシュ", "「〜化」「〜的」"]


def test_core_is_the_only_runtime_resource():
    assert sorted(path.relative_to(SKILL).as_posix() for path in SKILL.rglob("*.md")) == [
        "SKILL.md"
    ]
    assert not list(SKILL.rglob("*.py"))


def test_host_router_only_loads_core():
    text = (ROOT / "opencode/AGENTS.md").read_text()
    route = text.split("<JapaneseWritingSkills>", 1)[1].split("</JapaneseWritingSkills>", 1)[0]
    assert "japanese-writing" in route
    assert "references/" not in route
    assert "scripts/" not in route


def test_writer_does_not_call_retired_language_resources():
    pipeline = ROOT / "hermes/profiles/writer/skills/writer-pipeline"
    for path in pipeline.rglob("*.md"):
        text = path.read_text()
        assert "japanese-writing/scripts/" not in text, path
        assert "references/inspection/" not in text, path
        assert "references/tech-prose.md" not in text, path
        assert "references/prose-rhythm.md" not in text, path
        assert "references/business/" not in text, path
