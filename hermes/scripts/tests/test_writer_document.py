"""Document contracts: source fidelity is not runtime or rendering evidence."""

from pathlib import Path

import pytest
import yaml


PIPELINE = Path(__file__).resolve().parents[2] / "profiles/writer/skills/writer-pipeline"
FORMATS = [
    "readme", "guide", "reference", "report", "minutes", "proposal",
    "slides", "release-notes", "issue",
]


def content(path):
    return " ".join(path.read_text().split())


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_document_form_and_local_format_references(verb):
    root = PIPELINE / verb / "document"
    text = (root / "SKILL.md").read_text()
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["name"] == f"{verb}-document"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing"
    assert meta["output"]
    assert "cost" not in meta and "hands" not in meta
    form = meta["form"]
    assert form["format"]["options"] == FORMATS
    assert form["format"]["other"] is True
    assert form["format"]["references"] == "references/*.md"
    assert form["format"]["required"] is (verb == "write")
    assert form["humanizer"]["options"] == ["yes", "no"]
    assert "explicit" in form["humanizer"]["label"]
    assert all(isinstance(field["required"], bool) for field in form.values())
    assert "note" in form
    expected = {"purpose", "reader", "format"} if verb == "write" else {
        "source", "changes" if verb == "edit" else "question"
    }
    assert {key for key, field in form.items() if field["required"]} == expected
    for name in FORMATS:
        reference = root / "references" / f"{name}.md"
        assert reference.is_file()
        assert f"](references/{name}.md)" in text
        assert "QA:" in reference.read_text()
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text
    assert "scripts/lint.py" not in text


def test_document_kernel_routes_existing_brief_names():
    kernel = content(PIPELINE / "SKILL.md")
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/document/SKILL.md)" in kernel
    assert "documentation or business-document" in kernel
    assert "Factual release notes belong here" in kernel
    assert "Copy, messages and production scripts retain their legacy routes" in kernel


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_minutes_do_not_turn_missing_records_into_decisions(verb):
    text = content(PIPELINE / verb / "document/references/minutes.md").lower()
    assert "record" in text and "owner" in text and "deadline" in text
    assert "agreement" in text or "decision" in text
    assert "missing from the record" in text or "absent deadline" in text


def test_edit_protects_structure_and_execution_status():
    text = content(PIPELINE / "edit/document/SKILL.md")
    assert "Untouched sections and protected content stay unchanged" in text
    assert "Do not imply that unseen inbound links were checked" in text
    assert "Do not execute examples" in text
    assert "Never overwrite the source without authorization" in text


def test_analysis_gates_report_not_an_imaginary_new_document():
    text = content(PIPELINE / "analyze/document/SKILL.md")
    assert "Apply QA to the report" in text
    assert "does not require a full new-document brief" in text
    assert "analysis report need not contain a new README quick start" in text
    assert "Keep original files unchanged" in text
    assert "Missing evidence is unverified, not proof of falsehood" in text


def test_release_status_and_slides_are_not_publication_claims():
    release = content(PIPELINE / "write/document/references/release-notes.md")
    assert "planned, unreleased and shipped" in release
    assert "Do not infer a release date" in release
    slides = content(PIPELINE / "write/document/references/slides.md")
    assert "not a rendered deck" in slides
    assert "Source text alone cannot prove legibility" in slides


@pytest.mark.parametrize("name", FORMATS)
def test_format_guidance_is_operation_specific(name):
    texts = {
        (PIPELINE / verb / f"document/references/{name}.md").read_text()
        for verb in ("write", "edit", "analyze")
    }
    assert len(texts) == 3
