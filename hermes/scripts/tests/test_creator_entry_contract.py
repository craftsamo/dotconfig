"""Offline mechanical text contracts, not model selection or policy enforcement.

Public candidate only. Configs are parsed with safe YAML, never Hermes' mutating
config loader; assertions/serialization use only the approved safe projection.
Existing role, engine, transport and approval suites own their broader contracts.
"""

from pathlib import Path
import re

import pytest
import hermes_yaml as yaml


ROOT = Path(__file__).resolve().parents[2]
ENTRIES = {
    "propose-creator": "# Propose - intent into directions",
    "revise-creator": "# Revise - feedback into changes",
}
RETIRED_ENTRIES = ("plan-creator", "build-creator", "qa-creator")


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


def creator_config():
    return yaml.safe_load(text(ROOT / "profiles/creator/config.yaml"))


@pytest.mark.parametrize("entry", ENTRIES)
def test_creator_direct_entry_contract_offline_mechanical(entry):
    document = text(pipeline("creator") / entry / "SKILL.md")
    context = block(document, "ReadBeforeWork")
    assert ENTRIES[entry] in document
    assert document.index("</ReadBeforeWork>") < document.index(ENTRIES[entry])
    for required in (
        'skill_view(name="creator-pipeline")',
        "on each inbound turn or completion",
        "before a change of entry, subject or scope",
        "Reuse full-body instructions only while present in current context",
        "including direct entry, load the kernel if its full body is missing",
        "This entry is the complete procedure",
        "Read only the selected subject references and knowledge",
        "If `skill_view` returns unchanged while a body is unavailable",
        "`read_file`",
        "`${HERMES_SKILL_DIR}/../SKILL.md`",
        "`${HERMES_SKILL_DIR}/SKILL.md`",
        "`${HERMES_SKILL_DIR}/../references/`",
        "following `next_offset`",
        "if a required body stays missing, stop and report it",
    ):
        assert required in context, required
    kernel = text(pipeline("creator") / "SKILL.md")
    assert kernel.count(f"({entry}/SKILL.md)") >= 1
    assert not (pipeline("creator") / entry / "references").exists()


def test_creator_references_point_back_to_kernel():
    references = list((pipeline("creator") / "references").glob("*/*.md"))
    assert references
    for path in references:
        body = text(path)
        assert "(../../SKILL.md)" in body
        assert "name:" not in body.split("\n\n", 1)[0]
        assert not (path.parent / "SKILL.md").exists()


def test_creator_is_a_read_only_advisor_offline_mechanical():
    kernel = compact(text(pipeline("creator") / "SKILL.md"))
    propose = compact(text(pipeline("creator") / "propose-creator/SKILL.md"))
    revise = compact(text(pipeline("creator") / "revise-creator/SKILL.md"))
    assert "Creator is an advisor" in kernel
    assert "The Assistant is the only client" in kernel
    assert "never its `<Procedure>`" in kernel
    assert "No production: no generation, TTS, hands calls, `clarify`" in kernel
    assert "No storyboard, timeline, frame specification, layout or pixel size" in kernel
    assert "no score, verdict, ranking or unrequested critique" in kernel
    assert "A recommendation never approves a proposal, preview or spend" in kernel
    assert "`no leaf fits`" in kernel
    assert "`skill / intent / deliver / budget / form`" in kernel
    # observed / suggested / decided stay apart
    assert "Keep observed evidence, the user's decisions, your suggestions and open questions apart" in propose
    assert "A research example is inspiration, never a production input" in propose
    assert "A direction is a suggestion; nothing is approved or released until the Assistant relays the user's choice" in propose
    assert "The feedback is the brief" in revise
    assert "No score, verdict, ranking or comparison with other work" in revise
    assert "needing a new approval" in revise


def test_creator_turn_selection_and_retired_paths():
    prompt = compact(creator_config()["agent"]["system_prompt"])
    for required in (
        "select propose-creator or revise-creator from the available skills",
        "re-evaluate before a change of entry, subject or scope within the turn",
        "never from a past load, preload label or summary alone",
        "Direct entry requires the kernel too",
        "if still missing, stop the affected action",
        "Never evade dedup with alternate paths or artificial ranges",
        "you produce nothing and commission nothing",
        "Use specialist_call/specialist_session only for researcher and searcher",
    ):
        assert required in prompt, required
    skills = ROOT / "profiles/creator/skills"
    for entry in RETIRED_ENTRIES:
        assert not (skills / "creator-pipeline" / entry).exists()
    for retired in ("capabilities.md", "craft.md", "legacy"):
        assert not (skills / "creator-pipeline/references" / retired).exists()
    assert not any(p.is_file() and p.name != ".gitkeep" for p in (skills / "technic").rglob("*"))
    for path in skills.rglob("*.md"):
        body = text(path)
        for entry in RETIRED_ENTRIES:
            assert f"({entry}/" not in body, path
            assert f"skill_view(name=\"{entry}\")" not in body, path
        assert not re.search(r"references/(?:plan|build|quality-assurance|legacy)/", body), path


def test_creator_config_has_no_generation_or_hands_reach():
    config = creator_config()
    assert config["toolsets"] == [
        "file", "vision", "web", "skills", "memory", "specialist", "media_inspect",
    ]
    for toolsets in config["platform_toolsets"].values():
        assert "image_gen" not in toolsets and "tts" not in toolsets
        assert "terminal" not in toolsets
    # Researcher and Searcher only, never a hands target; Searcher has no A2A endpoint.
    assert config["specialist_call"]["resident_targets"] == ["researcher", "searcher"]
    assert set(config["a2a_agents"]) == {"researcher"}
    assert not config.get("platforms", {}).get("telegram")
    external = [str(p) for p in config["skills"]["external_dirs"]]
    for hands in ("image-creator", "video-creator", "audio-creator"):
        assert f"~/.hermes/profiles/{hands}/skills/{hands}-pipeline" in external
