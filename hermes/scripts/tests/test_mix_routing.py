"""Routing/topology tests for the Mix subject on the audio-creator profile.

Mix places already-finished sources on a shared timeline: create/edit/analyze
only (no generate/mix - it never synthesizes audio). It reuses the existing
speech/sfx/music toolsets/plugins and adds none of its own.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"


class MixRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audio = yaml.safe_load(
            (HERMES_ROOT / "profiles" / "audio-creator" / "config.yaml").read_text()
        )

    def test_mix_has_create_edit_analyze_leaves_and_no_generate(self) -> None:
        for verb in ("create", "edit", "analyze"):
            self.assertTrue((PIPELINE / verb / "mix" / "SKILL.md").is_file())
        self.assertFalse((PIPELINE / "generate" / "mix").exists())

    def test_mix_frontmatter_closes_before_the_4000_char_discovery_cutoff(self) -> None:
        """Hermes discovery truncates before parsing YAML; an incomplete closing fence
        falls back to the parent directory name, collapsing every mix leaf into one
        generic 'mix' skill despite the topology validator passing."""
        for verb in ("create", "edit", "analyze"):
            text = (PIPELINE / verb / "mix" / "SKILL.md").read_text(encoding="utf-8")
            fence = text.index("---", 3)
            self.assertLess(fence, 4000, f"{verb}/mix frontmatter fence must close within 4000 chars")

    def test_parse_frontmatter_mix_leaf_names(self) -> None:
        from agent.skill_utils import parse_frontmatter

        expected_names = {"create": "create-mix", "edit": "edit-mix", "analyze": "analyze-mix"}
        for verb, expected_name in expected_names.items():
            text = (PIPELINE / verb / "mix" / "SKILL.md").read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(text[:4000])
            self.assertEqual(expected_name, frontmatter.get("name"))

    def test_mix_leaves_declare_free_cost_and_hands_metadata(self) -> None:
        for verb in ("create", "edit", "analyze"):
            text = (PIPELINE / verb / "mix" / "SKILL.md").read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(text.split("---", 2)[1])
            metadata = frontmatter["metadata"]["hermes"]
            self.assertEqual("hands", metadata["category"])
            self.assertEqual("audio-creator", metadata["hands"])
            self.assertEqual("free", metadata["cost"])

    def test_find_all_skills_discovers_every_leaf_including_mix_once_each(self) -> None:
        """tools.skills_tool._find_all_skills, scoped to only this profile's skill root,
        must discover the pipeline root plus all 14 leaves (3 speech + 4 sfx + 4 music +
        3 mix) with their real distinct names - no generic 'mix' fallback, no dropped
        duplicate."""
        import tools.skills_tool as skills_tool

        with patch.object(skills_tool, "_skill_search_dirs", return_value=([], [PIPELINE], PIPELINE)), \
             patch.object(skills_tool, "_get_disabled_skill_names", return_value=set()), \
             patch.object(skills_tool, "_SKILLS_CACHE", {}):
            skills = skills_tool._find_all_skills()

        names = [s["name"] for s in skills]
        self.assertEqual(15, len(names))
        self.assertEqual(15, len(set(names)))
        self.assertNotIn("mix", names)
        for expected_name in (
            "audio-creator-pipeline",
            "generate-speech", "edit-speech", "analyze-speech",
            "create-sfx", "generate-sfx", "edit-sfx", "analyze-sfx",
            "create-music", "generate-music", "edit-music", "analyze-music",
            "create-mix", "edit-mix", "analyze-mix",
        ):
            self.assertEqual(1, names.count(expected_name))

    def test_mix_adds_no_new_plugin_toolset_or_secret(self) -> None:
        """Mix is deterministic local placement/gain/fade/sum, cost: free throughout -
        it shares no runtime with SFX/Music's Stable Audio install and adds nothing new."""
        toolsets = set(self.audio["toolsets"])
        expected = {"terminal", "file", "tts", "sfx_gen", "music_gen", "skills", "memory"}
        self.assertEqual(expected, toolsets)
        for forbidden in ("mix", "mix_gen"):
            self.assertNotIn(forbidden, toolsets)
        plugins = set(self.audio["plugins"]["enabled"])
        for forbidden in ("mix-gen", "mix-media", "mix"):
            self.assertNotIn(forbidden, plugins)

    def test_mix_media_script_lives_beside_music_media_not_a_new_engine(self) -> None:
        scripts = PIPELINE / "scripts"
        self.assertTrue((scripts / "mix-media.py").is_file())
        self.assertTrue((scripts / "music-media.py").is_file())
        self.assertFalse((scripts / "mix-gen.py").exists())

    def test_audio_creator_prompt_names_all_three_mix_leaves(self) -> None:
        prompt = self.audio["agent"]["system_prompt"]
        for leaf in ("create-mix", "edit-mix", "analyze-mix"):
            self.assertIn(leaf, prompt)


if __name__ == "__main__":
    unittest.main()
