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


def test_legacy_consumers_still_have_resources_during_migration():
    for relative in (
        "references/tech-prose.md", "references/prose-rhythm.md",
        "references/business/overview.md", "references/inspection/workflow.md",
        "scripts/lint.py", "scripts/outline.py", "scripts/terms.py",
    ):
        assert (SKILL / relative).is_file(), relative


def test_host_router_only_loads_core():
    text = (ROOT / "opencode/AGENTS.md").read_text()
    route = text.split("<JapaneseWritingSkills>", 1)[1].split("</JapaneseWritingSkills>", 1)[0]
    assert "japanese-writing" in route
    assert "references/" not in route
    assert "scripts/" not in route


def test_legacy_references_do_not_require_removed_core_sections():
    for relative in ("references/tech-prose.md", "references/business/overview.md"):
        text = (SKILL / relative).read_text()
        assert "SKILL.md の Verification" not in text
        assert "一文一行の規則" not in text
        assert "表記の既定値" in text
