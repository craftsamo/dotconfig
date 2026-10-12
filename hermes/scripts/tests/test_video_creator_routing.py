"""Tests for the video-creator profile's gateway/A2A wiring with creator."""

from __future__ import annotations

import unittest
from pathlib import Path

import hermes_yaml as yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = HERMES_ROOT.parent / "agents/curated/motion-vocabulary/references"


class VideoCreatorRoutingTest(unittest.TestCase):
    def test_gateway_and_assistant_wiring(self) -> None:
        video_path = HERMES_ROOT / "profiles" / "video-creator" / "config.yaml"
        video = yaml.safe_load(video_path.read_text())
        root = yaml.safe_load((HERMES_ROOT / "config.yaml").read_text())
        creator = yaml.safe_load((HERMES_ROOT / "profiles/creator/config.yaml").read_text())
        assistant = yaml.safe_load((HERMES_ROOT / "profiles/assistant/config.example.yaml").read_text())
        # One host gateway serves every profile directory; there is no allowlist to join.
        self.assertTrue(root["gateway"]["multiplex_profiles"])
        self.assertNotIn("multiplex_profile_allowlist", root["gateway"])
        self.assertEqual(9908, video["platforms"]["a2a"]["extra"]["port"])
        self.assertIn("video-creator", assistant["specialist_call"]["resident_targets"])
        self.assertIn("~/.hermes/profiles/video-creator/skills/video-creator-pipeline",
                      assistant["skills"]["external_dirs"])
        # Creator is an advisor: it reads the leaves' forms but has no video-creator peer or target.
        self.assertNotIn("video-creator", creator["a2a_agents"])
        self.assertNotIn("video-creator", creator["specialist_call"]["resident_targets"])
        self.assertIn("~/.hermes/profiles/video-creator/skills/video-creator-pipeline",
                      creator["skills"]["external_dirs"])
        self.assertEqual({}, video["a2a_agents"])

    def test_every_hyperframes_leaf_names_from_the_vocabulary(self) -> None:
        kernel = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline"
        vocab = (VOCABULARY / "core.md").read_text()
        self.assertIn("A dictionary, not a rulebook", vocab)
        self.assertIn("## Visual metaphors", vocab)
        self.assertIn("| Idea | Image | Looks like |", vocab)
        # Character motion and drawn looks live in neighbouring files the skill routes to;
        # how each is built in a rendered video lives under references/video/.
        self.assertIn("## Character and physical motion", (VOCABULARY / "character.md").read_text())
        self.assertIn("## Drawn looks", (VOCABULARY / "looks.md").read_text())
        self.assertIn("never re-renders supplied\nart, a cast or a logo", (VOCABULARY / "video/looks.md").read_text())
        for leaf in ("promotion", "story", "ad", "tour", "explainer-video"):
            text = (kernel / "create" / leaf / "SKILL.md").read_text()
            with self.subTest(leaf=leaf):
                self.assertIn('skill_view(name="motion-vocabulary")', text)
                self.assertIn('skill_view(name="motion-vocabulary", file_path="references/core.md")', text)
                self.assertIn("`references/video/`", text)
                self.assertIn('instead of generic "fade", "slide" or "card"', " ".join(text.split()))


if __name__ == "__main__":
    unittest.main()
