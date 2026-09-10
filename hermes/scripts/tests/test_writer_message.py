"""Message text contracts preserve intent without implying sending or UI work."""

from pathlib import Path

import pytest
import yaml


PIPELINE = Path(__file__).resolve().parents[2] / "profiles/writer/skills/writer-pipeline"
CHANNELS = ["email", "chat", "notification", "ui", "error"]
CRAFT = {
    "email": ("subject", "sender stance", "requested reply", "refusal"),
    "chat": ("contextual unit", "referents", "greeting"),
    "notification": ("state", "impact", "action", "task-essential", "response"),
    "ui": ("action", "object", "helper", "before", "rendered fit", "implement controls"),
    "error": (
        "known result", "unknown outcome", "field", "empty", "invalid",
        "retry safety", "blame",
    ),
}


def content(path):
    return " ".join(path.read_text().split())


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_message_form_and_channel_references(verb):
    root = PIPELINE / verb / "message"
    text = (root / "SKILL.md").read_text()
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["name"] == f"{verb}-message"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing"
    assert meta["output"]
    assert "hands" not in meta and "cost" not in meta
    form = meta["form"]
    assert form["channel"]["options"] == CHANNELS
    assert form["channel"]["other"] is True
    assert form["channel"]["references"] == "references/*.md"
    assert form["channel"]["required"] is (verb == "write")
    assert form["humanizer"]["options"] == ["yes", "no"]
    assert "explicit" in form["humanizer"]["label"]
    expected = {"recipient", "purpose", "channel"} if verb == "write" else {
        "source", "changes" if verb == "edit" else "question"
    }
    assert {key for key, field in form.items() if field["required"]} == expected
    assert all(isinstance(field["required"], bool) for field in form.values())
    assert "note" in form
    for channel in CHANNELS:
        reference = root / "references" / f"{channel}.md"
        assert reference.is_file()
        assert f"](references/{channel}.md)" in text
        assert "QA:" in reference.read_text()
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text
    assert "scripts/lint.py" not in text


def test_message_routing_does_not_capture_other_capabilities():
    kernel = content(PIPELINE / "SKILL.md")
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/message/SKILL.md)" in kernel
    assert "Social posts and promotional mail are separate subjects" in kernel
    assert "not contact resolution, system diagnosis, interface implementation or sending" in kernel


def test_write_preserves_stance_and_protects_reports():
    text = content(PIPELINE / "write/message/SKILL.md")
    assert "Politeness or warmth must not add an apology" in text
    assert "both the body and report" in text
    assert "Do not invent HTML comment hiding" in text
    assert "unseen images cannot be claimed as inspected" in text


def test_edit_does_not_change_outcome_or_untouched_fields():
    text = content(PIPELINE / "edit/message/SKILL.md")
    assert '"result unknown" into "not sent"' in text
    assert "including untouched fields" in text
    assert "do not overwrite the source without authorization" in text.lower()
    assert "A changed approved draft needs renewed approval" in text


def test_analysis_reports_readings_not_motives_or_replies():
    text = content(PIPELINE / "analyze/message/SKILL.md")
    assert "do not require a full writing brief" in text.lower()
    assert "Do not claim to know how the recipient feels" in text
    assert "Do not compose an unsolicited reply" in text
    assert "it needs no new greeting" in text


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_error_guidance_does_not_invent_recovery_or_safety(verb):
    text = content(PIPELINE / verb / "message/references/error.md").lower()
    assert "retry" in text and "evidence" in text
    assert "result" in text or "non-delivery" in text
    assert "secret" in text or "sensitive" in text


@pytest.mark.parametrize("channel", CHANNELS)
def test_channel_references_are_operation_specific(channel):
    texts = {
        (PIPELINE / verb / f"message/references/{channel}.md").read_text()
        for verb in ("write", "edit", "analyze")
    }
    assert len(texts) == 3


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
@pytest.mark.parametrize("channel", CHANNELS)
def test_message_craft_has_grounded_examples_and_operation_boundaries(verb, channel):
    reference = PIPELINE / verb / f"message/references/{channel}.md"
    raw = reference.read_text()
    text = " ".join(raw.split()).lower()
    assert 40 <= len(raw.splitlines()) <= 90
    assert raw.count("\nQA:") == 1
    for marker in (
        "## Craft decisions", "## Worked example", "Fictional material:",
        "Why:", "Retain:", "Counterexample:", "QA evidence:",
    ):
        assert marker in raw
    for concept in CRAFT[channel]:
        assert concept in text
    for source in ("writing-constitution", "revision-guide"):
        assert (
            "https://github.com/coji/natural-japanese/blob/v1.5.0/"
            f"skills/natural-japanese/references/{source}.md"
        ) in text
    assert "local adaptation" in text and "examples" in text
    assert "not upstream" in text or "no upstream" in text
    example = raw.split("## Worked example", 1)[1].split("Retain:", 1)[0]
    output = {"write": "Draft", "edit": "Revision", "analyze": "Finding:"}[verb]
    assert example.index("Fictional material:") < example.index(output)
    if verb == "edit":
        for protection in ("authorized changes", "protect intent", "no-op"):
            assert protection in text
    if verb == "analyze":
        for protection in ("quote", "evidence", "mismatch", "consequence", "replacement"):
            assert protection in text
        assert "Revision:" not in example and "Draft:" not in example
    assert "eval-rubric.md" not in text and "scripts/lint.py" not in text
