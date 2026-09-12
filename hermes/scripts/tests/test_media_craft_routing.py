"""Real isolated discovery and structural routes, not model or media evaluation."""

import json
from pathlib import Path
import shutil

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
HERMES = ROOT / "hermes"
CRAFT = {"direction", "visual", "motion", "audio"}
PROFILE_CRAFT = {
    "image-creator": {"direction", "visual"},
    "video-creator": {"direction", "visual", "motion"},
    "audio-creator": {"direction", "audio"},
    "creator": CRAFT,
}


def pipeline(profile):
    return HERMES / "profiles" / profile / "skills" / f"{profile}-pipeline"


@pytest.mark.parametrize("profile", PROFILE_CRAFT)
def test_exact_profile_craft_surface(profile):
    config = yaml.safe_load((HERMES / "profiles" / profile / "config.yaml").read_text())["skills"]
    if profile == "creator":
        assert "~/.agents/skills" in config["external_dirs"]
    else:
        assert "~/.agents/skills" not in config["external_dirs"]
        actual = {Path(path).name.removeprefix("media-craft-") for path in config["external_dirs"]
                  if Path(path).name.startswith("media-craft-")}
        assert actual == PROFILE_CRAFT[profile]
    assert not {f"media-craft-{name}" for name in PROFILE_CRAFT[profile]} & set(config.get("disabled", []))
    assert config["inline_shell"] is False


@pytest.mark.parametrize("profile", PROFILE_CRAFT)
def test_conditional_craft_routes_cover_subjects(profile):
    root = pipeline(profile)
    policy = (root / "references/craft.md").read_text()
    assert "read_file" in policy and "current context" in policy
    for suffix in PROFILE_CRAFT[profile]:
        assert f"media-craft-{suffix}" in policy
    if profile == "creator":
        for mode in ("plan", "build", "qa"):
            assert "../references/craft.md" in (root / f"{mode}-creator/SKILL.md").read_text()
        assert "../craft.md" in (root / "references/legacy/produce.md").read_text()
    else:
        assert "[craft reading](references/craft.md)" in (root / "SKILL.md").read_text()
        leaves = list(root.glob("*/*/SKILL.md"))
        assert leaves
        for leaf in leaves:
            assert leaf.parent.name in policy
        kernel = " ".join((root / "SKILL.md").read_text().split())
        assert "Require the full kernel, selected leaf and required reference bodies in current context" in kernel


@pytest.fixture(params=PROFILE_CRAFT)
def craft_store(request, tmp_path, monkeypatch):
    from agent import skill_utils
    from tools import skills_tool
    from hermes_cli import config as hermes_config

    profile = request.param
    home = tmp_path / ".hermes"
    local = home / "skills"
    local.mkdir(parents=True)
    store = tmp_path / ".agents/skills"
    for suffix in CRAFT:
        name = f"media-craft-{suffix}"
        shutil.copytree(ROOT / "agents/curated" / name, store / name)
    source = pipeline(profile)
    for file in [*source.glob("**/SKILL.md"), source / "references/craft.md"]:
        target = local / source.name / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    skill_config = yaml.safe_load((HERMES / "profiles" / profile / "config.yaml").read_text())["skills"]
    config = {"skills": skill_config}
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local)
    monkeypatch.setattr(skill_utils, "get_project_skills_dirs", lambda: [])
    monkeypatch.setattr(hermes_config, "load_config", lambda *args, **kwargs: config)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    yield profile, skills_tool, store, local
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()


def test_actual_discovery_and_all_reference_bodies(craft_store):
    profile, skills, store, _ = craft_store
    found = {item["name"] for item in skills._find_all_skills()}
    expected = {f"media-craft-{name}" for name in PROFILE_CRAFT[profile]}
    assert found & {f"media-craft-{name}" for name in CRAFT} == expected
    for name in expected:
        root = json.loads(skills.skill_view(name))
        assert root["success"], root
        assert Path(root["skill_dir"]).resolve() == (store / name).resolve()
        for file in (store / name / "references").glob("*.md"):
            result = json.loads(skills.skill_view(name, file_path=f"references/{file.name}"))
            assert result["success"], result
            assert file.read_text().splitlines()[0] in result["content"]


def test_missing_and_ambiguous_knowledge_fail_without_hiding_producer(craft_store):
    from agent import skill_utils

    profile, skills, store, local = craft_store
    name = "media-craft-direction"
    duplicate = local / name
    shutil.copytree(store / name, duplicate)
    result = json.loads(skills.skill_view(name))
    assert result["success"] is False
    assert "Ambiguous skill name" in result["error"]
    shutil.rmtree(duplicate)
    shutil.rmtree(store / name)
    skill_utils._external_dirs_cache_clear()
    skills._SKILLS_CACHE.clear()
    assert json.loads(skills.skill_view(name))["success"] is False
    assert json.loads(skills.skill_view(f"{profile}-pipeline"))["success"]
    policy = json.loads(skills.skill_view(f"{profile}-pipeline", file_path="references/craft.md"))
    assert policy["success"]
    assert "stop" in policy["content"] or "blocks" in policy["content"]


def test_all_fifteen_subjects_have_behavioral_cases():
    subjects = {leaf.parent.name for profile in PROFILE_CRAFT if profile != "creator"
                for leaf in pipeline(profile).glob("*/*/SKILL.md")}
    cases = [case for path in (ROOT / "agents/tests").glob("media-craft-*-cases.json")
             for case in json.loads(path.read_text())]
    assert subjects == {subject for case in cases for subject in case["subjects"]}
    assert len(subjects) == 15
    assert "human" in (pipeline("audio-creator") / "references/craft.md").read_text().lower()
