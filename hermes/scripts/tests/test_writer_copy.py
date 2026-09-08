"""Copy contracts preserve commercial meaning without certifying publication."""

from pathlib import Path

import pytest
import yaml


PIPELINE = Path(__file__).resolve().parents[2] / "profiles/writer/skills/writer-pipeline"
MARKETER = PIPELINE.parents[2] / "marketer/skills/marketer-pipeline"
DESTINATIONS = ["landing-page", "email", "announcement"]


def content(path):
    return " ".join(path.read_text().split())


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_copy_forms_and_local_references(verb):
    root = PIPELINE / verb / "copy"
    text = (root / "SKILL.md").read_text()
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["name"] == f"{verb}-copy"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing" and meta["output"]
    assert "hands" not in meta and "cost" not in meta
    form = meta["form"]
    assert form["destination"]["options"] == DESTINATIONS
    assert form["destination"]["other"] is True
    assert form["destination"]["references"] == "references/*.md"
    assert form["destination"]["required"] is (verb == "write")
    assert form["humanizer"]["options"] == ["yes", "no"]
    assert "explicit" in form["humanizer"]["label"]
    expected = {"audience", "message", "destination"} if verb == "write" else {
        "source", "changes" if verb == "edit" else "question"
    }
    assert {key for key, field in form.items() if field["required"]} == expected
    assert all(isinstance(field["required"], bool) for field in form.values())
    assert "note" in form
    for destination in DESTINATIONS:
        reference = root / "references" / f"{destination}.md"
        assert reference.is_file()
        assert f"](references/{destination}.md)" in text
        assert "QA:" in reference.read_text()
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text
    assert "scripts/lint.py" not in text


def test_copy_routing_and_script_boundary():
    kernel = content(PIPELINE / "SKILL.md")
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/copy/SKILL.md)" in kernel
    assert "Existing marketing-copy briefs select this family" in kernel
    assert "Ordinary correspondence, social posts and factual release notes" in kernel
    assert "Production scripts retain their legacy route" in kernel
    assert (PIPELINE / "references/script.md").is_file()


def test_write_does_not_manufacture_proof_or_an_action():
    text = content(PIPELINE / "write/copy/SKILL.md")
    assert "do not force a CTA into every announcement" in text
    assert "Do not invent proof or silently weaken a mandatory promise" in text
    assert "Omit an optional proof slot when no evidence exists" in text
    assert "do not omit a mandatory condition" in text
    assert "not a universal guarantee" in text


def test_edit_preserves_protected_and_untouched_terms():
    text = content(PIPELINE / "edit/copy/SKILL.md")
    assert "including untouched fields" in text
    assert "both requested and supported" in text
    assert "If protected text conflicts with evidence, return that conflict" in text
    assert "A changed approved draft needs renewed approval" in text
    assert "Do not overwrite the source without authorization" in text


def test_analysis_is_not_new_copy_or_a_performance_verdict():
    text = content(PIPELINE / "analyze/copy/SKILL.md")
    assert "do not require a full writing brief" in text.lower()
    assert "Description need not find defects" in text
    assert "it needs no new headline" in text
    assert "Do not produce replacement copy" in text
    assert "No statistical quality/authorship scores" in text


def test_marketer_consumes_copy_without_bypassing_acceptance():
    produce = content(MARKETER / "references/produce.md")
    parts = content(MARKETER / "references/parts.md")
    for verb in ("write", "edit", "analyze"):
        assert f"`{verb}-copy`" in produce
    assert "Writer peer response still needs the requester's writing QA" in produce
    assert "Return wording changes to `edit-copy` via the requester" in parts
    assert "Do not shorten, strengthen, add urgency or run humanizer" in produce
    assert "An `analyze-copy` report is not publishable copy" in parts
    assert "including a custom copy destination" in produce
    assert "PASONA" not in produce
    config = yaml.safe_load((MARKETER.parents[1] / "config.yaml").read_text())
    prompt = config["agent"]["system_prompt"]
    assert "write-copy/edit-copy/analyze-copy" in prompt
    assert "never local claim removal" in prompt
    kernel = content(MARKETER / "SKILL.md")
    for verb in ("write", "edit", "analyze"):
        assert f"`{verb}-copy`" in kernel
    assert "Other unmigrated platform-post channels" in kernel
    assert "legacy copy craft" not in kernel


@pytest.mark.parametrize("destination", DESTINATIONS)
def test_references_are_operation_specific(destination):
    texts = {
        (PIPELINE / verb / f"copy/references/{destination}.md").read_text()
        for verb in ("write", "edit", "analyze")
    }
    assert len(texts) == 3
