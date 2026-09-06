"""Tests for the audio-creator profile's gateway/A2A wiring with creator."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]


class AudioCreatorRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audio = yaml.safe_load(
            (HERMES_ROOT / "profiles" / "audio-creator" / "config.yaml").read_text()
        )
        cls.root = yaml.safe_load((HERMES_ROOT / "config.yaml").read_text())
        cls.creator = yaml.safe_load(
            (HERMES_ROOT / "profiles" / "creator" / "config.yaml").read_text()
        )
        cls.image = yaml.safe_load(
            (HERMES_ROOT / "profiles" / "image-creator" / "config.yaml").read_text()
        )

    def test_root_allowlist_and_creator_peer(self) -> None:
        self.assertIn(
            "audio-creator", self.root["gateway"]["multiplex_profile_allowlist"]
        )
        self.assertEqual(9909, self.audio["platforms"]["a2a"]["extra"]["port"])
        self.assertEqual(
            "http://127.0.0.1:9909",
            self.creator["a2a_agents"]["audio-creator"]["url"],
        )
        self.assertEqual(310, self.creator["a2a_agents"]["audio-creator"]["timeout"])
        self.assertIn(
            "~/.hermes/profiles/audio-creator/skills",
            self.creator["skills"]["external_dirs"],
        )

    def test_toolsets_are_exact_allowlist_no_broad_grants(self) -> None:
        expected = {"terminal", "file", "tts", "skills", "memory"}
        self.assertEqual(expected, set(self.audio["toolsets"]))
        self.assertNotIn("no_mcp", self.audio["toolsets"])
        platform_toolsets = self.audio["platform_toolsets"]
        self.assertEqual(expected | {"no_mcp"}, set(platform_toolsets["cli"]))
        self.assertEqual(expected | {"no_mcp"}, set(platform_toolsets["a2a"]))
        self.assertEqual([], platform_toolsets["telegram"])
        self.assertEqual([], platform_toolsets["discord"])
        self.assertEqual({}, self.audio["a2a_agents"])
        for forbidden in ("a2a", "delegation", "video", "video_gen", "image_gen"):
            self.assertNotIn(forbidden, self.audio["toolsets"])

    def test_plugins_enable_tts_and_character_voice_not_on_creator(self) -> None:
        audio_plugins = set(self.audio["plugins"]["enabled"])
        for plugin in ("character-voice", "irodori-tts", "qwen3-tts", "tts-fallback", "skill-topology"):
            self.assertIn(plugin, audio_plugins)
        creator_plugins = set(self.creator["plugins"]["enabled"])
        self.assertNotIn("character-voice", creator_plugins)
        self.assertIn("tts", set(self.creator["toolsets"]))

    def test_model_and_fallback_match_image_creator_no_secrets(self) -> None:
        self.assertEqual(self.image["model"], self.audio["model"])
        self.assertEqual(self.image["fallback_providers"], self.audio["fallback_providers"])
        self.assertEqual(self.image["auxiliary"], self.audio["auxiliary"])
        for provider in self.audio["fallback_providers"]:
            self.assertEqual("", provider.get("api_key", ""))

    def test_pipeline_leaves_are_speech_only_no_source_or_create(self) -> None:
        pipeline = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
        for verb in ("generate", "edit", "analyze"):
            self.assertTrue((pipeline / verb / "speech" / "SKILL.md").is_file())
        for forbidden_verb in ("source", "create"):
            self.assertFalse((pipeline / forbidden_verb).exists())
        prompt = self.audio["agent"]["system_prompt"]
        self.assertIn("costs no", prompt)
        self.assertIn("600-character script", prompt)

    def test_docs_list_all_three_hands_and_no_tts_voice_residue(self) -> None:
        profiles_md = (HERMES_ROOT / "PROFILES.md").read_text()
        self.assertIn("image-creator", profiles_md)
        self.assertIn("video-creator", profiles_md)
        self.assertIn("audio-creator", profiles_md)
        self.assertNotIn("tts-voice", profiles_md)
        creator_prompt = self.creator["agent"]["system_prompt"]
        self.assertIn("image-creator", creator_prompt)
        self.assertIn("video-creator", creator_prompt)
        self.assertIn("audio-creator", creator_prompt)
        self.assertNotIn("tts-voice", creator_prompt)

    def test_private_assistant_catalog_optional(self) -> None:
        """Only checked when the private overlay is present (not on a public clone)."""
        references = (
            HERMES_ROOT
            / "profiles"
            / "assistant"
            / "skills"
            / "assistant-pipeline"
            / "references"
        )
        index = references / "execute" / "creative" / "index.md"
        if not index.is_file():
            self.skipTest("private assistant catalog overlay not present")
        contents = index.read_text()
        self.assertNotIn("tts-voice", contents)
        self.assertIn("audio-creator", contents)
        for retired in ("voice", "audio-generation", "song-generation", "audio-visualization"):
            self.assertFalse((references / "plan" / "creative" / f"{retired}.md").exists())

    def test_runtime_toolset_cache_keeps_profile_overlay(self) -> None:
        """Guard the upstream scope-key fix required by a multiplexed TTS hand."""
        import toolsets
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from tools.registry import ToolRegistry

        reg = ToolRegistry()
        with tempfile.TemporaryDirectory() as temp, patch("tools.registry.registry", reg), patch.object(toolsets, "_resolve_toolset_memo", {}):
            audio_home = Path(temp) / "audio"
            token = set_hermes_home_override(audio_home)
            try:
                reg.register(
                    name="speech_scope_probe", toolset="tts",
                    schema={"name": "speech_scope_probe", "parameters": {"type": "object", "properties": {}}},
                    handler=lambda args, **kwargs: "{}", scope=reg.current_scope_key(),
                )
            finally:
                reset_hermes_home_override(token)
            for home in (Path(temp) / "creator", audio_home, Path(temp) / "creator", audio_home):
                token = set_hermes_home_override(home)
                try:
                    self.assertEqual(
                        home == audio_home, "speech_scope_probe" in toolsets.resolve_toolset("tts"),
                        "Hermes resolve_toolset cache must include profile scope",
                    )
                finally:
                    reset_hermes_home_override(token)


if __name__ == "__main__":
    unittest.main()
