"""Writer leaf validation; fixtures never contain private caller contracts."""

import importlib.util
import json
from pathlib import Path
import shutil

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("writer_validator", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def read_contract():
    return (
        '<ReadBeforeWork>\nWhen executing as Writer, require the kernel in current context.\n'
        'skill_view(name="writer-pipeline")\n${HERMES_SKILL_DIR}/../../SKILL.md\n'
        'A past load or summary is not its body. Re-evaluate the operation.\n'
        'Reuse full bodies; if unchanged without the body, use read_file and next_offset.\n'
        'If unavailable, stop the affected action. A Client reading a form does not\n'
        "inherit Writer's role.\n</ReadBeforeWork>\n"
    )


def leaf(root, location="write/article", **overrides):
    path = root / location / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": location.replace("/", "-"),
        "description": "Write an article draft, not a published post.",
        "metadata": {"hermes": {
            "category": "writing", "output": "Complete draft at the requested path",
            "form": {"note": {"required": False, "label": "Other constraints"}},
        }},
    }
    data.update(overrides)
    path.write_text("---\n" + yaml.safe_dump(data) + "---\n" + read_contract() +
                    "<Procedure>\nDraft.\n</Procedure>\n"
                    "<QA>\nRead the draft.\n</QA>\n"
                    "<Report>\nPath and evidence.\n</Report>\n")
    return path, data


def update(path, data, suffix=""):
    body = path.read_text().split("---", 2)[2]
    path.write_text("---\n" + yaml.safe_dump(data) + "---" + body + suffix)


def errors(root):
    found = []
    VALIDATOR.validate_writer_leaves(root, found)
    return found


def test_empty_migration_is_valid(tmp_path):
    assert errors(tmp_path) == []


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_operation_leaf_is_valid(tmp_path, verb):
    leaf(tmp_path, f"{verb}/article")
    assert errors(tmp_path) == []


@pytest.mark.parametrize("location", ["generate/article", "write/article/zenn", "write/Article"])
def test_invalid_location(tmp_path, location):
    leaf(tmp_path, location)
    assert errors(tmp_path)


def test_name_category_and_output(tmp_path):
    path, data = leaf(tmp_path, name="other")
    data["metadata"]["hermes"]["category"] = "hands"
    data["metadata"]["hermes"].pop("output")
    update(path, data)
    result = errors(tmp_path)
    assert any("name must be write-article" in error for error in result)
    assert any("category must be writing" in error for error in result)
    assert any("metadata.hermes.output" in error for error in result)


@pytest.mark.parametrize("field", [
    {"required": "yes", "label": "Topic"},
    {"required": True, "label": "Topic", "type": "list"},
    {"required": True},
    {"required": False, "label": "Tool", "options": [True, False]},
    {"required": True, "label": "Platform", "other": "yes"},
])
def test_invalid_field(tmp_path, field):
    path, data = leaf(tmp_path)
    data["metadata"]["hermes"]["form"]["topic"] = field
    update(path, data)
    assert errors(tmp_path)


@pytest.mark.parametrize("directory", ["references", "references/platform"])
def test_explicit_reference_mapping_and_link(tmp_path, directory):
    path, data = leaf(tmp_path)
    data["metadata"]["hermes"]["form"]["platform"] = {
        "required": False, "label": "Destination", "options": ["zenn"],
        "other": True, "references": f"{directory}/*.md",
    }
    update(path, data)
    assert any("no local reference" in error for error in errors(tmp_path))
    backing = path.parent / directory / "zenn.md"
    backing.parent.mkdir(parents=True, exist_ok=True)
    backing.write_text("# Zenn\n")
    assert any("direct body link" in error for error in errors(tmp_path))
    update(path, data, f"\n[Zenn]({directory}/zenn.md)\n")
    assert errors(tmp_path) == []


def test_reference_cannot_escape(tmp_path):
    path, data = leaf(tmp_path)
    data["metadata"]["hermes"]["form"]["platform"] = {
        "required": False, "label": "Destination", "options": ["outside"],
        "references": "references/../../*.md",
    }
    update(path, data)
    assert any("local references" in error for error in errors(tmp_path))


def test_leaf_must_own_qa(tmp_path):
    path, _ = leaf(tmp_path)
    path.write_text(path.read_text().replace("<QA>", "<Review>"))
    assert any("own <QA>" in error for error in errors(tmp_path))


def test_creator_verbs_are_unchanged():
    assert "write" not in VALIDATOR.HANDS_VERBS
    assert "writer" not in VALIDATOR.HANDS_PROFILES


@pytest.mark.parametrize("required", [
    'skill_view(name="writer-pipeline")', "../../SKILL.md", "as Writer",
    "current context", "past load or summary", "Re-evaluate", "Reuse",
    "unchanged", "read_file", "next_offset", "stop the affected action", "Client reading",
    "inherit Writer's role",
])
def test_leaf_missing_read_contract_is_rejected(tmp_path, required):
    path, _ = leaf(tmp_path)
    path.write_text(path.read_text().replace(required, "REMOVED"))
    assert any("ReadBeforeWork missing" in error for error in errors(tmp_path))


def test_worker_accepts_leaves_and_rejects_duplicate_learned_name(tmp_path, monkeypatch):
    skills = tmp_path / "profiles/writer/skills"
    root = skills / "writer-pipeline"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: writer-pipeline\n---\n")
    (skills / "technic").mkdir()
    leaf(root)
    monkeypatch.setattr(VALIDATOR, "HERMES_ROOT", tmp_path)
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    monkeypatch.setattr(VALIDATOR, "validate_plugin_enabled", lambda *args: None)
    found = []
    assert VALIDATOR.validate_worker("writer", found) == (1, 0)
    assert found == []
    duplicate = skills / "learned/write-article/SKILL.md"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text("---\nname: write-article\n---\n")
    VALIDATOR.validate_worker("writer", found)
    assert any("duplicate writer skill name" in error for error in found)


def test_hermes_discovers_writer_and_serves_its_references(tmp_path, monkeypatch):
    # Stub ambient configuration, not Hermes' actual discovery/file serving.
    home = tmp_path / ".hermes"
    local = home / "skills"
    local.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(home))
    from agent import skill_utils
    from hermes_cli import config as hermes_config
    from tools import skills_tool

    config = {"skills": {"external_dirs": [], "project_discovery": False}}
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    source = SCRIPT.parent.parent / "profiles/writer/skills/writer-pipeline"
    target = local / "writer-pipeline"
    shutil.copytree(source, target)
    language_source = SCRIPT.parents[2] / "agents/curated/japanese-writing"
    shutil.copytree(language_source, local / "japanese-writing")
    leaf(target, "analyze/fixture")
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local)
    monkeypatch.setattr(skill_utils, "get_project_skills_dirs", lambda: [])
    monkeypatch.setattr(hermes_config, "load_config", lambda *args, **kwargs: config)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    try:
        names = {item["name"] for item in skills_tool._find_all_skills()}
        assert {"writer-pipeline", "analyze-fixture", "japanese-writing"} <= names
        language = json.loads(skills_tool.skill_view("japanese-writing", preprocess=False))
        assert language["success"], language
        assert language["content"] == (language_source / "SKILL.md").read_text()
        for retired in ("references/inspection/workflow.md", "scripts/lint.py"):
            missing = json.loads(skills_tool.skill_view(
                "japanese-writing", file_path=retired, preprocess=False
            ))
            assert not missing["success"], retired
        for skill in target.rglob("SKILL.md"):
            data = VALIDATOR.frontmatter(skill)
            result = json.loads(skills_tool.skill_view(data["name"], preprocess=False))
            assert result["success"], result
            assert Path(result["skill_dir"]) == skill.parent
            for reference in (skill.parent / "references").glob("**/*.md"):
                relative = reference.relative_to(skill.parent).as_posix()
                viewed = json.loads(skills_tool.skill_view(data["name"], file_path=relative, preprocess=False))
                assert viewed["success"], viewed
                assert viewed["content"] == reference.read_text()
    finally:
        skill_utils._external_dirs_cache_clear()
        skills_tool._SKILLS_CACHE.clear()
