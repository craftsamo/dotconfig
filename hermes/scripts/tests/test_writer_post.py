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


def test_post_family_is_routed_without_generic_fallback():
    kernel = (PIPELINE / "SKILL.md").read_text()
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/post/SKILL.md)" in kernel
    assert (PIPELINE / "consult-writer/SKILL.md").is_file()
    assert "If no installed leaf fits, return the unsupported scope" in kernel


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
    produce = " ".join((root / "references/build/parts.md").read_text().split())
    assert "not writing-QA-gated" in produce
    assert "before it can enter a message unit or approval relay" in produce
    assert "No local shortening" in produce
    assert "Missing shared QA blocks acceptance" in produce
    assert "supported custom destination is not evidence" in produce


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
@pytest.mark.parametrize("platform,anchors", [
    ("x", ("P10", "P20", "West shuttle", "trial", "standalone", "subject", "qualifier")),
    ("instagram", ("C10", "I10", "Ground floor only", "alt", "fictional inspection record")),
])
def test_post_reference_craft_coverage(verb, platform, anchors):
    path = PIPELINE / verb / f"post/references/{platform}.md"
    text = path.read_text()
    flat = " ".join(text.split())
    assert len(text.splitlines()) <= 90
    for marker in ("## Craft Decisions", "MATERIAL-COMPLETE", "Rationale:",
                   "Retain:", "Counterexample:", "QA:", "LOCAL adaptation"):
        assert marker in text, (path, marker)
    example = text.split("## Worked Example", 1)[1].split("LOCAL adaptation", 1)[0]
    assert example.index("Supplied material:") < example.index("Creative-fiction allowance:")
    assert example.index("Creative-fiction allowance:") < example.index("```text")
    assert example.count("```text") == 1 and example.count("```") == 2
    assert "QA:" in example and "unverified" in example
    assert re.search(r"\bif\b", flat, re.IGNORECASE)
    for anchor in anchors:
        assert anchor.lower() in flat.lower(), (path, anchor)
    base = "https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/"
    for source in ("writing-constitution.md", "genre-notes.md", "revision-guide.md"):
        assert f"]({base}{source})" in text
    if platform == "x":
        assert "https://service-manual.ons.gov.uk/content/content-types/social-media" in text
    else:
        assert "https://service-manual.ons.gov.uk/content/content-types/social-media" in text
        assert "https://www.w3.org/WAI/tutorials/images/informative/" in text
        assert "communications.gov.uk" not in text
        assert "growth promise" in flat and "unseen" in flat
    if verb == "write":
        assert "Draft" in example
    elif verb == "edit":
        assert "Original" in example and "Revised" in example and "no-op" in text
        assert "protected" in example and "unchanged" in example
    else:
        for marker in ("Finding:", "Evidence:", "Consequence:", "unchanged"):
            assert marker in example, (path, marker)
        assert "without replacement" in flat
        assert "Revised" not in example


@pytest.mark.parametrize("platform", ["x", "instagram"])
def test_post_destination_tables_and_documentary_checks_survive(platform):
    text = (PIPELINE / "write/post/references" / f"{platform}.md").read_text()
    assert "Documentary check: 2026-09-08. No logged-in composer test was performed." in text
    assert "| Expression | Draft representation |" in text
    assert "Markdown" in text
    if platform == "x":
        assert "weighted character counting" in text
        assert "https://help.x.com/en/using-x/articles" in text
    else:
        assert "Universal clickability is unverified" in text
        assert "https://www.facebook.com/help/instagram/442418472487929" in text
