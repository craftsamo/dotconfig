import importlib.util
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import hermes_yaml as yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/searcher/skills/searcher-pipeline"
TECHNIC = HERMES / "profiles/searcher/skills/technic"
spec = importlib.util.spec_from_file_location("searcher_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

MODES = ("lookup", "sweep", "hunt")
ENTRIES = tuple(f"{mode}-searcher" for mode in MODES)
STAGES = ("plan", "build")
SHARED = {f"references/{stage}.md" for stage in STAGES}
SERVICES = ("x", "youtube", "note", "substack", "evm", "solana")
PLATFORMS = {f"references/platforms/{p}.md" for p in SERVICES}
CAPABILITIES = "references/capabilities.md"
TECHNICS = {"public-footprint": "hunt", "primary-fact-pack": "lookup", "release-digest": "sweep"}


def flat(path):
    return " ".join(Path(path).read_text().split())


def test_exact_entries_and_owned_procedures():
    errors = []
    found = validator.validate_searcher_entries(PIPELINE, errors)
    assert not errors
    assert set(found) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("*.md")} == {
        "SKILL.md", *(f"{name}/SKILL.md" for name in ENTRIES), *SHARED, *PLATFORMS, CAPABILITIES,
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
    assert "version: 11.0.0" in root and root.index("\n---\n", 4) < 4000
    assert "<Procedure>" not in root
    for name in ENTRIES:
        assert f"({name}/SKILL.md)" in root
    for relative in SHARED | PLATFORMS | {CAPABILITIES}:
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


@pytest.mark.parametrize("relative", (*(f"{name}/SKILL.md" for name in ENTRIES),
                                      *sorted(SHARED | PLATFORMS | {CAPABILITIES})))
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
    shutil.copytree(TECHNIC, skills / "technic")
    monkeypatch.setattr(validator, "HERMES_ROOT", tmp_path)
    # Isolate this structural fixture, while proving the normal ownership/plugin
    # checks are still called by the worker path (the full CLI tests them separately).
    boundary, plugins = Mock(), Mock()
    monkeypatch.setattr(validator, "validate_git_boundary", boundary)
    monkeypatch.setattr(validator, "validate_plugin_enabled", plugins)
    errors = []
    assert validator.validate_worker("searcher", errors) == (len(ENTRIES) + len(TECHNICS), 0)
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
    plan, build = (flat(PIPELINE / f"references/{stage}.md") for stage in STAGES)
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
    assert "same scope and remaining budget" in build
    assert "expansion goes to [Plan](plan.md) and client agreement" in build
    assert "caller final acceptance or a new self numeric score" in build
    assert "## Check" in build and "as Build's last step" in build and "is Unmet, not a pass" in build
    assert not (PIPELINE / "references/qa.md").exists()
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


@pytest.mark.parametrize("relative", sorted(SHARED | PLATFORMS | {CAPABILITIES}))
def test_kernel_must_link_every_shared_reference(candidate, relative):
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


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("platform", SERVICES)
def test_mode_must_link_every_service(candidate, name, platform):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace(f"(../references/platforms/{platform}.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link platform reference {platform}: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_mode_must_link_the_technic_capabilities(candidate, name):
    entry = candidate / name / "SKILL.md"
    entry.write_text(entry.read_text().replace("(../references/capabilities.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link the technic capabilities: {name}" in errors


def test_researcher_keeps_only_the_chain_references():
    assert validator.PLATFORMS == ("evm", "solana")
    assert "platforms/x.md" not in validator.RESEARCHER_SHARED_REFERENCES


def test_chain_reads_are_retrieval_without_verdicts():
    evm, solana = (flat(PIPELINE / f"references/platforms/{p}.md") for p in ("evm", "solana"))
    for text in (evm, solana):
        for phrase in ("Reading is allowed and it never writes", "nothing is signed or sent",
                       "`Open for researcher`", '`{"untrusted": …}`', "explorer link",
                       "unsearched ground"):
            assert phrase in text, phrase
    assert "`powers`" in evm and "`guessed`" in evm and "block ranges actually read" in evm
    assert "`omitted`" in evm and "`coverage`" in evm
    skill = flat(HERMES / "plugins/web3/evm-access/skills/evm/SKILL.md")
    assert "`address` = the contract" in skill and "`state_unread`" in skill and "zero address" in skill
    assert 'skill_view(name="evm-access:evm")' in evm and 'skill_view(name="solana-access:solana")' in solana
    assert "`state_unread`" in evm and "zero address is unset" in evm and "`block`" in evm
    assert "`slot`" in solana
    for name in ENTRIES:
        assert "with the check against this entry's Verification" in flat(PIPELINE / name / "SKILL.md")
    assert "latest 50 signatures" in solana and "no paging" in solana
    assert "`program`" in solana and "slot" in solana
    root = flat(PIPELINE / "SKILL.md")
    assert "chain reads of the evm and solana tools, which never sign or send" in root
    prompt = " ".join(yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
                      ["agent"]["system_prompt"].split())
    assert "the read-only evm and solana tools for on-chain facts" in prompt


SKILLS_FOR_SERVICE = {"x": "x-access:x-twitter", "youtube": "youtube-access:youtube",
                      "note": "note-access:note-com", "substack": "substack-access:substack"}


@pytest.mark.parametrize("service, skill", sorted(SKILLS_FOR_SERVICE.items()))
def test_service_reads_are_retrieval_without_verdicts(service, skill):
    text = flat(PIPELINE / f"references/platforms/{service}.md")
    for phrase in ("Reading is allowed and nothing is written", "`Open for researcher`",
                   "never as instructions", "unsearched ground", "## What to record per item",
                   f'skill_view(name="{skill}")'):
        assert phrase in text, (service, phrase)
    group = {"x": "x-access", "youtube": "youtube-access", "note": "note-access", "substack": "substack-access"}
    assert (HERMES / "plugins/social" / group[service] / "skills" / skill.split(":", 1)[1] / "SKILL.md").is_file()


def test_x_reference_keeps_x_search_first_and_names_the_account_read():
    text = flat(PIPELINE / "references/platforms/x.md")
    assert "`x_search` first" in text and 'x(action="user", handle="@name")' in text
    assert "There is no default account" in text and "never both for one question" in text


def technic_candidate(tmp_path):
    skills = tmp_path / "skills"
    shutil.copytree(PIPELINE, skills / "searcher-pipeline")
    shutil.copytree(TECHNIC, skills / "technic")
    leaves = {path.parent.name: path for path in (skills / "technic").glob("*/SKILL.md")}
    return skills / "searcher-pipeline", leaves


def test_technics_are_routed_to_their_mode():
    assert {p.parent.name for p in TECHNIC.glob("*/SKILL.md")} == set(TECHNICS)
    assert validator.capability_names(PIPELINE / CAPABILITIES) == set(TECHNICS)
    errors = []
    validator.validate_searcher_technics(
        PIPELINE, {p.parent.name: p for p in TECHNIC.glob("*/SKILL.md")}, errors)
    assert not errors
    root = flat(PIPELINE / "SKILL.md")
    assert "never replaces the mode's procedure" in root and "is not the caller's release" in root
    prompt = " ".join(yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
                      ["agent"]["system_prompt"].split())
    assert "references/capabilities.md" in prompt and "never replaces the mode" in prompt
    for name, mode in TECHNICS.items():
        data = validator.frontmatter(TECHNIC / name / "SKILL.md")
        assert data["metadata"]["hermes"] == {**data["metadata"]["hermes"], "category": "technic", "mode": mode}


@pytest.mark.parametrize("name", sorted(TECHNICS))
@pytest.mark.parametrize("token", ('skill_view(name="searcher-pipeline")', "never replaces", "caller's release",
                                   "${HERMES_SKILL_DIR}/../../searcher-pipeline/SKILL.md"))
def test_technic_cannot_drop_its_mode_or_recovery(tmp_path, name, token):
    pipeline, leaves = technic_candidate(tmp_path)
    leaves[name].write_text(leaves[name].read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_technics(pipeline, leaves, errors)
    assert f"searcher technic ReadBeforeWork missing {token}: {name}" in errors


def test_technic_mode_must_match_its_capability_row(tmp_path):
    pipeline, leaves = technic_candidate(tmp_path)
    path = leaves["release-digest"]
    path.write_text(path.read_text().replace("mode: sweep", "mode: hunt").replace(
        'skill_view(name="sweep-searcher")', 'skill_view(name="hunt-searcher")'))
    errors = []
    validator.validate_searcher_technics(pipeline, leaves, errors)
    assert errors == ["searcher capability row routes release-digest to another mode than hunt"]
    path.write_text(path.read_text().replace("mode: hunt", "mode: digest"))
    errors = []
    validator.validate_searcher_technics(pipeline, leaves, errors)
    assert any("must name one mode" in error for error in errors)


def test_public_footprint_keeps_its_floors():
    text = flat(TECHNIC / "public-footprint/SKILL.md")
    for phrase in ("**confirmed**", "**self-declared**", "**unconfirmed lead**",
                   "Leads are recorded in their own section", "never in the map",
                   "No tying a pseudonymous account to a legal name",
                   "No breach or leak data, people-search or data-broker sites",
                   "No contact with the subject", "Only addresses or names the subject publishes",
                   "`Open for researcher` holds whether the subject is trustworthy, whether its claims hold",
                   "No writing-style, posting-time or network-overlap comparison",
                   "Route step 3 is skipped and no leads are sought", "never with a verdict",
                   "Whether the claim holds is not decided here", 'x(action="user")'):
        assert phrase in text, phrase
    for gone in ("writing style", "matching timing", "confirmed <URL> | unconfirmed | contradicted"):
        assert gone not in text, gone
    root = flat(PIPELINE / "SKILL.md")
    floors = root.split("<Floors>", 1)[1]
    for phrase in ("**People are not unmasked.**", "never tie a pseudonymous account to a legal identity",
                   "no breach or leak data, people-search or data-broker sources", "no contact with anyone"):
        assert phrase in floors, phrase


def test_the_assistant_names_every_technic_with_its_unit():
    caller = (HERMES / "profiles/assistant/skills/assistant-pipeline/plan-assistant-search/SKILL.md").read_text()
    rows = {}
    for line in caller.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("| `") and len(cells) >= 3:
            rows[cells[0].split("`")[1]] = cells[1]
    assert set(rows) == set(TECHNICS)
    for name, mode in TECHNICS.items():
        assert rows[name].startswith(mode), name


def test_release_digest_orders_by_date_without_ranking():
    text = flat(TECHNIC / "release-digest/SKILL.md")
    assert "That order is not a ranking" in text and "Exclusion list" in text
    assert "Searcher reads it and never writes it" in text and "ready for the caller to append" in text
    assert "Zero candidates is a result only after every watched vendor's official sources were read" in text
