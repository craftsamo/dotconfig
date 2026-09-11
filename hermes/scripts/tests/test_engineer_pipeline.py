import importlib.util
from pathlib import Path

import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/engineer/skills/engineer-pipeline"
spec = importlib.util.spec_from_file_location("engineer_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_mode_tree_and_links():
    errors = []
    validator.validate_engineer_references(PIPELINE, errors)
    assert not errors
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
    qa = (PIPELINE / "references/quality-assurance/ux-persona.md").read_text()
    persona = (HERMES / "profiles/ux-persona/skills/ux-persona-pipeline/SKILL.md").read_text()
    assert "OWN ux-persona resident conversation" in qa
    assert "persona never performs this triage" in qa
    assert "Never inspect repository files" in persona
    for name in ("Hostile", "Reluctant", "Conscripted", "Earnest novice", "Hurried expert", "Distracted mobile", "Forced novice"):
        assert name in (PIPELINE / "references/quality-assurance/personas.md").read_text()
