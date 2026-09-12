import importlib.util
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/searcher/skills/searcher-pipeline"
spec = importlib.util.spec_from_file_location("searcher_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

ENTRIES = ("lookup-searcher", "sweep-searcher", "hunt-searcher")
CATALOG = {"survey-enumeration": "searcher", "exhaustive-hunt": "searcher"}


def test_exact_entries_and_owned_procedures():
    errors = []
    found = validator.validate_searcher_entries(PIPELINE, errors)
    assert not errors
    assert set(found) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("*.md")} == {
        "SKILL.md", *(f"{name}/SKILL.md" for name in ENTRIES),
    }
    assert not list((PIPELINE / "references").rglob("*.md"))
    for name, marker in (
        ("lookup-searcher", "## Steps"),
        ("sweep-searcher", "## Measurement variant"),
        ("hunt-searcher", "## Hop loop"),
    ):
        text = found[name].read_text()
        assert marker in text and "## Output template" in text
        assert "## Verification" in text and "## Handoff" in text
        assert text.index("<ReadBeforeWork>") < text.index("# " + name.split("-")[0].title())
        assert text.index("\n---\n", 4) < 4000


def test_profile_selection_contract_and_unchanged_tool_surface():
    config = yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
    prompt = " ".join(config["agent"]["system_prompt"].split())
    for name in ENTRIES:
        assert name in prompt
    for phrase in (
        "every caller, judge, resume or completion turn", "midturn",
        "full searcher-pipeline kernel", "not a past load, summary or root preload",
        "unchanged", "earlier body is unavailable", "read_file", "next_offset",
        "stop the affected search", "caller's release", "kanban_show and the card gate",
    ):
        assert phrase in prompt
    assert set(config["toolsets"]) == {"file", "web", "x_search", "skills", "memory"}
    assert set(config["platform_toolsets"]["cli"]) == {"file", "web", "x_search", "skills", "memory", "no_mcp"}
    assert config["platform_toolsets"]["telegram"] == []
    assert config["platform_toolsets"]["discord"] == []
    assert config["skills"]["create_dir"] == "skills/learned"
    assert config["skills"]["template_vars"] is True
    assert config["skills"]["inline_shell"] is False


def test_kernel_keeps_card_and_release_boundaries():
    errors = []
    validator.validate_worker_card_gate("searcher", CATALOG, errors)
    assert not errors
    text = (PIPELINE / "SKILL.md").read_text()
    for unit in CATALOG:
        assert f"`{unit}`" in text
    for phrase in (
        "agent-authored context, not human approval", "Retrieval, not synthesis",
        "No write-actions on social platforms", "caller's release",
    ):
        assert phrase in text
    for name in ENTRIES:
        block = (PIPELINE / name / "SKILL.md").read_text().split("</ReadBeforeWork>", 1)[0]
        assert "Direct entry requires" in block and "card gate" in block
        assert "does not restart coverage or the frontier, reset a budget" in block
        assert "caller's release, not self-decomposition" in block


@pytest.fixture
def candidate(tmp_path):
    return Path(shutil.copytree(PIPELINE, tmp_path / "searcher-pipeline"))


@pytest.mark.parametrize("name", ENTRIES)
def test_missing_entry_fails(candidate, name):
    (candidate / name / "SKILL.md").unlink()
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"missing searcher instruction: {name}/SKILL.md" in errors


@pytest.mark.parametrize("token", (
    'skill_view(name="searcher-pipeline")', "${HERMES_SKILL_DIR}/../SKILL.md",
    "not a past load or summary", "read_file", "next_offset", "stop", "card gate",
))
def test_direct_entry_cannot_drop_dependency_or_recovery(candidate, token):
    entry = candidate / "lookup-searcher/SKILL.md"
    entry.write_text(entry.read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry ReadBeforeWork missing {token}: lookup-searcher" in errors


@pytest.mark.parametrize("replacement, expected", (
    (("name: lookup-searcher", "name: alternate-lookup"), "frontmatter name must be lookup-searcher"),
    (("category: searcher-pipeline", "category: technic"), "metadata.hermes.category must be searcher-pipeline"),
    (("Lookup: targeted", "Generic: targeted"), "searcher description must frontload lookup"),
    (("version: 1.0.0", "version: ''"), "searcher entry version must be a nonempty string"),
))
def test_entry_metadata_is_validated(candidate, replacement, expected):
    entry = candidate / "lookup-searcher/SKILL.md"
    entry.write_text(entry.read_text().replace(*replacement))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


@pytest.mark.parametrize("relative", (
    "references/lookup.md", "tests/fixture/SKILL.md", "fourth-searcher/SKILL.md",
    "lookup-searcher/references/notes.txt", "hunt-searcher/scripts/probe.sh",
    ".editor/SKILL.md",
))
def test_old_alias_or_unexpected_instruction_fails(candidate, relative):
    path = candidate / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Not an authorized instruction\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"unexpected searcher instruction: {relative}" in errors


def test_incidental_dotfiles_do_not_change_topology(candidate):
    for relative in (".DS_Store", "lookup-searcher/.SKILL.md.swp", ".editor/state"):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Editor metadata\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert not errors


def test_catalog_cannot_be_redeclared_on_child(candidate):
    entry = candidate / "sweep-searcher/SKILL.md"
    entry.write_text(entry.read_text().replace("version: 1.0.0", "card_units: []\nversion: 1.0.0"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("searcher must not declare card_units" in error for error in errors)


@pytest.mark.parametrize("link, expected", (
    ("missing.md", "broken searcher link"),
    ("../../outside.md", "searcher link escapes pipeline"),
))
def test_links_are_contained_and_real(candidate, link, expected):
    entry = candidate / "lookup-searcher/SKILL.md"
    entry.write_text(entry.read_text() + f"\n[bad]({link})\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


def test_nested_symlink_cannot_hide_instructions(candidate):
    (candidate / "hidden").symlink_to(candidate / "lookup-searcher", target_is_directory=True)
    errors = []
    assert validator.validate_searcher_entries(candidate, errors) == {}
    assert any("searcher pipeline must not contain symlinks" in error for error in errors)


def test_worker_wires_entries_and_detects_learned_collision(tmp_path, monkeypatch):
    skills = tmp_path / "profiles/searcher/skills"
    shutil.copytree(PIPELINE, skills / "searcher-pipeline")
    (skills / "technic").mkdir()
    monkeypatch.setattr(validator, "HERMES_ROOT", tmp_path)
    # Isolate this structural fixture, while proving the normal ownership/plugin
    # checks are still called by the worker path (the full CLI tests them separately).
    boundary, plugins = Mock(), Mock()
    monkeypatch.setattr(validator, "validate_git_boundary", boundary)
    monkeypatch.setattr(validator, "validate_plugin_enabled", plugins)
    errors = []
    assert validator.validate_worker("searcher", errors, catalog=CATALOG) == (3, 0)
    assert not errors
    boundary.assert_called_once()
    plugins.assert_called_once()
    learned = skills / "learned/lookup-searcher"
    learned.mkdir(parents=True)
    (learned / "SKILL.md").write_text("---\nname: lookup-searcher\ndescription: Collision\n---\n")
    errors = []
    validator.validate_worker("searcher", errors, catalog=CATALOG)
    assert "duplicate searcher skill name: lookup-searcher" in errors
