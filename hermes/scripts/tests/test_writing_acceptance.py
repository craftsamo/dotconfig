"""The requester-acceptance rubric has one public definition; Writer links to it
but never runs it as self-QA, and it names no private caller-pipeline path."""

from pathlib import Path


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/writer/skills/writer-pipeline"
ACCEPTANCE = PIPELINE / "references/acceptance"


def text(name):
    return " ".join((ACCEPTANCE / name).read_text().split())


def raw(name):
    return (ACCEPTANCE / name).read_text()


def test_acceptance_docs_exist_as_a_flat_set():
    assert {p.name for p in ACCEPTANCE.glob("*.md")} == {"index.md", "prose.md", "script.md"}


def test_skill_links_to_acceptance_but_does_not_self_qa():
    kernel = (PIPELINE / "SKILL.md").read_text()
    assert "[references/acceptance/index.md](references/acceptance/index.md)" in kernel
    assert "never runs it as self-QA" in kernel
    assert "This is self-review, not the" in kernel
    # The kernel links to it; it does not duplicate the rubric table.
    assert "| Purpose |" not in kernel
    assert "at most two corrective returns" not in kernel


def test_acceptance_is_self_contained_no_private_pipeline_paths():
    index_raw = raw("index.md")
    for private_marker in (
        "../../plan/", "../../execute/", "assistant-pipeline",
        "marketing-state.md", "Plan/requester",
    ):
        assert private_marker not in index_raw
    # Only internal, same-directory or same-skill links remain.
    for name in ("prose.md", "script.md"):
        assert raw(name).count("../..") == 0


def test_common_floor_is_inlined_not_cross_referenced():
    index = text("index.md")
    assert "## Common floor" in raw("index.md")
    assert "Inspect the actual artifact" in index
    assert "Cannot verify" in index or "Cannot verify \u2260 pass" in index
    assert "Never repair" in index


def test_all_six_families_and_three_operations_present():
    index = text("index.md")
    for family in ("post", "article", "document", "message", "copy", "script"):
        assert f"Served {family} gate" in index
    prose = text("prose.md")
    for family in ("Post", "Article", "Document", "Message", "Copy"):
        assert f"### {family} scoring anchors" in prose
        assert f"write-{family.lower()}" in prose or f"write-{family.lower()}" in index
    script = text("script.md")
    assert "write-script" in script or "write-script" in index
    for verb in ("write", "edit", "analyze"):
        assert f"`{verb}-" in index or f"`{verb}-" in prose


def test_evidence_anchored_rubric_and_ceiling_are_intact():
    index = text("index.md")
    for axis in ("Purpose", "Structure and usability", "Reasoning and evidence",
                 "Information economy", "Expression fit", "Fidelity and voice"):
        assert f"| {axis} |" in index
    for score in range(5):
        assert f"| {score} |" in index
    assert "every applicable axis is at least 3" in index
    assert "unverified with no numeric score" in index
    assert "at most two corrective returns per released unit" in index
    assert "does not reset the budget" in index
    assert "Escalation is not acceptance" in index


def test_assessor_is_the_requester_not_a_named_profile():
    index = text("index.md")
    assert "The requester scores its own reading" in index
    assert "Assistant scores" not in index
    assert "Assistant" not in raw("index.md")
    assert "The requester performs a read-only inspection" in text("prose.md")
    assert "The orchestrating assistant" not in raw("prose.md")


def test_who_reads_this_names_every_caller_and_stays_self_contained():
    index = text("index.md")
    assert "## Who reads this" in raw("index.md")
    for caller in ("assistant", "engineer", "creator", "marketer"):
        assert caller in index
    assert "It needs no other file from this or any other profile" in index
    assert "Writer does not run this contract as self-QA" in index
