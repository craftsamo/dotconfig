from __future__ import annotations

import importlib.util
import json
import shlex
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
ROOT = HERMES / "profiles/marketer/skills/marketer-pipeline"
SPEC = importlib.util.spec_from_file_location("marketer_validator", HERMES / "scripts/validate-profile-skills.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

# Split, flat entries: no mode/domain matrix like the Assistant pipeline.
ENTRIES = ("plan-marketer", "build-marketer", "qa-marketer", "analyze-marketer")

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
    shared = Path("profiles/writer/skills/writer-pipeline/references/acceptance")
    shutil.copytree(HERMES / shared, tmp_path / shared)
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


def add_card_units_field(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---\n"):
        edit_frontmatter(path, card_units=["fake-unit"])
    else:
        path.write_text("---\ncard_units:\n  - fake-unit\n---\n" + raw, encoding="utf-8")


def strip_read_before_work_token(path: Path, token: str) -> None:
    doc = path.read_text(encoding="utf-8")
    match = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", doc, re.S)
    block = match.group(1)
    corrupted = block.replace(token, "REDACTED", 1)
    doc = doc[: match.start(1)] + corrupted + doc[match.end(1):]
    path.write_text(doc, encoding="utf-8")


def test_five_roots_and_four_entries_returned(candidate):
    entries, found = entries_and_errors(candidate)
    assert found == []
    roots = sorted(p.relative_to(candidate).as_posix() for p in candidate.rglob("SKILL.md"))
    assert roots == sorted(["SKILL.md"] + [f"{name}/SKILL.md" for name in ENTRIES])
    assert set(entries) == set(ENTRIES)
    for name in ENTRIES:
        assert entries[name] == candidate / name / "SKILL.md"


def test_sixteen_reference_files_all_present(candidate):
    assert len(VALIDATOR.MARKETER_REFERENCE_FILES) == 16
    for relative in VALIDATOR.MARKETER_REFERENCE_FILES:
        assert (candidate / relative).is_file(), relative
    assert errors(candidate) == []


@pytest.mark.parametrize("relative", sorted(VALIDATOR.MARKETER_REFERENCE_FILES))
def test_missing_reference_fails(candidate, relative):
    (candidate / relative).unlink()
    assert any(f"missing marketer reference: {relative}" in e for e in errors(candidate))


def test_missing_shared_acceptance_fails(candidate):
    (VALIDATOR.HERMES_ROOT / "profiles/writer/skills/writer-pipeline/references/acceptance/index.md").unlink()
    assert "missing shared writing acceptance: index.md" in errors(candidate)


@pytest.mark.parametrize("link", ["../../../../missing.md", "../../scripts/missing.py"])
def test_broken_and_escaping_links_fail(candidate, link):
    doc = candidate / "plan-marketer/references/discovery.md"
    doc.write_text(doc.read_text() + f"\n[bad]({link})\n")
    assert any("reference escapes" in e or "broken marketer reference" in e for e in errors(candidate))


def test_old_publish_engine_and_duplicate_mode_platforms_fail(candidate):
    (candidate / "references/publish.md").write_text("# Old publishing\n")
    assert "unexpected marketer reference: references/publish.md" in errors(candidate)


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


@pytest.mark.parametrize(
    "relative",
    ["SKILL.md", "plan-marketer/SKILL.md", "plan-marketer/references/discovery.md"],
)
def test_card_units_forbidden_everywhere(candidate, relative):
    path = candidate / relative
    add_card_units_field(path)
    assert any(f"marketer defines no card units: {relative}" in e for e in errors(candidate))


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


def test_entry_unlinking_own_detail_fails(candidate):
    entry = "build-marketer"
    path = candidate / entry / "SKILL.md"
    doc = path.read_text(encoding="utf-8")
    needle = "[draft](references/draft.md)"
    assert needle in doc
    path.write_text(doc.replace(needle, "draft"), encoding="utf-8")
    assert any(f"marketer entry does not link reference: {entry}: draft.md" in e for e in errors(candidate))


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


def test_validate_worker_accepts_four_entries_and_rejects_unknown_root(candidate, monkeypatch):
    skills = candidate.parent
    (skills / "technic").mkdir()
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    monkeypatch.setattr(VALIDATOR, "validate_plugin_enabled", lambda *args: None)

    found: list[str] = []
    assert VALIDATOR.validate_worker("marketer", found) == (4, 0)
    assert found == []

    rogue = skills / "rogue" / "SKILL.md"
    rogue.parent.mkdir()
    rogue.write_text("---\nname: rogue\n---\n")
    found = []
    VALIDATOR.validate_worker("marketer", found)
    assert any("unexpected skill root" in error for error in found)


def test_actual_config_preserves_browser_and_limits_dispatch():
    config = yaml.safe_load((HERMES / "profiles/marketer/config.yaml").read_text())
    assert set(config["specialist_call"]["resident_targets"]) == {"engineer", "creator", "researcher", "writer"}
    assert "specialist-call" in config["plugins"]["enabled"]
    assert "a2a" not in config["toolsets"]
    assert config["platforms"]["a2a"]["enabled"] is True
    for platform in ("cli", "telegram", "a2a"):
        tools = config["platform_toolsets"][platform]
        assert "specialist" in tools and "a2a" not in tools
        if platform == "a2a":
            assert not {"browser", "terminal", "delegation"} & set(tools)
        else:
            assert "browser" in tools
    assert "clarify" in config["platform_toolsets"]["telegram"]
    assert config["browser"]["use_real_profile"] is True
    assert config["browser"]["real_profile_pin"] == "Profile 13"
    assert config["skills"]["external_dirs"] == ["~/.hermes/profiles/writer/skills/writer-pipeline"]
    prompt = " ".join(config["agent"]["system_prompt"].split())
    for name in ENTRIES:
        assert name in prompt
    assert "Each user turn or specialist completion, select" in prompt
    assert "Re-evaluate before a mode, target, platform or scope-changing action" in prompt
    assert ("Reuse the full marketer-pipeline kernel and selected entry only while "
            "their bodies are in current context") in prompt
    assert "never from a past load, preload label or summary alone" in prompt
    assert "Approval-only replies resume the recorded job, not a new plan or grant" in prompt
    assert "Never publish, schedule, send/test-send" in prompt
    assert "Before typing or uploading" in prompt and "autosave is already an upload" in prompt
    assert "Old Publish/P1 grants do not authorize" in prompt
    assert "inquiry-only" in prompt


def test_direct_client_discovery_and_bounded_requests():
    kernel = text("SKILL.md")
    assert "both a human conversation and an Assistant brief" in kernel
    assert "A product need not exist at intake" in kernel
    assert "not mandatory consecutive stages" in kernel
    discovery = text("plan-marketer/references/discovery.md")
    assert "absent offer is a valid starting state" in discovery
    assert "actual purchase" in discovery
    assert "No automatic outreach" in discovery


def test_save_contract_orders_consent_before_editor_and_reopen_after_save():
    procedure = text("build-marketer/references/draft.md")
    assert procedure.index("3. Obtain explicit approval") < procedure.index("4. Use the existing")
    assert procedure.index("6. Save") < procedure.index("7. Reopen the SAME draft")
    for requirement in ("autosave can transmit immediately", "lease", "before ANY browser action",
                        "No timeout-based stealing", "before ever creating", "save-uncertain"):
        assert requirement in procedure
    qa = text("qa-marketer/references/saved-draft.md")
    assert "unpublished-state evidence" in qa
    assert "A shared/secret preview link is not a private editor URL" in qa


def test_relocated_draft_resolves_lease_from_kernel_not_shell_environment():
    draft = (ROOT / "build-marketer/references/draft.md").read_text()
    commands = re.findall(r"```sh\n(.*?)\n```", draft, re.S)
    assert len(commands) == 2
    for command, operation in zip(commands, ("acquire", "release")):
        assert "$" not in command
        argv = shlex.split(command.replace("<marketer-pipeline-directory>", str(ROOT)))
        assert Path(argv[1]) == ROOT / "scripts/browser-lease.py"
        assert Path(argv[1]).is_file()
        assert argv[2] == operation
    assert "Any nonzero acquire exit means do not proceed to the browser" in " ".join(draft.split())


@pytest.mark.parametrize("platform", ["x", "substack", "note", "zenn"])
def test_platform_procedures_do_not_claim_live_support(platform):
    procedure = text(f"references/platforms/{platform}.md")
    assert "2026-09-10" in procedure
    assert "unverified" in procedure or "approved" in procedure and "trial" in procedure
    assert "draft" in procedure.lower()
    assert "publish" in procedure.lower()
    assert "https://" in procedure


def test_platform_specific_nonpublication_hazards():
    assert "per-post approval or draft-only work is not a stated exception" in text("references/platforms/x.md")
    assert "record the user's scoped decision" in text("references/platforms/x.md")
    assert "test email" in text("references/platforms/substack.md")
    assert "sharing-preview link" in text("references/platforms/note.md")
    assert "notify other members" in text("references/platforms/zenn.md")
    assert "default scope must be inspected" in text("references/platforms/zenn.md")


def test_note_smoke_scope_and_observed_input_hazards_are_explicit():
    note = text("references/platforms/note.md")
    assert "BEFORE opening a new editor" in note
    assert "native character key events" in note
    assert "multiline Input.insertText" in note
    assert "scope its Close control to that dialog" in note
    assert "NOT a fresh candidate AIAgent" in note
    assert "remain unverified" in note
    assert "textarea alone also does not prove hydration is complete" in note
    assert "another read, not another save" in note
    draft = text("build-marketer/references/draft.md")
    assert "do not assume Python variables or the active tab persist" in draft


def test_readonly_draft_recheck_keeps_common_qa_and_bounded_verdict():
    kernel = text("SKILL.md")
    assert ("loads qa-marketer, its saved-draft reference and the selected platform "
            "procedure before any browser action") in kernel
    assert "Read-only references may be loaded in parallel" in kernel
    assert "Reading instructions does not authorize navigation or waive the browser lease" in kernel
    qa = text("qa-marketer/references/saved-draft.md")
    assert "`draft-verified`" in qa
    assert "never claim a new save/update" in qa
    assert "not infer unpublished status from an editor's Publish/Continue button alone" in qa


def test_measurement_does_not_turn_missing_data_into_success():
    measure = text("build-marketer/references/measurement.md")
    for state in ("measured zero", "not measured", "retrieval failed", "not comparable"):
        assert state in measure
    analysis = text("analyze-marketer/SKILL.md")
    assert "Sparse data remains inconclusive" in analysis
    assert "No universal sample count" in analysis
    assert "Zero changes is legitimate" in analysis


def test_real_skill_discovery_and_shared_reference_loading(monkeypatch):
    from tools import skills_tool, skills_tool_plugin

    skills = ROOT.parent
    writer = HERMES / "profiles/writer/skills/writer-pipeline"
    monkeypatch.setattr(skills_tool, "_skill_search_dirs", lambda: ([], [skills, writer], skills))
    config = yaml.safe_load((HERMES / "profiles/marketer/config.yaml").read_text())
    disabled = set(config["skills"]["disabled"])
    monkeypatch.setattr(skills_tool, "_is_skill_disabled", lambda name, **kwargs: name in disabled)
    monkeypatch.setattr(skills_tool, "_get_disabled_skill_names", lambda: disabled)
    monkeypatch.setattr(skills_tool, "_SKILLS_CACHE", {})
    monkeypatch.setattr(skills_tool_plugin, "_mark_background_review_read", lambda *args: None)
    names = [s["name"] for s in skills_tool._find_all_skills()]
    for name in ("marketer-pipeline", *ENTRIES):
        assert names.count(name) == 1
    assert names.count("writer-pipeline") == 1
    authoring = {
        yaml.safe_load(path.read_text().split("---", 2)[1])["name"]
        for path in writer.rglob("SKILL.md") if path != writer / "SKILL.md"
    }
    assert "consult-writer" in authoring
    assert authoring <= disabled
    assert not authoring & set(names)
    denied = json.loads(skills_tool.skill_view("write-post", preprocess=False))
    assert denied["success"] is False
    assert json.loads(skills_tool.skill_view("consult-writer", preprocess=False))["success"] is False
    for name, relative in (("build-marketer", "references/draft.md"),
                           ("writer-pipeline", "references/acceptance/index.md")):
        result = json.loads(skills_tool.skill_view(name, relative, preprocess=False))
        assert result["success"] is True
        assert result["file"] == relative
        assert result["content"]
    monkeypatch.setattr(skills_tool, "_skill_search_dirs", lambda: ([], [skills], skills))
    result = json.loads(skills_tool.skill_view("writer-pipeline", "references/acceptance/index.md", preprocess=False))
    assert result["success"] is False
