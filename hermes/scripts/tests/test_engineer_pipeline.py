import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/engineer/skills/engineer-pipeline"
spec = importlib.util.spec_from_file_location("engineer_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

ENTRIES = ("assess-engineer", "plan-engineer", "build-engineer", "qa-engineer")


def test_mode_tree_and_links():
    errors = []
    entries = validator.validate_engineer_references(PIPELINE, errors)
    assert not errors
    assert set(entries) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("SKILL.md")} == {
        "SKILL.md", *(f"{name}/SKILL.md" for name in ENTRIES),
    }
    assert len((PIPELINE / "SKILL.md").read_text().splitlines()) < 160


def test_engineer_scope_and_tools():
    config = yaml.safe_load((HERMES / "profiles/engineer/config.yaml").read_text())
    assert {"browser", "vision", "clarify", "specialist", "opencode"} <= set(config["toolsets"])
    assert "a2a" not in config["toolsets"]
    for platform in ("cli", "telegram"):
        assert {"browser", "specialist", "opencode"} <= set(config["platform_toolsets"][platform])
    assert not {"terminal", "browser", "specialist", "opencode", "delegation"} & set(config["platform_toolsets"]["a2a"])
    assert config["browser"]["use_real_profile"] is False
    assert set(config["specialist_call"]["resident_targets"]) == {"marketer", "researcher", "writer", "ui-review", "ux-persona"}
    assert {"opencode", "specialist-call"} <= set(config["plugins"]["enabled"])
    assert config["opencode_cli"]["enabled"] is True


def test_review_profiles_are_resident_only_and_non_coding():
    for name in ("ui-review", "ux-persona"):
        root = HERMES / "profiles" / name
        config = yaml.safe_load((root / "config.yaml").read_text())
        assert set(config["toolsets"]) == {"browser", "vision", "skills", "ui-inspection"}
        assert config["browser"]["use_real_profile"] is False
        assert config["browser"]["backend"] == "off"
        assert config["agent"]["coding_context"] == "off"
        assert config["memory"]["memory_enabled"] is False
        for platform in ("telegram", "discord", "a2a"):
            assert config["platform_toolsets"][platform] == []
        assert "platforms" not in config and "a2a_agents" not in config
        assert (root / ".no-bundled-skills").is_file()
        assert (root / "skills" / (name + "-pipeline") / "SKILL.md").is_file()


def test_no_retired_approval_or_cli_driving_contract():
    text = (PIPELINE / "SKILL.md").read_text()
    assert "Issue creation/updates/comments require" in text
    assert "One explicit implementation approval" in text
    assert "A1" not in text and "one unit at a time" not in text
    for name in ("assess.md", "implement.md", "verify.md", "delivery.md"):
        assert not (PIPELINE / "references" / name).exists()


def test_persona_independence_and_triage_owner():
    qa = (PIPELINE / "qa-engineer/references/ux-persona.md").read_text()
    persona = (HERMES / "profiles/ux-persona/skills/ux-persona-pipeline/SKILL.md").read_text()
    assert "OWN ux-persona resident conversation" in qa
    assert "persona never performs this triage" in qa
    assert "Never inspect repository files" in persona
    for name in ("Hostile", "Reluctant", "Conscripted", "Earnest novice", "Hurried expert", "Distracted mobile", "Forced novice"):
        assert name in (PIPELINE / "qa-engineer/references/personas.md").read_text()


def _copy_pipeline_candidate(tmp_path):
    candidate = tmp_path / "engineer-pipeline"
    shutil.copytree(PIPELINE, candidate)
    return candidate


@pytest.mark.parametrize("mode", ENTRIES)
def test_hands_references_missing_file_is_reported(tmp_path, mode):
    candidate = _copy_pipeline_candidate(tmp_path)
    (candidate / mode / "references/hands-references.md").unlink()
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert f"missing engineer reference: {mode}/references/hands-references.md" in errors


@pytest.mark.parametrize("mode", ENTRIES)
def test_hands_references_missing_route_is_reported(tmp_path, mode):
    candidate = _copy_pipeline_candidate(tmp_path)
    index = candidate / mode / "SKILL.md"
    index.write_text(index.read_text().replace("hands-references.md", ""))
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert f"engineer {mode} entry does not route hands-references.md" in errors


@pytest.mark.parametrize("mode", ENTRIES)
def test_hands_references_broken_link_is_reported(tmp_path, mode):
    candidate = _copy_pipeline_candidate(tmp_path)
    guide = candidate / mode / "references/hands-references.md"
    guide.write_text(guide.read_text() + "\n[broken](does-not-exist.md)\n")
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert "broken engineer reference link: hands-references.md: does-not-exist.md" in errors


def test_always_on_selection_and_approval_resume():
    config = yaml.safe_load((HERMES / "profiles/engineer/config.yaml").read_text())
    prompt = " ".join(config["agent"]["system_prompt"].split())
    for entry in ENTRIES:
        assert entry in prompt
    assert "Each inbound user turn or completion" in prompt
    assert "before any changed mode or scope action" in prompt
    assert "engineer-pipeline kernel" in prompt
    assert "read_file" in prompt and "or stop" in prompt
    assert "not an approval, a scope expansion or a replay" in prompt
    kernel = " ".join((PIPELINE / "SKILL.md").read_text().split())
    assert "select Build when it releases the agreed implementation, not Plan again" in kernel
    assert "instructions never resets the job or expands its grant" in kernel


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_requires_kernel_even_on_direct_selection(tmp_path, entry):
    candidate = _copy_pipeline_candidate(tmp_path)
    skill = candidate / entry / "SKILL.md"
    skill.write_text(skill.read_text().replace('skill_view(name="engineer-pipeline")', ""))
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert f'engineer entry ReadBeforeWork missing skill_view(name="engineer-pipeline"): {entry}' in errors


@pytest.mark.parametrize("entry", ENTRIES)
def test_missing_entry_is_not_a_silent_mode_fallback(tmp_path, entry):
    candidate = _copy_pipeline_candidate(tmp_path)
    (candidate / entry / "SKILL.md").unlink()
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert f"missing engineer entry skill: {entry}/SKILL.md" in errors


@pytest.mark.parametrize("token", [
    "read_file", "next_offset", "unchanged", "not a past load or summary",
    "${HERMES_SKILL_DIR}/../SKILL.md", "${HERMES_SKILL_DIR}/../references/opencode.md",
    "Stop the affected action", "not implementation\napproval",
])
def test_recovery_contract_cannot_be_omitted(tmp_path, token):
    candidate = _copy_pipeline_candidate(tmp_path)
    skill = candidate / "plan-engineer/SKILL.md"
    text = skill.read_text()
    assert token in text
    skill.write_text(text.replace(token, ""))
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert any("ReadBeforeWork missing" in error for error in errors)


def test_unexpected_skill_and_old_mode_reference_are_rejected(tmp_path):
    candidate = _copy_pipeline_candidate(tmp_path)
    hidden = candidate / "plan-engineer/references/unexpected"
    hidden.mkdir()
    (hidden / "SKILL.md").write_text("# Not a discoverable reference\n")
    old = candidate / "references/plan"
    old.mkdir()
    (old / "index.md").write_text("# Obsolete mode body\n")
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert "unexpected engineer entry skill: plan-engineer/references/unexpected/SKILL.md" in errors
    assert "unexpected engineer reference: references/plan/index.md" in errors


def test_no_nested_symlinks_or_reference_escape(tmp_path):
    candidate = _copy_pipeline_candidate(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside the contract\n")
    skill = candidate / "plan-engineer/SKILL.md"
    skill.write_text(skill.read_text() + "\n[outside](../../outside.md)\n")
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert "engineer reference escapes pipeline: SKILL.md: ../../outside.md" in errors
    (candidate / "linked").symlink_to(tmp_path, target_is_directory=True)
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert "engineer pipeline must not contain symlinks: linked" in errors


def test_no_new_card_catalog_or_orphan_personas(tmp_path):
    candidate = _copy_pipeline_candidate(tmp_path)
    skill = candidate / "build-engineer/SKILL.md"
    skill.write_text(skill.read_text().replace("version: 1.0.0", "card_units: []\nversion: 1.0.0"))
    persona = candidate / "qa-engineer/references/ux-persona.md"
    persona.write_text(persona.read_text().replace("](personas.md)", "](#missing)"))
    errors = []
    validator.validate_engineer_references(candidate, errors)
    assert "engineer defines no card units: build-engineer/SKILL.md" in errors
    assert "engineer ux-persona reference does not route personas.md" in errors


def test_worker_allows_only_the_four_engineer_entries(tmp_path, monkeypatch):
    profile = tmp_path / "profiles/engineer"
    shutil.copytree(HERMES / "profiles/engineer", profile)
    monkeypatch.setattr(validator, "HERMES_ROOT", tmp_path)
    # This is a structural fixture, not a substitute for the real Git gate.
    monkeypatch.setattr(validator, "validate_git_boundary", lambda *args: None)
    monkeypatch.setattr(validator, "validate_plugin_enabled", lambda *args: None)
    errors = []
    leaves, _ = validator.validate_worker("engineer", errors, catalog={})
    assert not errors
    assert leaves == 4 + len(list((profile / "skills/technic").glob("*/SKILL.md")))
    duplicate = profile / "skills/technic/plan-engineer"
    duplicate.mkdir()
    (duplicate / "SKILL.md").write_text(
        "---\nname: plan-engineer\nmetadata:\n  hermes:\n    category: technic\n---\n"
    )
    errors = []
    validator.validate_worker("engineer", errors, catalog={})
    assert "duplicate engineer skill name: plan-engineer" in errors
