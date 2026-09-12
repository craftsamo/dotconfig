"""Offline mechanical text contracts, not model selection or policy enforcement.

Public candidate only. Configs are parsed with safe YAML, never Hermes' mutating
config loader; assertions/serialization use only the approved safe projection.
Existing role, engine, transport and approval suites own their broader contracts.
"""

from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ENTRIES = {
    "plan-creator": "# Plan - from a client's words to filled forms",
    "build-creator": "# Build - hands make it; you hand off and supervise",
    "qa-creator": "# Quality assurance - against the client's intent",
}


def pipeline(profile):
    return ROOT / f"profiles/{profile}/skills/{profile}-pipeline"


def text(path):
    return path.read_text(encoding="utf-8")


def compact(value):
    return " ".join(value.split())


def block(value, tag):
    matches = re.findall(rf"<{tag}>\s*(.*?)\s*</{tag}>", value, re.DOTALL)
    assert len(matches) == 1, f"Expected one {tag} contract"
    return compact(matches[0])


@pytest.mark.parametrize("entry", ENTRIES)
def test_creator_direct_entry_contract_offline_mechanical(entry):
    document = text(pipeline("creator") / entry / "SKILL.md")
    context = block(document, "ReadBeforeWork")
    assert ENTRIES[entry] in document
    assert document.index("</ReadBeforeWork>") < document.index(ENTRIES[entry])
    for required in (
        'skill_view(name="creator-pipeline")',
        "every inbound turn or completion",
        "before an action changes mode, subject or scope",
        "A short approval resumes the retained job",
        "selection never restarts a plan or expands a grant",
        "Reuse full-body instructions only while present in current context",
        "not a past load, summary or preload marker",
        "Direct entry requires the full kernel as well",
        "Load that dependency if its body is missing",
        "This entry is the mode procedure",
        "there is no separate common-mode file to load",
        "Read only the selected subjects",
        "Before applying another entry's detail, load its owning entry and kernel",
        "Creator reads hands forms and relevant options as a Client",
        "never their producer procedure as permission to execute a served leaf locally",
        "If skill_view returns unchanged while the earlier body is unavailable",
        "read_file on the canonical document",
        "`${HERMES_SKILL_DIR}/../SKILL.md`",
        "`${HERMES_SKILL_DIR}/SKILL.md`",
        "`${HERMES_SKILL_DIR}/references/`",
        "Follow next_offset only when that read is truncated",
        "If the full required body still cannot be recovered, stop the affected action",
        "Never evade dedup with alternate paths or artificial ranges",
        "document's owning SKILL.md, not whichever skill was loaded last",
    ):
        assert required in context, required
    # Root navigation cannot be the sole route to a child's kernel dependency.
    assert text(pipeline("creator") / "SKILL.md").count(f"({entry}/SKILL.md)") >= 1
    references = list((pipeline("creator") / entry / "references").glob("*/*.md"))
    assert references
    for path in references:
        body = text(path)
        assert "(../../SKILL.md)" in body
        assert "name:" not in body.split("\n\n", 1)[0]
        assert not (path.parent / "SKILL.md").exists()


def test_creator_release_and_hands_boundary_offline_mechanical():
    root = compact(text(pipeline("creator") / "SKILL.md"))
    build = compact(text(pipeline("creator") / "build-creator/SKILL.md"))
    qa = compact(text(pipeline("creator") / "qa-creator/SKILL.md"))
    assert "Read the hands' `form`, never run their `<Procedure>`" in root
    assert "a proposal, findings-only analysis and final media are different outputs" in qa
    assert "You produce nothing yourself for a served family" in build
    assert "Transport is not a release or an additional grant" in build
    assert "A completed transport is not acceptance" in build
    music = compact(text(pipeline("creator") / "build-creator/references/audio-creator/music.md"))
    for required in ("zero spend", "only a matching second handoff", "approved_plan",
                     "approval_sha256", "A changed creative field needs a new proposal"):
        assert required in music


def test_creator_turn_selection_and_retired_paths():
    prompt = compact(yaml.safe_load(text(ROOT / "profiles/creator/config.yaml"))["agent"]["system_prompt"])
    for required in (
        "On every inbound turn or completion",
        "before an action changes mode, subject or scope",
        "select the matching entry from the available skills",
        "Reuse full bodies, never a past load, summary or preload marker",
        "A short approval resumes the retained job, not a new plan",
        "if recovery fails, stop the affected action",
    ):
        assert required in prompt
    skills = ROOT / "profiles/creator/skills"
    for path in skills.rglob("*.md"):
        body = text(path)
        assert not re.search(r"\[\.\./\.\./(?:plan|build|quality-assurance)/", body), path
        assert not re.search(r"`creator-pipeline` references/(?:plan|build|quality-assurance)/", body), path
