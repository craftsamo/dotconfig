"""Tests for the video-creator profile config that pairs it with
image-creator's shape.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import pytest
import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
PROFILE = HERMES_ROOT / "profiles" / "video-creator"
PIPELINE = PROFILE / "skills" / "video-creator-pipeline"
TECHNICAL_SKILLS = (
    "hyperframes-core",
    "hyperframes-animation",
    "cut-the-curve",
    "oversized-cursor",
)
CRAFT_SKILLS = ("media-craft-direction", "media-craft-visual", "media-craft-motion")


class VideoCreatorConfigTest(unittest.TestCase):
    """The video-creator profile config must mirror image-creator's shape
    (Creator's other 'hand') except for the video-specific toolset/budget/
    plugin differences documented in hermes/AGENTS.md."""

    @classmethod
    def setUpClass(cls) -> None:
        video_path = HERMES_ROOT / "profiles" / "video-creator" / "config.yaml"
        image_path = HERMES_ROOT / "profiles" / "image-creator" / "config.yaml"
        cls.video = yaml.safe_load(video_path.read_text())
        cls.image = yaml.safe_load(image_path.read_text())

    def test_auxiliary_matches_image_creator(self) -> None:
        self.assertEqual(self.image["auxiliary"], self.video["auxiliary"])

    def test_model_matches_image_creator(self) -> None:
        self.assertEqual(self.image["model"], self.video["model"])
        self.assertEqual(self.image["fallback_providers"], self.video["fallback_providers"])

    def test_toolsets_contain_video_not_tts_image_gen_delegation_a2a(self) -> None:
        toolsets = self.video["toolsets"]
        self.assertIn("video", toolsets)
        self.assertIn("video_gen", toolsets)
        for forbidden in ("tts", "image_gen", "delegation", "a2a"):
            self.assertNotIn(forbidden, toolsets)
        for platform_list in self.video["platform_toolsets"].values():
            for forbidden in ("tts", "image_gen", "delegation", "a2a"):
                self.assertNotIn(forbidden, platform_list)

    def test_only_curated_external_skill_dirs(self) -> None:
        self.assertEqual(
            [f"~/.agents/skills/{name}" for name in (*TECHNICAL_SKILLS, *CRAFT_SKILLS)],
            self.video["skills"]["external_dirs"],
        )
        self.assertFalse(set((*TECHNICAL_SKILLS, *CRAFT_SKILLS)) & set(self.video["skills"]["disabled"]))
        self.assertIs(False, self.video["skills"]["inline_shell"])

    def test_technical_reading_is_scoped_to_authored_leaves(self) -> None:
        for leaf in PIPELINE.glob("*/*/SKILL.md"):
            contents = leaf.read_text()
            self.assertEqual(
                leaf.parent.parent.name == "create" and leaf.parent.name in {"tour", "ad", "explainer-video"},
                'file_path="references/hyperframes.md"' in contents,
            )
        for subject in ("tour", "ad", "explainer-video"):
            contents = (PIPELINE / "create" / subject / "SKILL.md").read_text()
            self.assertIn(
                'skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")',
                contents,
            )
            self.assertIn("local-authoring fallback", contents.split("<Report>")[1])

    def test_no_persistent_public_storage(self) -> None:
        self.assertIs(False, self.video["video_gen"]["xai"]["storage"]["enabled"])

    def test_plugins_allow_tool_override_true(self) -> None:
        entries = self.video["plugins"]["entries"]
        self.assertIn("video-analyze-mimo", entries)
        self.assertTrue(entries["video-analyze-mimo"]["allow_tool_override"])

    def test_budget_is_two_not_four(self) -> None:
        prompt = self.video["agent"]["system_prompt"]
        self.assertIn("2 variants", prompt)
        self.assertNotIn("4 variants", prompt)
        # image-creator's sibling contract uses 4; confirm the two differ
        # deliberately rather than both having drifted to the same number.
        image_prompt = self.image["agent"]["system_prompt"]
        self.assertIn("4 variants", image_prompt)


@pytest.fixture
def skill_environment(tmp_path, monkeypatch):
    """Exercise Hermes discovery against isolated stores, never the live profile.

    Stub only config loading/project discovery to prevent config rewrites or
    ambient project overrides. The skill discovery and file serving are real.
    """
    from agent import skill_utils
    from tools import skills_tool
    from hermes_cli import config as hermes_config

    home = tmp_path / ".hermes"
    local = home / "skills"
    local.mkdir(parents=True)
    config = {"skills": yaml.safe_load((PROFILE / "config.yaml").read_text())["skills"]}
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    sources = [*PIPELINE.glob("**/SKILL.md"), PIPELINE / "references/hyperframes.md"]
    sources.extend(PIPELINE / "create" / subject / "references/authoring.md" for subject in ("tour", "ad", "explainer-video"))
    for source in sources:
        target = local / "video-creator-pipeline" / source.relative_to(PIPELINE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    store = tmp_path / ".agents" / "skills"
    for name in (*TECHNICAL_SKILLS, "hyperframes", "media-use"):
        skill = store / name
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Isolated technical fixture\n---\n\nFixture {name}.\n"
        )
        (skill / "references/fixture.md").write_text(f"Reference for {name}.\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local)
    monkeypatch.setattr(skill_utils, "get_project_skills_dirs", lambda: [])
    monkeypatch.setattr(hermes_config, "load_config", lambda *args, **kwargs: config)
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()
    yield skills_tool, store, local
    skill_utils._external_dirs_cache_clear()
    skills_tool._SKILLS_CACHE.clear()


def test_curated_skill_discovery_and_reference_reads(skill_environment):
    skills, store, _ = skill_environment
    names = {item["name"] for item in skills._find_all_skills()}
    assert set(TECHNICAL_SKILLS) <= names
    assert not {"hyperframes", "media-use"} & names
    for name in TECHNICAL_SKILLS:
        result = json.loads(skills.skill_view(name))
        assert result["success"], result
        assert Path(result["skill_dir"]) == store / name
        reference = json.loads(skills.skill_view(name, file_path="references/fixture.md"))
        assert reference["success"], reference
        assert f"Reference for {name}." in reference["content"]


@pytest.mark.parametrize("missing", [("hyperframes-core",), TECHNICAL_SKILLS])
def test_missing_external_skills_leave_local_authoring_available(skill_environment, missing):
    skills, store, _ = skill_environment
    for name in missing:
        shutil.rmtree(store / name)
    for name in missing:
        result = json.loads(skills.skill_view(name))
        assert result["success"] is False
        assert "not found" in result["error"]
    for name in set(TECHNICAL_SKILLS) - set(missing):
        assert json.loads(skills.skill_view(name))["success"]
    for name in ("create-tour", "create-ad", "create-explainer-video"):
        assert json.loads(skills.skill_view(name))["success"]
        reference = json.loads(skills.skill_view(name, file_path="references/authoring.md"))
        assert reference["success"], reference
        assert "Source Contract" in reference["content"]
    policy = json.loads(skills.skill_view("video-creator-pipeline", file_path="references/hyperframes.md"))
    assert policy["success"], policy
    assert "continue with the local authoring reference" in policy["content"]
    assert "final Report" in policy["content"]


def test_missing_reference_file_is_reported_without_hiding_skill(skill_environment):
    skills, _, _ = skill_environment
    result = json.loads(skills.skill_view("hyperframes-core", file_path="references/missing.md"))
    assert result["success"] is False
    assert json.loads(skills.skill_view("hyperframes-core"))["success"]
    assert json.loads(skills.skill_view("create-tour", file_path="references/authoring.md"))["success"]


def test_ambiguous_external_skill_is_not_silently_chosen(skill_environment):
    skills, store, local = skill_environment
    shutil.copytree(store / "hyperframes-core", local / "hyperframes-core")
    result = json.loads(skills.skill_view("hyperframes-core"))
    assert result["success"] is False
    assert "Ambiguous skill name" in result["error"]
    assert json.loads(skills.skill_view("create-ad", file_path="references/authoring.md"))["success"]


if __name__ == "__main__":
    unittest.main()
