"""Retired routing must not re-enter through consultation or injected policy."""

from itertools import product
from pathlib import Path

import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/writer/skills/writer-pipeline"
RETIRED = ["legacy.md", "assess.md", "prose.md", "script.md", "review.md"]


def content(path):
    return " ".join(path.read_text().split())


def test_only_consultation_remains_in_root_references():
    assert sorted(path.name for path in (PIPELINE / "references").glob("*.md")) == [
        "consultation.md"
    ]
    kernel = (PIPELINE / "SKILL.md").read_text()
    assert "](references/consultation.md)" in kernel
    assert "If no installed leaf fits, return the unsupported scope" in kernel
    for name in RETIRED:
        assert f"references/{name}" not in kernel


def test_all_eighteen_leaves_are_retained_and_routed():
    kernel = (PIPELINE / "SKILL.md").read_text()
    for verb, subject in product(
        ("write", "edit", "analyze"),
        ("post", "article", "document", "message", "copy", "script"),
    ):
        path = f"{verb}/{subject}/SKILL.md"
        assert (PIPELINE / path).is_file()
        assert f"]({path})" in kernel
    assert "technical-prose briefs" in kernel
    assert "documentation or business-document" in kernel
    assert "marketing-copy briefs" in kernel


def test_consultation_is_bounded_advice_not_a_fourth_operation():
    advice = content(PIPELINE / "references/consultation.md")
    assert "not a fourth writing operation" in advice
    assert "Reference text supplied merely to inform advice" in advice
    assert "does not itself change the operation" in advice
    assert "explicitly released outline unit is different" in advice
    assert "no full draft or unsolicited rewrite" in advice
    assert "not an actual producer limit or measured timing" in advice
    assert "For effort/sizing questions" in advice
    assert "planning estimates, not measured completion times" in advice


def test_injected_policy_cannot_reactivate_legacy_workflows():
    config = yaml.safe_load((HERMES / "profiles/writer/config.yaml").read_text())
    policy = config["agent"]["system_prompt"]
    assert "consultation reference" in policy
    assert "no generic fallback or additional review pipeline" in policy
    assert "only on an explicit request" in policy
    assert "bounded consultation or analysis" in policy
    assert "legacy contract" not in policy
    assert "TypeTable" not in policy
    assert "terminal" not in config["toolsets"]


def test_runtime_writer_files_do_not_reference_retired_paths():
    for path in PIPELINE.rglob("*.md"):
        text = path.read_text()
        for name in RETIRED:
            assert f"references/{name}" not in text, (path, name)
        assert "japanese-writing/scripts/" not in text, path
        assert "references/inspection/" not in text, path
