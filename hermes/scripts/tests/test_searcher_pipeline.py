import importlib.util
import re
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import hermes_yaml as yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/searcher/skills/pipeline"
TECHNIC = HERMES / "profiles/searcher/skills/technic"
spec = importlib.util.spec_from_file_location("searcher_topology", HERMES / "scripts/validate-profile-skills.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

MODES = ("lookup", "sweep", "hunt")
STAGES = ("plan", "build")
STAGE_SECTIONS = {"plan": ("## Plan", "## Handoff"),
                  "build": ("## Build", "## Output template", "## Verification", "## Handoff")}
# {declared name: (mode, stage)} and the path of each entry under the pipeline.
STAGE_ENTRIES = {f"{stage}-{mode}": (mode, stage) for mode in MODES for stage in STAGES}
ENTRIES = tuple(STAGE_ENTRIES)
ENTRY_PATHS = {name: f"{mode}/{stage}/SKILL.md" for name, (mode, stage) in STAGE_ENTRIES.items()}
RETIRED_ENTRIES = tuple(f"{mode}-searcher/SKILL.md" for mode in MODES)
SERVICES = ("x", "youtube", "note", "substack", "evm", "solana", "hyperliquid")
PLATFORMS = {f"references/platforms/{p}.md" for p in SERVICES}
CAPABILITIES = "references/capabilities.md"
TECHNICS = {"public-footprint": "hunt", "primary-fact-pack": "lookup", "release-digest": "sweep"}


def flat(path):
    return " ".join(Path(path).read_text().split())


def kernel_section(tag):
    """The flattened text of the kernel's <Plan> or <Build> section."""
    body = (PIPELINE / "SKILL.md").read_text()
    match = re.search(rf"<{tag}>(.*?)</{tag}>", body, re.S)
    assert match, tag
    return " ".join(match.group(1).split())


def test_exact_entries_and_owned_procedures():
    errors = []
    found = validator.validate_searcher_entries(PIPELINE, errors)
    assert not errors
    assert set(found) == set(ENTRIES)
    assert {p.relative_to(PIPELINE).as_posix() for p in PIPELINE.rglob("*.md")} == {
        "SKILL.md", *ENTRY_PATHS.values(), *PLATFORMS, CAPABILITIES,
    }
    for name, (mode, stage) in STAGE_ENTRIES.items():
        text = found[name].read_text()
        for section in STAGE_SECTIONS[stage]:
            assert section in text, (name, section)
        other = "build" if stage == "plan" else "plan"
        assert f"(../{other}/SKILL.md)" in text
        assert text.index("<ReadBeforeWork>") < text.index("# " + mode.title())
        assert text.index("\n---\n", 4) < 4000
    for name, marker in (("build-lookup", "### Steps"), ("build-sweep", "### Measurement variant"),
                         ("build-hunt", "### Hop loop")):
        assert marker in found[name].read_text()
    root = (PIPELINE / "SKILL.md").read_text()
    assert "version: 12.0.0" in root and root.index("\n---\n", 4) < 4000
    assert "<Procedure>" not in root
    assert "<Plan>" in root and "<Build>" in root
    for relative in ENTRY_PATHS.values():
        assert f"({relative})" in root
    for relative in PLATFORMS | {CAPABILITIES}:
        assert f"({relative})" in root


def test_profile_selection_contract_and_unchanged_tool_surface():
    config = yaml.safe_load((HERMES / "profiles/searcher/config.example.yaml").read_text())
    prompt = " ".join(config["agent"]["system_prompt"].split())
    assert "first message is the brief" not in prompt.lower()
    assert "Purpose alone is not execution authority" in prompt
    assert "<stage>-<mode>" in prompt
    for gone in ("plan-searcher", "build-searcher", "qa-searcher",
                 *(f"{mode}-searcher" for mode in MODES), "references/<stage>.md"):
        assert gone not in prompt
    for phrase in (
        "every caller, resume or completion turn", "midturn",
        "full searcher-pipeline kernel", "not a past load, summary or root preload",
        "unchanged", "earlier body is unavailable", "read_file", "next_offset",
        "stop the affected search", "caller's release",
        "Plan / Build mechanics",
    ):
        assert phrase in prompt
    assert "Workflow v5" not in prompt
    for gone in ("goal_mode", "kanban_show", "kanban_complete", "survey-enumeration",
                 "exhaustive-hunt", "STATE:", "DECISION(", "card gate"):
        assert gone not in prompt
    social = {"x_access", "youtube_access", "note_access", "substack_access"}
    chains = {"evm_access", "solana_access", "hyperliquid_access"}
    assert set(config["toolsets"]) == {"file", "web", "x_search", "skills", "memory"} | social | chains
    assert set(config["platform_toolsets"]["cli"]) == {
        "file", "web", "x_search", "skills", "memory", "no_mcp", "connections"} | social | chains
    assert {"x-access", "youtube-access", "note-access", "substack-access",
            "evm-access", "solana-access", "hyperliquid-access"} <= set(config["plugins"]["enabled"])
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
        block = (PIPELINE / ENTRY_PATHS[name]).read_text().split("</ReadBeforeWork>", 1)[0]
        assert "Direct entry requires" in block and "card gate" not in block
        block = " ".join(block.split())
        assert "does not restart coverage or the frontier, reset a budget" in block
        assert "caller's release" in block
        assert "${HERMES_SKILL_DIR}/../../SKILL.md" in block


@pytest.fixture
def candidate(tmp_path):
    return Path(shutil.copytree(PIPELINE, tmp_path / "pipeline"))


@pytest.mark.parametrize("relative", (*ENTRY_PATHS.values(), *sorted(PLATFORMS | {CAPABILITIES})))
def test_missing_instruction_fails(candidate, relative):
    (candidate / relative).unlink()
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"missing searcher document: {relative}" in errors


@pytest.mark.parametrize("token", (
    'skill_view(name="searcher-pipeline")', "past load", "read_file", "next_offset", "stop",
    "current context", "${HERMES_SKILL_DIR}/../../SKILL.md", "${HERMES_SKILL_DIR}/SKILL.md",
))
@pytest.mark.parametrize("name", ENTRIES)
def test_direct_entry_cannot_drop_dependency_or_recovery(candidate, token, name):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry missing dependency/recovery {token}: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_direct_entry_cannot_drop_its_own_name_or_stage_tag(candidate, name):
    mode, stage = STAGE_ENTRIES[name]
    entry = candidate / ENTRY_PATHS[name]
    for token in (f'skill_view(name="{name}")', f"<{stage.capitalize()}>"):
        entry.write_text(entry.read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    for token in (f'skill_view(name="{name}")', f"<{stage.capitalize()}>"):
        assert f"searcher entry missing dependency/recovery {token}: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_direct_entry_cannot_drop_the_full_body_reuse_contract(candidate, name):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace("full-body", "removed"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry missing full-body reuse contract: {name}" in errors


@pytest.mark.parametrize("replacement, expected", (
    (("name: build-lookup", "name: alternate-lookup"), "frontmatter name must be build-lookup"),
    (("category: pipeline", "category: technic"), "metadata.hermes.category must be pipeline"),
    (("Lookup, Build stage", "Generic, Build stage"), "searcher description must frontload lookup"),
    (("Lookup, Build stage", "Lookup, final stage"), "searcher description must frontload lookup and name the build stage"),
    (("version: 1.0.0", "version: ''"), "searcher entry needs a version"),
))
def test_entry_metadata_is_validated(candidate, replacement, expected):
    entry = candidate / "lookup/build/SKILL.md"
    text = entry.read_text()
    assert replacement[0] in text
    entry.write_text(text.replace(*replacement))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


@pytest.mark.parametrize("relative", (
    "references/lookup.md", "references/plan.md", "references/build.md", "tests/fixture/SKILL.md",
    "fourth/plan/SKILL.md", "lookup/plan/notes.txt", "sweep/build/scripts/probe.sh",
    "lookup/SKILL.md", "plan-searcher/SKILL.md", "build-searcher/SKILL.md", "qa-searcher/SKILL.md",
    *RETIRED_ENTRIES, "lookup-searcher/references/lookup.md", ".editor/SKILL.md",
))
def test_old_alias_or_unexpected_instruction_fails(candidate, relative):
    path = candidate / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Not an authorized instruction\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"unexpected searcher document: {relative}" in errors


def test_incidental_dotfiles_do_not_change_topology(candidate):
    for relative in (".DS_Store", "lookup/build/.SKILL.md.swp", ".editor/state"):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Editor metadata\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert not errors


@pytest.mark.parametrize("relative", ("SKILL.md", "hunt/build/SKILL.md", "hunt/plan/SKILL.md"))
def test_goal_mode_cannot_return_without_cards(candidate, relative):
    path = candidate / relative
    path.write_text(path.read_text() + "\nEach judge turn is one hop under goal_mode.\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any("has no goal_mode" in error and str(path) in error for error in errors)


@pytest.mark.parametrize("link, expected", (
    ("missing.md", "broken searcher link"),
    ("../../../outside.md", "searcher link escapes pipeline"),
))
def test_links_are_contained_and_real(candidate, link, expected):
    entry = candidate / "lookup/build/SKILL.md"
    entry.write_text(entry.read_text() + f"\n[bad]({link})\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert any(expected in error for error in errors)


def test_nested_symlink_cannot_hide_instructions(candidate):
    (candidate / "hidden").symlink_to(candidate / "lookup", target_is_directory=True)
    errors = []
    assert validator.validate_searcher_entries(candidate, errors) == {}
    assert any("searcher pipeline must not contain symlinks" in error for error in errors)


@pytest.mark.parametrize("name", ENTRIES)
def test_worker_wires_entries_and_detects_learned_collision(tmp_path, monkeypatch, name):
    skills = tmp_path / "profiles/searcher/skills"
    shutil.copytree(PIPELINE, skills / "pipeline")
    shutil.copytree(TECHNIC, skills / "technic")
    monkeypatch.setattr(validator, "HERMES_ROOT", tmp_path)
    # Learned skills live in the profile HOME, beside the links into the tree.
    home = tmp_path / ".hermes"
    monkeypatch.setattr(validator, "HERMES_HOME_ROOT", home)
    # No private overlay for the fixture: only the example config is checked.
    monkeypatch.setattr(validator, "PRIVATE_OVERLAY", tmp_path / "private")
    # Isolate this structural fixture, while proving the normal ownership/plugin
    # checks are still called by the worker path (the full CLI tests them separately).
    boundary, plugins = Mock(), Mock()
    monkeypatch.setattr(validator, "validate_git_boundary", boundary)
    monkeypatch.setattr(validator, "validate_plugin_enabled", plugins)
    errors = []
    assert validator.validate_worker("searcher", errors) == (len(ENTRIES) + len(TECHNICS), 0)
    assert len(ENTRIES) == 6
    assert not errors
    boundary.assert_called_once()
    plugins.assert_called_once()
    learned = home / "profiles/searcher/skills/learned" / name
    learned.mkdir(parents=True)
    (learned / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Collision\n---\n")
    errors = []
    validator.validate_worker("searcher", errors)
    assert f"duplicate searcher skill name: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_frontmatter_must_fit_runtime_prefix(candidate, name):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace("author: CraftSamo", "padding: " + "x" * 4000 + "\nauthor: CraftSamo"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher frontmatter exceeds discovery prefix: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
@pytest.mark.parametrize("section", ("## Plan", "## Build", "## Output template", "## Verification", "## Handoff"))
def test_stage_entry_must_own_its_stage_sections(candidate, name, section):
    _, stage = STAGE_ENTRIES[name]
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace(f"\n{section}\n", "\n## Removed\n"))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    message = f"searcher entry missing {section}: {name}"
    assert (message in errors) == (section in STAGE_SECTIONS[stage])


@pytest.mark.parametrize("tag", ("Plan", "Build"))
def test_kernel_must_own_both_stages(candidate, tag):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"</{tag}>", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher kernel must own the <{tag}> stage" in errors


@pytest.mark.parametrize("tag", ("Plan", "Build"))
def test_kernel_stage_owns_its_mechanics(tag):
    text = kernel_section(tag)
    if tag == "Plan":
        assert "Plan's reply uses this template:" in text and "Agreement needed:" in text
    else:
        for phrase in ("Checked:", "Unmet:", "Unverified:", "Budget / continuity:", "**Check.**"):
            assert phrase in text


def test_declared_policy_not_model_routing_compliance():
    root = flat(PIPELINE / "SKILL.md")
    plan, build = kernel_section("Plan"), kernel_section("Build")
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
    assert "expansion goes to Plan and client agreement" in build
    assert "caller final acceptance or a new self numeric score" in build
    assert "**Check.**" in build and "as Build's last step" in build and "is Unmet, not a pass" in build
    assert not (PIPELINE / "references/qa.md").exists()
    assert "Interpreted as:" in build and "direct settled briefs" in build
    assert "valid cards" not in build
    assert "A stop needs a true reason" in build


@pytest.mark.parametrize("name", ENTRIES)
def test_kernel_must_route_every_stage_entry(candidate, name):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"({ENTRY_PATHS[name]})", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher kernel does not route {name}" in errors


@pytest.mark.parametrize("relative", sorted(PLATFORMS | {CAPABILITIES}))
def test_kernel_must_link_every_shared_reference(candidate, relative):
    root = candidate / "SKILL.md"
    root.write_text(root.read_text().replace(f"({relative})", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher kernel does not link reference: {relative.removeprefix('references/')}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_stage_entry_must_link_its_sibling_stage(candidate, name):
    _, stage = STAGE_ENTRIES[name]
    other = "build" if stage == "plan" else "plan"
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace(f"(../{other}/SKILL.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link its {other} stage: {name}" in errors


@pytest.mark.parametrize("name", [n for n in ENTRIES if STAGE_ENTRIES[n][1] == "build"])
@pytest.mark.parametrize("platform", SERVICES)
def test_build_entry_must_link_every_service(candidate, name, platform):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace(f"(../../references/platforms/{platform}.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link platform reference {platform}: {name}" in errors


@pytest.mark.parametrize("name", [n for n in ENTRIES if STAGE_ENTRIES[n][1] == "plan"])
@pytest.mark.parametrize("reference", ("references/platforms/x.md", "references/gather.md"))
def test_plan_entry_reads_supplied_material_only(candidate, name, reference):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text() + f"\nSee {reference}.\n")
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher plan entry reads supplied material only: {name}" in errors


@pytest.mark.parametrize("name", ENTRIES)
def test_mode_must_link_the_technic_capabilities(candidate, name):
    entry = candidate / ENTRY_PATHS[name]
    entry.write_text(entry.read_text().replace("(../../references/capabilities.md)", ""))
    errors = []
    validator.validate_searcher_entries(candidate, errors)
    assert f"searcher entry does not link the technic capabilities: {name}" in errors


def test_researcher_keeps_only_the_chain_and_venue_references():
    assert validator.PLATFORMS == ("evm", "solana", "hyperliquid")
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
        if STAGE_ENTRIES[name][1] == "build":
            assert "with the check against this entry's Verification" in flat(PIPELINE / ENTRY_PATHS[name])
    assert "latest 50 signatures" in solana and "no paging" in solana
    assert "`program`" in solana and "slot" in solana
    root = flat(PIPELINE / "SKILL.md")
    assert "chain reads of the evm and solana tools, which never sign or send" in root
    prompt = " ".join(yaml.safe_load((HERMES / "profiles/searcher/config.example.yaml").read_text())
                      ["agent"]["system_prompt"].split())
    assert "the read-only evm and solana tools for on-chain facts" in prompt


def test_venue_reads_are_retrieval_without_verdicts():
    text = flat(PIPELINE / "references/platforms/hyperliquid.md")
    for phrase in ("Reading is allowed and it never writes", "nothing is signed or sent", "`Open for researcher`",
                   '`{"untrusted": …}`', "explorer link", "unsearched ground", "network and time",
                   'skill_view(name="hyperliquid-access:hyperliquid")'):
        assert phrase in text, phrase
    assert "venue reads of the hyperliquid tool, which never trades" in flat(PIPELINE / "SKILL.md")
    assert (HERMES / "plugins/web3/hyperliquid-access/skills/hyperliquid/SKILL.md").is_file()


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
    shutil.copytree(PIPELINE, skills / "pipeline")
    shutil.copytree(TECHNIC, skills / "technic")
    leaves = {path.parent.name: path for path in (skills / "technic").glob("*/SKILL.md")}
    return skills / "pipeline", leaves


def test_technics_are_routed_to_their_mode():
    assert {p.parent.name for p in TECHNIC.glob("*/SKILL.md")} == set(TECHNICS)
    assert validator.capability_names(PIPELINE / CAPABILITIES) == set(TECHNICS)
    errors = []
    validator.validate_searcher_technics(
        PIPELINE, {p.parent.name: p for p in TECHNIC.glob("*/SKILL.md")}, errors)
    assert not errors
    root = flat(PIPELINE / "SKILL.md")
    assert "never replaces the mode's procedure" in root and "is not the caller's release" in root
    prompt = " ".join(yaml.safe_load((HERMES / "profiles/searcher/config.example.yaml").read_text())
                      ["agent"]["system_prompt"].split())
    assert "references/capabilities.md" in prompt and "never replaces the mode" in prompt
    for name, mode in TECHNICS.items():
        data = validator.frontmatter(TECHNIC / name / "SKILL.md")
        assert data["metadata"]["hermes"] == {**data["metadata"]["hermes"], "category": "technic", "mode": mode}


@pytest.mark.parametrize("name", sorted(TECHNICS))
@pytest.mark.parametrize("token", ('skill_view(name="searcher-pipeline")', "never replaces", "caller's release",
                                   "${HERMES_SKILL_DIR}/../../pipeline/SKILL.md"))
def test_technic_cannot_drop_its_mode_or_recovery(tmp_path, name, token):
    pipeline, leaves = technic_candidate(tmp_path)
    leaves[name].write_text(leaves[name].read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_technics(pipeline, leaves, errors)
    assert f"searcher technic ReadBeforeWork missing {token}: {name}" in errors


@pytest.mark.parametrize("name", sorted(TECHNICS))
def test_technic_loads_the_stage_entries_of_its_mode(tmp_path, name):
    pipeline, leaves = technic_candidate(tmp_path)
    token = f'skill_view(name="<stage>-{TECHNICS[name]}")'
    assert token in leaves[name].read_text()
    leaves[name].write_text(leaves[name].read_text().replace(token, "removed"))
    errors = []
    validator.validate_searcher_technics(pipeline, leaves, errors)
    assert f"searcher technic ReadBeforeWork missing {token}: {name}" in errors
    assert 'file_path="references/<stage>.md"' not in leaves[name].read_text()


def test_technic_mode_must_match_its_capability_row(tmp_path):
    pipeline, leaves = technic_candidate(tmp_path)
    path = leaves["release-digest"]
    path.write_text(path.read_text().replace("mode: sweep", "mode: hunt").replace(
        'skill_view(name="<stage>-sweep")', 'skill_view(name="<stage>-hunt")'))
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
    caller = (HERMES / "profiles/assistant/skills/pipeline/search/plan/SKILL.md").read_text()
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
