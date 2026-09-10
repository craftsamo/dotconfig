"""Tests for the video-creator profile's gateway/A2A wiring with creator."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]


class VideoCreatorRoutingTest(unittest.TestCase):
    def test_gateway_and_creator_wiring(self) -> None:
        video_path = HERMES_ROOT / "profiles" / "video-creator" / "config.yaml"
        video = yaml.safe_load(video_path.read_text())
        root = yaml.safe_load((HERMES_ROOT / "config.yaml").read_text())
        creator = yaml.safe_load((HERMES_ROOT / "profiles/creator/config.yaml").read_text())
        self.assertIn("video-creator", root["gateway"]["multiplex_profile_allowlist"])
        self.assertEqual(9908, video["platforms"]["a2a"]["extra"]["port"])
        self.assertEqual("http://127.0.0.1:9908", creator["a2a_agents"]["video-creator"]["url"])
        self.assertEqual(310, creator["a2a_agents"]["video-creator"]["timeout"])
        self.assertIn("~/.hermes/profiles/video-creator/skills", creator["skills"]["external_dirs"])
        self.assertEqual({}, video["a2a_agents"])


if __name__ == "__main__":
    unittest.main()
