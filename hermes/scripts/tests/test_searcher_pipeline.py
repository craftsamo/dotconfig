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

ENTRIES = ("plan-searcher", "build-searcher", "qa-searcher")
UNITS = ("lookup", "sweep", "hunt")
CATALOG = {"survey-enumeration": "searcher", "exhaustive-hunt": "searcher"}


def test_exact_entries_and_owned_procedures():
    errors = []
    found = validator.validate_searcher_entries(PIPELINE, errors)
    assert not errors
    assert set(found) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("*.md")} == {
        "SKILL.md", *(f"{name}/SKILL.md" for name in ENTRIES),
        *(f"{name}/references/{unit}.md" for name in ENTRIES for unit in UNITS),
    }
    assert not list((PIPELINE / "references").rglob("*.md"))
    for name in ENTRIES:
        text = found[name].read_text()
        assert "## Output template" in text
        assert "## Verification" in text and "## Handoff" in text
        heading = "QA" if name.startswith("qa-") else name.split("-")[0].title()
        assert text.index("<ReadBeforeWork>") < text.index("# " + heading)
        assert text.index("\n---\n", 4) < 4000
        marker = {"plan-searcher": "## Plan", "build-searcher": "## Output template", "qa-searcher": "## Verification"}[name]
        for unit in UNITS:
            ref = PIPELINE / name / f"references/{unit}.md"
            assert marker in ref.read_text()
            assert not ref.read_text().startswith("---")
            assert f"(references/{unit}.md)" in text
    for unit, marker in (("lookup", "## Steps"), ("sweep", "## Measurement variant"), ("hunt", "## Hop loop")):
        assert marker in (PIPELINE / "build-searcher/references" / f"{unit}.md").read_text()
    root = (PIPELINE / "SKILL.md").read_text()
    assert "version: 7.0.0" in root and root.index("\n---\n", 4) < 4000
    assert "<Procedure>" not in root
    for name in ENTRIES:
        assert f"({name}/SKILL.md)" in root


def test_profile_selection_contract_and_unchanged_tool_surface():
    config = yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
    prompt = " ".join(config["agent"]["system_prompt"].split())
    assert "first message is the brief" not in prompt.lower()
    assert "Purpose alone is not execution authority" in prompt
    for name in ENTRIES:
        assert name in prompt
    for phrase in (
        "every caller, judge, resume or completion turn", "midturn",
        "full searcher-pipeline kernel", "not a past load, summary or root preload",
        "unchanged", "earlier body is unavailable", "read_file", "next_offset",
        "stop the affected search", "caller's release", "kanban_show and the card gate",
        "selected unit references", "before ALL phases", "Build -> QA -> terminal",
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
        block = " ".join(block.split())
        assert "does not restart coverage or the frontier, reset a budget" in block
        assert "caller's release" in block
        assert "${HERMES_SKILL_DIR}/references/<unit>.md" in block


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
    "full-body", "current context", "unchanged", "earlier body is unavailable",
    "${HERMES_SKILL_DIR}/SKILL.md", "${HERMES_SKILL_DIR}/references/<unit>.md",
    "caller's release",
))
@pytest.mark.parametrize("name", ENTRIES)
def test_direct_entry_cannot_drop_dependency_or_recovery(candidate, token, name):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry ReadBeforeWork missing {token}: {name}" in errors


@pytest.mark.parametrize("replacement, expected", (
    (("name: plan-searcher", "name: alternate-plan"), "frontmatter name must be plan-searcher"),
    (("category: searcher-pipeline", "category: technic"), "metadata.hermes.category must be searcher-pipeline"),
    (("Plan: propose", "Generic: propose"), "searcher description must frontload plan"),
    (("version: 1.0.0", "version: ''"), "searcher entry version must be a nonempty string"),
))
def test_entry_metadata_is_validated(candidate, replacement, expected):
    entry = candidate / "plan-searcher/SKILL.md"
    entry.write_text(entry.read_text().replace(*replacement))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


@pytest.mark.parametrize("relative", (
    "references/lookup.md", "tests/fixture/SKILL.md", "fourth-searcher/SKILL.md",
    "plan-searcher/references/notes.txt", "build-searcher/scripts/probe.sh",
    "lookup-searcher/SKILL.md", "sweep-searcher/SKILL.md", "hunt-searcher/SKILL.md",
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
    for relative in (".DS_Store", "plan-searcher/.SKILL.md.swp", ".editor/state"):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Editor metadata\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert not errors


@pytest.mark.parametrize("name", ENTRIES)
def test_catalog_cannot_be_redeclared_on_child(candidate, name):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace("version: 1.0.0", "card_units: []\nversion: 1.0.0"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("searcher must not declare card_units" in error for error in errors)


@pytest.mark.parametrize("link, expected", (
    ("missing.md", "broken searcher link"),
    ("../../outside.md", "searcher link escapes pipeline"),
))
def test_links_are_contained_and_real(candidate, link, expected):
    entry = candidate / "plan-searcher/SKILL.md"
    entry.write_text(entry.read_text() + f"\n[bad]({link})\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


def test_nested_symlink_cannot_hide_instructions(candidate):
    (candidate / "hidden").symlink_to(candidate / "plan-searcher", target_is_directory=True)
    errors = []
    assert validator.validate_searcher_entries(candidate, errors) == {}
    assert any("searcher pipeline must not contain symlinks" in error for error in errors)


@pytest.mark.parametrize("name", ENTRIES)
def test_worker_wires_entries_and_detects_learned_collision(tmp_path, monkeypatch, name):
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
    learned = skills / "learned" / name
    learned.mkdir(parents=True)
    (learned / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Collision\n---\n")
    errors = []
    validator.validate_worker("searcher", errors, catalog=CATALOG)
    assert f"duplicate searcher skill name: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("unit", UNITS)
def test_missing_owned_reference_fails(candidate, name, unit):
    relative = f"{name}/references/{unit}.md"
    (candidate / relative).unlink()
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"missing searcher instruction: {relative}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_frontmatter_must_fit_runtime_prefix(candidate, name):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace("author: CraftSamo", "padding: " + "x" * 4000 + "\nauthor: CraftSamo"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("4000" in error or "4,000" in error for error in errors)


@pytest.mark.parametrize("phase,marker", (("plan", "## Plan"), ("build", "## Output template"), ("qa", "## Verification")))
@pytest.mark.parametrize("unit", UNITS)
def test_reference_phase_ownership_is_required(candidate, phase, marker, unit):
    ref = candidate / f"{phase}-searcher/references/{unit}.md"
    ref.write_text(ref.read_text().replace(marker, "## Removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert errors


def test_declared_policy_not_model_routing_compliance():
    root = " ".join((PIPELINE / "SKILL.md").read_text().split())
    plan = " ".join((PIPELINE / "plan-searcher/SKILL.md").read_text().split())
    qa = " ".join((PIPELINE / "qa-searcher/SKILL.md").read_text().split())
    for phrase in (
        "valid card is already released", "Build -> QA -> terminal",
        "no new Plan negotiation or approval", "Do not make a plan on the card",
        "immediate `kanban_block(kind=capability)`", "before ALL phases",
        "no reset, new grant or replay", "Fields or transport",
    ):
        assert phrase.lower() in root.lower()
    for phrase in (
        "supplied materials only, no unapproved external search",
        "Obtain client agreement before Build", "explicitly authorized settled execution brief",
        "ordinary one-shot inquiry needs no ceremonial approval", "bounded preliminary Build",
        "SAME-role units", "whole project decomposition or cross-role assignment",
        "short approval advances",
    ):
        assert phrase.lower() in plan.lower()
    assert "same scope and remaining budget" in qa
    assert "expansion goes to Plan and client agreement" in qa
    assert "caller final acceptance or a new self numeric score" in qa
    assert "actual Build findings/ledger in current context" in qa
    assert "report it as unverified and stop" in qa
    assert "never kanban_complete on a fabricated Checked result" in qa
    build = " ".join((PIPELINE / "build-searcher/SKILL.md").read_text().split())
    assert "Interpreted as:" in build and "valid cards and direct settled briefs" in build


@pytest.mark.parametrize("name", ENTRIES)
def test_kernel_must_link_every_phase(candidate, name):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"({name}/SKILL.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert errors


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("unit", UNITS)
def test_phase_must_link_owned_reference(candidate, name, unit):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace(f"(references/{unit}.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert errors


def test_reference_cannot_redeclare_cards(candidate):
    ref = candidate / "build-searcher/references/sweep.md"
    ref.write_text("---\ncard_units: []\n---\n" + ref.read_text())
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert errors
