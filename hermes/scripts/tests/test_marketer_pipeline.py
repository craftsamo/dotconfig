from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
ROOT = HERMES / "profiles/marketer/skills/marketer-pipeline"
SPEC = importlib.util.spec_from_file_location("marketer_validator", HERMES / "scripts/validate-profile-skills.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


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


def test_four_mode_reference_tree_and_shared_contract(candidate):
    assert errors(candidate) == []
    assert list(ROOT.rglob("SKILL.md")) == [ROOT / "SKILL.md"]


@pytest.mark.parametrize("relative", sorted(VALIDATOR.MARKETER_REFERENCE_FILES))
def test_missing_reference_fails(candidate, relative):
    (candidate / "references" / relative).unlink()
    assert any(f"missing marketer reference: {relative}" in e for e in errors(candidate))


def test_missing_shared_acceptance_fails(candidate):
    (VALIDATOR.HERMES_ROOT / "profiles/writer/skills/writer-pipeline/references/acceptance/index.md").unlink()
    assert "missing shared writing acceptance: index.md" in errors(candidate)


@pytest.mark.parametrize("link", ["../../../../missing.md", "../../scripts/missing.py"])
def test_broken_and_escaping_links_fail(candidate, link):
    doc = candidate / "references/plan/index.md"
    doc.write_text(doc.read_text() + f"\n[bad]({link})\n")
    assert any("reference escapes" in e or "broken marketer reference" in e for e in errors(candidate))


def test_old_publish_engine_and_duplicate_mode_platforms_fail(candidate):
    (candidate / "references/publish.md").write_text("# Old publishing\n")
    assert "unexpected marketer reference: publish.md" in errors(candidate)


def test_unlinked_reference_fails(candidate):
    kernel = candidate / "SKILL.md"
    kernel.write_text(kernel.read_text().replace("[state](references/state.md)", "state"))
    assert "marketer root does not link reference: state.md" in errors(candidate)


def test_legacy_version_remains_valid_without_new_tree(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: marketer-pipeline\nversion: 6.0.0\n---\n")
    assert errors(tmp_path) == []


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
    assert "Never publish, schedule, send/test-send" in prompt
    assert "Before typing or uploading" in prompt and "autosave is already an upload" in prompt
    assert "Old Publish/P1 grants do not authorize" in prompt
    assert "inquiry-only" in prompt


def test_direct_client_discovery_and_bounded_requests():
    kernel = text("SKILL.md")
    assert "both a human conversation and an Assistant brief" in kernel
    assert "A product need not exist at intake" in kernel
    assert "not mandatory consecutive stages" in kernel
    discovery = text("references/plan/discovery.md")
    assert "absent offer is a valid starting state" in discovery
    assert "actual purchase" in discovery
    assert "No automatic outreach" in discovery


def test_save_contract_orders_consent_before_editor_and_reopen_after_save():
    procedure = text("references/build/draft.md")
    assert procedure.index("3. Obtain explicit approval") < procedure.index("4. Use the existing")
    assert procedure.index("6. Save") < procedure.index("7. Reopen the SAME draft")
    for requirement in ("autosave can transmit immediately", "lease", "before ANY browser action",
                        "No timeout-based stealing", "before ever creating", "save-uncertain"):
        assert requirement in procedure
    qa = text("references/quality-assurance/saved-draft.md")
    assert "unpublished-state evidence" in qa
    assert "A shared/secret preview link is not a private editor URL" in qa


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
    draft = text("references/build/draft.md")
    assert "do not assume Python variables or the active tab persist" in draft


def test_readonly_draft_recheck_keeps_common_qa_and_bounded_verdict():
    kernel = text("SKILL.md")
    assert "index.md and applicable detailed/platform references before acting" in kernel
    assert "Read-only references may be loaded in parallel" in kernel
    assert "common index must not be omitted" in kernel
    qa = text("references/quality-assurance/saved-draft.md")
    assert "`draft-verified`" in qa
    assert "never claim a new save/update" in qa
    assert "not infer unpublished status from an editor's Publish/Continue button alone" in qa


def test_measurement_does_not_turn_missing_data_into_success():
    measure = text("references/build/measurement.md")
    for state in ("measured zero", "not measured", "retrieval failed", "not comparable"):
        assert state in measure
    analysis = text("references/analyze/index.md")
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
    assert names.count("marketer-pipeline") == 1
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
    for name, relative in (("marketer-pipeline", "references/build/draft.md"),
                           ("writer-pipeline", "references/acceptance/index.md")):
        result = json.loads(skills_tool.skill_view(name, relative, preprocess=False))
        assert result["success"] is True
        assert result["file"] == relative
        assert result["content"]
    monkeypatch.setattr(skills_tool, "_skill_search_dirs", lambda: ([], [skills], skills))
    result = json.loads(skills_tool.skill_view("writer-pipeline", "references/acceptance/index.md", preprocess=False))
    assert result["success"] is False
