import importlib.util
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import hermes_yaml as yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/searcher/skills/searcher-pipeline"
spec = importlib.util.spec_from_file_location("searcher_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

MODES = ("lookup", "sweep", "hunt")
ENTRIES = tuple(f"{mode}-searcher" for mode in MODES)
STAGES = ("plan", "build", "qa")
SHARED = {f"references/{stage}.md" for stage in STAGES}


def flat(path):
    return " ".join(Path(path).read_text().split())


def test_exact_entries_and_owned_procedures():
    errors = []
    found = validator.validate_searcher_entries(PIPELINE, errors)
    assert not errors
    assert set(found) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("*.md")} == {
        "SKILL.md", *(f"{name}/SKILL.md" for name in ENTRIES), *SHARED,
    }
    for name in ENTRIES:
        text = found[name].read_text()
        for section in ("## Plan", "## Build", "## Output template", "## Verification", "## Handoff"):
            assert section in text, (name, section)
        assert text.index("<ReadBeforeWork>") < text.index("# " + name.split("-")[0].title())
        assert text.index("\n---\n", 4) < 4000
        for stage in STAGES:
            assert f"(../references/{stage}.md)" in text
    for name, marker in (("lookup-searcher", "### Steps"), ("sweep-searcher", "### Measurement variant"),
                         ("hunt-searcher", "### Hop loop")):
        assert marker in found[name].read_text()
    for relative in SHARED:
        body = (PIPELINE / relative).read_text()
        assert not body.startswith("---")
        for section in ("## Output template", "## Verification", "## Handoff"):
            assert section in body
    root = (PIPELINE / "SKILL.md").read_text()
    assert "version: 9.0.0" in root and root.index("\n---\n", 4) < 4000
    assert "<Procedure>" not in root
    for name in ENTRIES:
        assert f"({name}/SKILL.md)" in root
    for relative in SHARED:
        assert f"({relative})" in root


def test_profile_selection_contract_and_unchanged_tool_surface():
    config = yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
    prompt = " ".join(config["agent"]["system_prompt"].split())
    assert "first message is the brief" not in prompt.lower()
    assert "Purpose alone is not execution authority" in prompt
    for name in ENTRIES:
        assert name in prompt
    for gone in ("plan-searcher", "build-searcher", "qa-searcher"):
        assert gone not in prompt
    for phrase in (
        "every caller, resume or completion turn", "midturn",
        "full searcher-pipeline kernel", "not a past load, summary or root preload",
        "unchanged", "earlier body is unavailable", "read_file", "next_offset",
        "stop the affected search", "caller's release", "references/<stage>.md",
    ):
        assert phrase in prompt
    assert "Workflow v5" not in prompt
    for gone in ("goal_mode", "kanban_show", "kanban_complete", "survey-enumeration",
                 "exhaustive-hunt", "STATE:", "DECISION(", "card gate"):
        assert gone not in prompt
    social = {"x_access", "youtube_access", "note_access", "substack_access"}
    chains = {"evm_access", "solana_access"}
    assert set(config["toolsets"]) == {"file", "web", "x_search", "skills", "memory"} | social | chains
    assert set(config["platform_toolsets"]["cli"]) == {
        "file", "web", "x_search", "skills", "memory", "no_mcp", "connections"} | social | chains
    assert {"x-access", "youtube-access", "note-access", "substack-access",
            "evm-access", "solana-access"} <= set(config["plugins"]["enabled"])
    assert "messaging" not in " ".join(config["toolsets"]) and not [t for t in config["toolsets"] if t.endswith("_account")]
    assert config["platform_toolsets"]["telegram"] == []
    assert config["platform_toolsets"]["discord"] == []
    assert config["skills"]["create_dir"] == "skills/learned"
    assert config["skills"]["template_vars"] is True
    assert config["skills"]["inline_shell"] is False


def test_kernel_keeps_release_boundaries():
    text = flat(PIPELINE / "SKILL.md")
    for unit in ("survey-enumeration", "exhaustive-hunt"):
        assert unit not in text
    for phrase in (
        "agent-authored context, not human approval", "Retrieval, not synthesis",
        "No write-actions on social platforms", "caller's release",
    ):
        assert phrase in text
    for path in PIPELINE.rglob("*.md"):
        body = path.read_text()
        assert "goal_mode" not in body and "kanban_complete" not in body, path.name
    for name in ENTRIES:
        block = (PIPELINE / name / "SKILL.md").read_text().split("</ReadBeforeWork>", 1)[0]
        assert "Direct entry requires" in block and "card gate" not in block
        block = " ".join(block.split())
        assert "does not restart coverage or the frontier, reset a budget" in block
        assert "caller's release" in block
        assert "${HERMES_SKILL_DIR}/../references/<stage>.md" in block


@pytest.fixture
def candidate(tmp_path):
    return Path(shutil.copytree(PIPELINE, tmp_path / "searcher-pipeline"))


@pytest.mark.parametrize("relative", (*(f"{name}/SKILL.md" for name in ENTRIES), *sorted(SHARED)))
def test_missing_instruction_fails(candidate, relative):
    (candidate / relative).unlink()
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"missing searcher instruction: {relative}" in errors


@pytest.mark.parametrize("token", (
    'skill_view(name="searcher-pipeline")', 'file_path="references/<stage>.md"',
    "${HERMES_SKILL_DIR}/../SKILL.md", "not a past load or summary", "read_file", "next_offset", "stop",
    "full-body", "current context", "unchanged", "earlier body is unavailable",
    "${HERMES_SKILL_DIR}/SKILL.md", "${HERMES_SKILL_DIR}/../references/<stage>.md",
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
    (("name: lookup-searcher", "name: alternate-lookup"), "frontmatter name must be lookup-searcher"),
    (("category: searcher-pipeline", "category: technic"), "metadata.hermes.category must be searcher-pipeline"),
    (("Lookup specific facts", "Generic specific facts"), "searcher description must frontload lookup"),
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
    "lookup-searcher/references/notes.txt", "sweep-searcher/scripts/probe.sh",
    "plan-searcher/SKILL.md", "build-searcher/SKILL.md", "qa-searcher/SKILL.md",
    "lookup-searcher/references/lookup.md", ".editor/SKILL.md",
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


@pytest.mark.parametrize("relative", ("SKILL.md", "hunt-searcher/SKILL.md", "references/build.md"))
def test_goal_mode_cannot_return_without_cards(candidate, relative):
    path = candidate / relative
    path.write_text(path.read_text() + "\nEach judge turn is one hop under goal_mode.\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("has no goal_mode" in error and path.name in error for error in errors)


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
    assert validator.validate_worker("searcher", errors) == (3, 0)
    assert not errors
    boundary.assert_called_once()
    plugins.assert_called_once()
    learned = skills / "learned" / name
    learned.mkdir(parents=True)
    (learned / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Collision\n---\n")
    errors = []
    validator.validate_worker("searcher", errors)
    assert f"duplicate searcher skill name: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_frontmatter_must_fit_runtime_prefix(candidate, name):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace("author: CraftSamo", "padding: " + "x" * 4000 + "\nauthor: CraftSamo"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("4000" in error or "4,000" in error for error in errors)


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("section", ("## Plan", "## Build", "## Output template", "## Verification", "## Handoff"))
def test_mode_must_own_every_stage_section(candidate, name, section):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace(f"\n{section}\n", "\n## Removed\n"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry missing {section}: {name}" in errors


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("section", ("## Output template", "## Verification", "## Handoff"))
def test_stage_reference_owns_its_sections(candidate, stage, section):
    ref = candidate / f"references/{stage}.md"
    ref.write_text(ref.read_text().replace(section, "## Removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher stage reference missing {section}: {stage}.md" in errors


def test_declared_policy_not_model_routing_compliance():
    root = flat(PIPELINE / "SKILL.md")
    plan, build, qa = (flat(PIPELINE / f"references/{stage}.md") for stage in STAGES)
    for phrase in (
        "no reset, new grant or replay", "Fields or transport",
    ):
        assert phrase.lower() in root.lower()
    for gone in ("valid card is already released", "no new Plan negotiation or approval",
                 "Do not make a plan on the card", "before ALL phases"):
        assert gone.lower() not in root.lower()
    for phrase in (
        "supplied materials only, no unapproved external search",
        "Obtain client agreement before Build", "explicitly authorized settled execution brief",
        "ordinary one-shot inquiry needs no ceremonial approval", "bounded preliminary Build",
        "SAME-role units", "whole project decomposition or cross-role assignment",
        "short approval advances",
    ):
        assert phrase.lower() in plan.lower()
    assert "same scope and remaining budget" in qa
    assert "expansion goes to [Plan](plan.md) and client agreement" in qa
    assert "caller final acceptance or a new self numeric score" in qa
    assert "actual Build findings/ledger in current context" in qa
    assert "report it as unverified and stop" in qa
    assert "never invent a Checked result" in qa
    assert "Interpreted as:" in build and "direct settled briefs" in build
    assert "valid cards" not in build
    assert "A stop needs a true reason" in build


@pytest.mark.parametrize("name", ENTRIES)
def test_kernel_must_route_every_mode(candidate, name):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"({name}/SKILL.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher kernel does not route {name}" in errors


@pytest.mark.parametrize("relative", sorted(SHARED))
def test_kernel_must_link_every_stage(candidate, relative):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"({relative})", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher kernel does not link reference: {relative.removeprefix('references/')}" in errors


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("stage", STAGES)
def test_mode_must_link_every_stage(candidate, name, stage):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace(f"(../references/{stage}.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link stage reference {stage}: {name}" in errors
