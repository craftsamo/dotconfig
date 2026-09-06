"""Tests for the video-creator profile config that pairs it with
image-creator's shape.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]


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

    def test_no_external_skill_dirs(self) -> None:
        self.assertEqual([], self.video["skills"]["external_dirs"])

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


if __name__ == "__main__":
    unittest.main()
