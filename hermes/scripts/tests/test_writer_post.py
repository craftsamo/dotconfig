"""Structural safeguards for the post family; behavioral trials remain separate."""

from pathlib import Path
import re

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/writer/skills/writer-pipeline"


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_post_form_survives_discovery_window(verb):
    path = PIPELINE / verb / "post/SKILL.md"
    text = path.read_text()
    header = text.split("---", 2)[1]
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(header)
    assert data["name"] == f"{verb}-post"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing"
    assert meta["output"]
    assert meta["form"]["platform"]["options"] == ["x", "instagram"]
    assert meta["form"]["humanizer"]["options"] == ["yes", "no"]
    for platform in ("x", "instagram"):
        assert (path.parent / "references" / f"{platform}.md").is_file()
    assert not re.search(r"\buv run\b|scripts/lint\.py|scripts/outline\.py", text)
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text


def test_post_family_is_routed_without_retiring_other_families():
    kernel = (PIPELINE / "SKILL.md").read_text()
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/post/SKILL.md)" in kernel
    assert (PIPELINE / "references/legacy.md").is_file()
    assert "compatibility material for explicit legacy callers" in kernel


def test_post_policy_does_not_expand_tools_or_publish():
    config = yaml.safe_load((HERMES / "profiles/writer/config.yaml").read_text())
    assert "terminal" not in config["toolsets"]
    assert "a2a" not in config["toolsets"]
    source = (PIPELINE / "analyze/post/SKILL.md").read_text()
    assert "not revised post" in source
    assert "not as a" in source and "new post" in source
    assert "Never change the" in source and "source" in source


def test_marketer_does_not_bypass_writer_acceptance():
    root = HERMES / "profiles/marketer/skills/marketer-pipeline"
    produce = " ".join((root / "references/produce.md").read_text().split())
    assert "not writing-QA-gated" in produce
    assert "before it can enter a message unit or approval relay" in produce
    assert "No local shortening" in produce
    assert "Instagram remains draft-only" in produce
