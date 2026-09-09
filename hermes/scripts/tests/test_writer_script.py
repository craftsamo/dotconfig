"""Script text and analysis never masquerade as performed production evidence."""

from pathlib import Path

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/writer/skills/writer-pipeline"
FORMATS = ["narration", "comic", "storyboard", "screenplay", "slide-script"]


def content(path):
    return " ".join(path.read_text().split())


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_script_form_and_local_references(verb):
    root = PIPELINE / verb / "script"
    text = (root / "SKILL.md").read_text()
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["name"] == f"{verb}-script"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing" and meta["output"]
    assert "hands" not in meta and "cost" not in meta
    form = meta["form"]
    assert form["format"]["options"] == FORMATS
    assert form["format"]["other"] is True
    assert form["format"]["references"] == "references/*.md"
    assert form["format"]["required"] is (verb == "write")
    assert form["humanizer"]["options"] == ["yes", "no"]
    assert "explicit" in form["humanizer"]["label"]
    required = {"audience", "purpose", "format"} if verb == "write" else {
        "source", "changes" if verb == "edit" else "question"
    }
    assert {key for key, field in form.items() if field["required"]} == required
    assert all(isinstance(field["required"], bool) for field in form.values())
    assert {"note", "producer_format", "unit_limits"} <= form.keys()
    for fmt in FORMATS:
        reference = root / "references" / f"{fmt}.md"
        assert reference.is_file()
        assert f"](references/{fmt}.md)" in text
        assert "QA:" in reference.read_text()
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text
    assert "scripts/lint.py" not in text


def test_kernel_routes_scripts_without_legacy_inspection():
    kernel = content(PIPELINE / "SKILL.md")
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/script/SKILL.md)" in kernel
    assert "Do not run the legacy script/inspection workflow" in kernel
    assert "An analysis is a report, not a new script" in kernel
    assert "Production scripts retain their legacy" not in kernel
    assert (PIPELINE / "references/consultation.md").is_file()


def test_consultation_does_not_reintroduce_legacy_script_limits():
    advice = content(PIPELINE / "references/consultation.md")
    assert "use the corresponding edit/analyze leaf" in advice
    assert "return to the kernel's operation selection" in advice
    assert "not an actual producer limit or measured timing" in advice
    assert "Do not execute its drafting procedure" in advice


def test_write_separates_spoken_text_and_exports():
    text = content(PIPELINE / "write/script/SKILL.md")
    assert "the input file contains only intended words" in text
    assert "no heading, speaker label, Markdown fence, stage direction or QA receipt" in text
    assert "separate same-stem `.production.md`" in text
    assert "checking equality with the master" in text
    assert "A small plain narration needs no forced scene table" in text
    assert "Fictional invention belongs only inside the agreed story freedom" in text


def test_edit_preserves_ids_and_invalidates_stale_evidence():
    text = content(PIPELINE / "edit/script/SKILL.md")
    assert "never speak that marker or compact/reuse the IDs" in text
    assert "old-to-new mapping accepted by the requester and consumer" in text
    assert "including untouched units" in text
    assert "no stale export may be delivered" in text
    assert "A changed approved script needs renewed approval" in text
    assert "dependent renders, audio and timing evidence are not automatically valid" in text
    assert "without overwriting the source unless authorized" in text


def test_analysis_is_a_report_not_new_production():
    text = content(PIPELINE / "analyze/script/SKILL.md")
    assert "does not require a complete writing brief" in text
    assert "Description need not invent faults" in text
    assert "This report needs no new scenes, dialogue, speaker roster, raw speech file" in text
    assert "Original scripts, IDs and exports remain unchanged" in text
    assert "Do not create media or mutate timing files" in text


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_narration_does_not_treat_estimated_timing_as_performance(verb):
    text = content(PIPELINE / verb / "script/references/narration.md").lower()
    assert "words" in text and "notes" in text
    assert "timing" in text or "duration" in text
    assert "synthesis" in text or "production" in text
    assert "600" not in text  # A consumer limit is not a universal script rule.


def test_creator_accepts_raw_approved_words_not_the_analysis():
    path = HERMES / "profiles/creator/skills/creator-pipeline/references/plan.md"
    text = content(path)
    assert "`write-script` or `edit-script`" in text
    assert "an `analyze-script` report is not a speech part" in text
    assert "approved raw spoken-text file, not a structured master" in text
    assert "changes return to the requester for Writer, not local rewriting" in text
    assert "A request for sectioning is not an automatic take grant" in text


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_references_are_operation_specific(fmt):
    texts = {
        (PIPELINE / verb / f"script/references/{fmt}.md").read_text()
        for verb in ("write", "edit", "analyze")
    }
    assert len(texts) == 3
