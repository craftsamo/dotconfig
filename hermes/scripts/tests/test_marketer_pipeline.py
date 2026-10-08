from __future__ import annotations

import importlib.util
import json
import shlex
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import hermes_yaml as yaml


HERMES = Path(__file__).resolve().parents[2]
ROOT = HERMES / "profiles/marketer/skills/marketer-pipeline"
SPEC = importlib.util.spec_from_file_location("marketer_validator", HERMES / "scripts/validate-profile-skills.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

# Split, flat advisory entries: no mode/domain matrix like the Assistant pipeline.
ENTRIES = ("plan-marketer", "review-marketer", "analyze-marketer")

DEPENDENCY_TOKENS = (
    'skill_view(name="marketer-pipeline")',
    "${HERMES_SKILL_DIR}/../SKILL.md",
    "${HERMES_SKILL_DIR}/SKILL.md",
    "read_file",
    "next_offset",
)

# (label, needle, replacement) - each needle appears exactly once inside the
# entry's <ReadBeforeWork> block; replacing it removes the matching recovery
# regex's only anchor without disturbing the other checks.
RECOVERY_BREAKS = (
    ("full-body reuse", "the current context", "the ongoing scope"),
    ("not a summary", "never a past load or summary", "never an outdated load or overview"),
    ("per-turn selection", "each user turn or completion", "each user turn or handoff"),
    ("midturn selection", "before a mode, target, platform or scope-changing action",
     "before a mode, target, platform or boundary-changing step"),
    ("missing body recovery", "the earlier body is unavailable", "the earlier body is retired"),
    ("stop on missing body", "body remains missing, stop", "body remains missing, halt"),
    ("preserve grants", "expand a grant", "extend permission"),
)


def text(relative):
    return " ".join((ROOT / relative).read_text().split())


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    root = tmp_path / "profiles/marketer/skills/marketer-pipeline"
    shutil.copytree(ROOT, root)
    monkeypatch.setattr(VALIDATOR, "HERMES_ROOT", tmp_path)
    return root


def errors(root):
    result = []
    VALIDATOR.validate_marketer_references(root, result)
    return result


def entries_and_errors(root):
    result = []
    found = VALIDATOR.validate_marketer_references(root, result)
    return found, result


def edit_frontmatter(path: Path, **overrides: Any) -> None:
    raw = path.read_text(encoding="utf-8")
    end = raw.index("\n---\n", 4)
    data = yaml.safe_load(raw[4:end])
    body = raw[end + 5:]
    data.update(overrides)
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\n" + body, encoding="utf-8")


def strip_read_before_work_token(path: Path, token: str) -> None:
    doc = path.read_text(encoding="utf-8")
    match = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", doc, re.S)
    block = match.group(1)
    corrupted = block.replace(token, "REDACTED", 1)
    doc = doc[: match.start(1)] + corrupted + doc[match.end(1):]
    path.write_text(doc, encoding="utf-8")


def test_four_roots_and_three_entries_returned(candidate):
    entries, found = entries_and_errors(candidate)
    assert found == []
    roots = sorted(p.relative_to(candidate).as_posix() for p in candidate.rglob("SKILL.md"))
    assert roots == sorted(["SKILL.md"] + [f"{name}/SKILL.md" for name in ENTRIES])
    assert set(entries) == set(ENTRIES)
    for name in ENTRIES:
        assert entries[name] == candidate / name / "SKILL.md"


def test_fifteen_reference_files_all_present(candidate):
    assert len(VALIDATOR.MARKETER_REFERENCE_FILES) == 15
    for relative in VALIDATOR.MARKETER_REFERENCE_FILES:
        assert (candidate / relative).is_file(), relative
    assert errors(candidate) == []


@pytest.mark.parametrize("relative", sorted(VALIDATOR.MARKETER_REFERENCE_FILES))
def test_missing_reference_fails(candidate, relative):
    (candidate / relative).unlink()
    assert any(f"missing marketer reference: {relative}" in e for e in errors(candidate))


@pytest.mark.parametrize("link", ["../../../../missing.md", "../../scripts/missing.py"])
def test_broken_and_escaping_links_fail(candidate, link):
    doc = candidate / "plan-marketer/references/discovery.md"
    doc.write_text(doc.read_text() + f"\n[bad]({link})\n")
    assert any("reference escapes" in e or "broken marketer reference" in e for e in errors(candidate))


def test_old_publish_engine_and_duplicate_mode_platforms_fail(candidate):
    (candidate / "references/publish.md").write_text("# Old publishing\n")
    assert "unexpected marketer reference: references/publish.md" in errors(candidate)


@pytest.mark.parametrize("entry, reference", [("build-marketer", "draft.md"), ("qa-marketer", "saved-draft.md")])
def test_retired_draft_entries_fail(candidate, entry, reference):
    path = candidate / entry / "references" / reference
    path.parent.mkdir(parents=True)
    path.write_text("# Retired\n")
    (candidate / entry / "SKILL.md").write_text(f"---\nname: {entry}\n---\n")
    found = errors(candidate)
    assert f"unexpected marketer skill root: {entry}/SKILL.md" in found
    assert f"unexpected marketer reference: {entry}/references/{reference}" in found


def test_pipeline_v8_needs_the_advisory_version(candidate):
    edit_frontmatter(candidate / "SKILL.md", version="8.0.0")
    assert "marketer advisory entries require pipeline version 9 or later" in errors(candidate)


def test_unlinked_reference_fails(candidate):
    kernel = candidate / "SKILL.md"
    kernel.write_text(kernel.read_text().replace("[state](references/state.md)", "state"))
    assert "marketer root does not link reference: state.md" in errors(candidate)


@pytest.mark.parametrize("entry", ENTRIES)
def test_root_unlinking_entry_route_fails(candidate, entry):
    kernel = candidate / "SKILL.md"
    doc = kernel.read_text(encoding="utf-8")
    needle = f"[{entry}]({entry}/SKILL.md)"
    assert needle in doc
    kernel.write_text(doc.replace(needle, entry), encoding="utf-8")
    assert any(f"marketer root does not route entry: {entry}" in e for e in errors(candidate))


def test_legacy_version_remains_valid_without_new_tree(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: marketer-pipeline\nversion: 6.0.0\n---\n")
    assert errors(tmp_path) == []


def test_nested_rogue_skill_md_fails(candidate):
    rogue = candidate / "plan-marketer/references/rogue/SKILL.md"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("---\nname: rogue\n---\n")
    assert any(
        "unexpected marketer skill root: plan-marketer/references/rogue/SKILL.md" in e
        for e in errors(candidate)
    )


def test_pipeline_symlink_fails(candidate):
    target = candidate / "references/state.md"
    link = candidate / "references/state-link.md"
    link.symlink_to(target)
    assert any("marketer pipeline must not contain symlinks" in e for e in errors(candidate))


@pytest.mark.parametrize("relative", ["references/notes.txt", "plan-marketer/references/notes.txt"])
def test_non_markdown_reference_fails(candidate, relative):
    path = candidate / relative
    path.write_text("not markdown")
    assert any("non-markdown marketer reference" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_wrong_name_fails(candidate, entry):
    path = candidate / entry / "SKILL.md"
    edit_frontmatter(path, name="wrong-name")
    assert any(f"frontmatter name must be {entry}" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_wrong_category_fails(candidate, entry):
    path = candidate / entry / "SKILL.md"
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw[4:raw.index("\n---\n", 4)])
    data["metadata"]["hermes"]["category"] = "writing"
    edit_frontmatter(path, metadata=data["metadata"])
    assert any("metadata.hermes.category must be marketer-pipeline" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_bad_description_fails(candidate, entry):
    path = candidate / entry / "SKILL.md"
    edit_frontmatter(path, description="Not prefixed with the phase at all.")
    prefix = f"{entry.split('-', 1)[0]} marketing"
    assert any(f"marketer entry description must frontload {prefix}: {entry}" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("version", [1, "", "   "])
def test_entry_bad_version_fails(candidate, entry, version):
    path = candidate / entry / "SKILL.md"
    edit_frontmatter(path, version=version)
    assert any(f"marketer entry version must be a nonempty string: {entry}" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("token", DEPENDENCY_TOKENS)
def test_entry_missing_dependency_token_fails(candidate, entry, token):
    path = candidate / entry / "SKILL.md"
    strip_read_before_work_token(path, token)
    assert any(
        f"marketer entry missing dependency/recovery {token}: {entry}" in e for e in errors(candidate)
    )


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("label, needle, replacement", RECOVERY_BREAKS)
def test_entry_missing_recovery_condition_fails(candidate, entry, label, needle, replacement):
    path = candidate / entry / "SKILL.md"
    doc = path.read_text(encoding="utf-8")
    pattern = re.compile(r"\s+".join(re.escape(word) for word in needle.split()))
    doc, count = pattern.subn(replacement, doc, count=1)
    assert count == 1
    path.write_text(doc, encoding="utf-8")
    assert any(
        f"marketer entry ReadBeforeWork missing {label}: {entry}" in e for e in errors(candidate)
    )


@pytest.mark.parametrize("entry, label, filename", [
    ("review-marketer", "content review", "content.md"),
    ("analyze-marketer", "measurement", "measurement.md"),
    ("plan-marketer", "strategy check", "strategy.md"),
])
def test_entry_unlinking_own_detail_fails(candidate, entry, label, filename):
    path = candidate / entry / "SKILL.md"
    doc = path.read_text(encoding="utf-8")
    needle = f"[{label}](references/{filename})"
    assert needle in doc
    path.write_text(doc.replace(needle, label), encoding="utf-8")
    assert any(f"marketer entry does not link reference: {entry}: {filename}" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_unlinking_shared_browsing_fails(candidate, entry):
    path = candidate / entry / "SKILL.md"
    doc = path.read_text(encoding="utf-8")
    needle = "[browsing](../references/browsing.md)"
    assert needle in doc
    path.write_text(doc.replace(needle, "browsing"), encoding="utf-8")
    assert any(f"marketer entry does not link reference: {entry}: browsing.md" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_entry_unlinking_shared_platform_route_fails(candidate, entry):
    path = candidate / entry / "SKILL.md"
    doc = path.read_text(encoding="utf-8")
    needle = "[Zenn](../references/platforms/zenn.md)"
    assert needle in doc
    path.write_text(doc.replace(needle, "Zenn"), encoding="utf-8")
    assert any(f"marketer entry does not link reference: {entry}: zenn.md" in e for e in errors(candidate))


@pytest.mark.parametrize("entry", ENTRIES)
def test_unexpected_entry_child_fails(candidate, entry):
    stray = candidate / entry / "notes.md"
    stray.write_text("# Stray\n")
    assert any(f"unexpected marketer entry child: {entry}/notes.md" in e for e in errors(candidate))


def test_validate_worker_accepts_three_entries_and_rejects_unknown_root(candidate, monkeypatch):
    skills = candidate.parent
    (skills / "technic").mkdir()
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    monkeypatch.setattr(VALIDATOR, "validate_plugin_enabled", lambda *args: None)

    found: list[str] = []
    assert VALIDATOR.validate_worker("marketer", found) == (3, 0)
    assert found == []

    rogue = skills / "rogue" / "SKILL.md"
    rogue.parent.mkdir()
    rogue.write_text("---\nname: rogue\n---\n")
    found = []
    VALIDATOR.validate_worker("marketer", found)
    assert any("unexpected skill root" in error for error in found)


def test_actual_config_is_a_read_only_advisor():
    config = yaml.safe_load((HERMES / "profiles/marketer/config.yaml").read_text())
    assert config["specialist_call"]["resident_targets"] == ["researcher"]
    assert set(config["a2a_agents"]) == {"researcher"}
    assert config["a2a_agents"]["researcher"]["timeout"] == 310
    assert "specialist-call" in config["plugins"]["enabled"]
    assert "a2a" not in config["toolsets"]
    assert config["platforms"]["a2a"]["enabled"] is True
    assert config["platforms"]["telegram"]["enabled"] is True
    for platform in ("cli", "telegram", "a2a"):
        tools = config["platform_toolsets"][platform]
        assert "specialist" in tools and "a2a" not in tools and "no_mcp" in tools
        for reader in ("x_access", "x_search", "substack_access", "youtube_access", "note_access", "web"):
            assert reader in tools
        if platform == "a2a":
            assert not {"browser", "terminal", "delegation"} & set(tools)
        else:
            assert "browser" in tools and "terminal" in tools
    assert "clarify" in config["platform_toolsets"]["telegram"]
    assert config["browser"]["use_real_profile"] is True
    assert config["browser"]["real_profile_pin"] == "Profile 13"
    # Writer's pipeline is no longer read: the client owns acceptance.
    assert config["skills"]["external_dirs"] == [
        "~/.config/private/hermes/skills/operations/hermes-browser-relaunch",
    ]
    assert config["skills"]["disabled"] == []
    prompt = " ".join(config["agent"]["system_prompt"].split())
    for name in ENTRIES:
        assert name in prompt
    for retired in ("build-marketer", "qa-marketer", "save package", "remote-save approval"):
        assert retired not in prompt
    assert "Each user turn or specialist completion, select" in prompt
    assert "Re-evaluate before a mode, target, platform or scope-changing action" in prompt
    assert ("Reuse the full marketer-pipeline kernel and selected entry only while "
            "their bodies are in current context") in prompt
    assert "never from a past load, preload label or summary alone" in prompt
    assert "You are an advisor" in prompt
    assert "Read-only toward every service, even before skill loading" in prompt
    assert "enter an editor or composer, create or save a draft" in prompt
    assert "Old Publish/P1 grants and old draft jobs authorize nothing" in prompt
    assert "Inbound A2A is inquiry-only" in prompt
    assert "Acquire the pipeline's profile-wide browser lease before any navigation" in prompt
    assert "Use specialist_call/specialist_session only for researcher" in prompt
    assert "Before a conversation ends, keep what should outlast it" in prompt
    tools = config["timeouts"]["tools"]
    assert tools["sequential_call"] == tools["concurrent_batch"] == 5460


def test_direct_client_discovery_and_bounded_requests():
    kernel = text("SKILL.md")
    assert "the Assistant, Creator and the human" in kernel
    assert "A product need not exist at intake" in kernel
    assert "not mandatory consecutive stages" in kernel
    assert "A short question finishes in one reply" in kernel
    discovery = text("plan-marketer/references/discovery.md")
    assert "absent offer is a valid starting state" in discovery
    assert "actual purchase" in discovery
    assert "No automatic outreach" in discovery


def test_kernel_and_entries_never_operate_a_service():
    kernel = text("SKILL.md")
    for boundary in ("Read-only toward the outside world",
                     "enter an editor, save a draft, submit a form",
                     "reach only Researcher",
                     "never a substitute public manuscript"):
        assert boundary in kernel
    for doc in sorted(ROOT.rglob("*.md")):
        body = " ".join(doc.read_text().split())
        for retired in ("save package", "remote-save approval relay", "Commission a clear released unit",
                        "[parts]", "saved-draft QA", "save-approved"):
            assert retired not in body, (doc, retired)
    review = text("review-marketer/SKILL.md")
    assert "This is advice" in review and "a clean review is not acceptance" in review
    assert "their editors, which you never open" in review
    content = text("review-marketer/references/content.md")
    assert "Do not score prose craft, shorten, strengthen, add urgency or run a humanizer" in content
    assert "never a legality guarantee" in content
    assert "never probe a publish, schedule or share control" in content
    plan = text("plan-marketer/SKILL.md")
    assert "Marketer starts none of them" in plan
    assert "brief for the client to commission" in plan
    campaign = text("plan-marketer/references/campaign.md")
    assert "brief it can commission from Writer or Creator" in campaign


def test_browsing_is_read_only_and_leased():
    browsing = text("references/browsing.md")
    for requirement in ("It never writes", "never type into an editor or composer",
                        "never create or open a new draft", "never generate a sharing or preview link",
                        "never submit a form", "holds the profile-wide lease", "No timeout-based stealing",
                        "Any nonzero acquire exit means do not proceed to the browser",
                        "do not assume Python variables or the active tab persist",
                        "is an incident: stop, keep the lease", "inbound A2A inquiry has no browser"):
        assert requirement in browsing, requirement


def test_browsing_resolves_lease_from_kernel_not_shell_environment():
    browsing = (ROOT / "references/browsing.md").read_text()
    commands = re.findall(r"```sh\n(.*?)\n```", browsing, re.S)
    assert len(commands) == 2
    for command, operation in zip(commands, ("acquire", "release")):
        assert "$" not in command
        argv = shlex.split(command.replace("<marketer-pipeline-directory>", str(ROOT)))
        assert Path(argv[1]) == ROOT / "scripts/browser-lease.py"
        assert Path(argv[1]).is_file()
        assert argv[2] == operation


@pytest.mark.parametrize("platform", ["x", "substack", "note", "zenn"])
def test_platform_references_advise_and_read_without_saving(platform):
    reference = text(f"references/platforms/{platform}.md")
    assert "Reviewed 2026-" in reference
    assert "https://" in reference
    assert "the user publishes" in reference.lower() or "the user posts" in reference.lower()
    for retired in ("Browser procedure", "Follow [draft]", "saved-draft QA", "create_draft", "Save by"):
        assert retired not in reference


def test_platform_specific_hazards_survive():
    x = text("references/platforms/x.md")
    assert "per-post approval or draft-only work is not a stated exception" in x
    assert "analytics pages only, never the timeline, composer, notifications or messages" in x
    assert "email delivery are separate effects" in text("references/platforms/substack.md")
    note = text("references/platforms/note.md")
    assert "for Marketer it has no save" in note and "open editor.note.com" in note
    zenn = text("references/platforms/zenn.md")
    assert "notify other members" in zenn
    assert "default scope must be inspected" in zenn
    assert "never open the editor" in zenn


def test_record_keeps_strategy_and_outlasting_lessons():
    state = text("references/state.md")
    assert "Marketer maintains the strategy record" in state
    assert "Write only inside that record location" in state
    assert "Before the conversation ends" in state
    assert "Task state, manuscripts, account records, reader data and approvals never do" in state
    assert "an unfinished save in them goes to the Assistant to reconcile" in state
    kernel = text("SKILL.md")
    assert "Before the conversation ends, keep what should outlast it" in kernel


def test_measurement_does_not_turn_missing_data_into_success():
    measure = text("analyze-marketer/references/measurement.md")
    for state in ("measured zero", "not measured", "retrieval failed", "not comparable"):
        assert state in measure
    assert "Prefer the tools, which need no browser and no lease" in measure
    analysis = text("analyze-marketer/SKILL.md")
    assert "Sparse data remains inconclusive" in analysis
    assert "No universal sample count" in analysis
    assert "Zero changes is legitimate" in analysis
    assert "recommend, never start them" in analysis


def test_real_skill_discovery_and_shared_reference_loading(monkeypatch):
    from tools import skills_tool, skills_tool_plugin

    skills = ROOT.parent
    monkeypatch.setattr(skills_tool, "_skill_search_dirs", lambda: ([], [skills], skills))
    monkeypatch.setattr(skills_tool, "_is_skill_disabled", lambda name, **kwargs: False)
    monkeypatch.setattr(skills_tool, "_get_disabled_skill_names", lambda: set())
    monkeypatch.setattr(skills_tool, "_SKILLS_CACHE", {})
    monkeypatch.setattr(skills_tool_plugin, "_mark_background_review_read", lambda *args: None)
    names = [s["name"] for s in skills_tool._find_all_skills()]
    for name in ("marketer-pipeline", *ENTRIES):
        assert names.count(name) == 1
    for retired in ("build-marketer", "qa-marketer", "writer-pipeline"):
        assert retired not in names
    for name, relative in (("review-marketer", "references/content.md"),
                           ("analyze-marketer", "references/measurement.md"),
                           ("marketer-pipeline", "references/browsing.md")):
        result = json.loads(skills_tool.skill_view(name, relative, preprocess=False))
        assert result["success"] is True
        assert result["file"] == relative
        assert result["content"]
