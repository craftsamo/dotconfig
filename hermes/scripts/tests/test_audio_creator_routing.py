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
        expected = {"terminal", "file", "tts", "sfx_gen", "music_gen", "skills", "memory"}
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
        for plugin in ("character-voice", "irodori-tts", "qwen3-tts", "tts-fallback", "sfx-gen", "music-gen", "skill-topology"):
            self.assertIn(plugin, audio_plugins)
        creator_plugins = set(self.creator["plugins"]["enabled"])
        self.assertNotIn("character-voice", creator_plugins)
        self.assertNotIn("sfx-gen", creator_plugins)
        self.assertNotIn("music-gen", creator_plugins)
        self.assertIn("tts", set(self.creator["toolsets"]))
        self.assertNotIn("sfx_gen", set(self.creator["toolsets"]))
        self.assertNotIn("music_gen", set(self.creator["toolsets"]))
        self.assertNotIn("sfx-gen", set(self.image["plugins"]["enabled"]))
        self.assertNotIn("music-gen", set(self.image["plugins"]["enabled"]))

    def test_model_and_fallback_match_image_creator_no_secrets(self) -> None:
        self.assertEqual(self.image["model"], self.audio["model"])
        self.assertEqual(self.image["fallback_providers"], self.audio["fallback_providers"])
        self.assertEqual(self.image["auxiliary"], self.audio["auxiliary"])
        for provider in self.audio["fallback_providers"]:
            self.assertEqual("", provider.get("api_key", ""))

    def test_pipeline_leaves_are_speech_and_sfx_no_source(self) -> None:
        pipeline = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
        for verb in ("generate", "edit", "analyze"):
            self.assertTrue((pipeline / verb / "speech" / "SKILL.md").is_file())
        for verb in ("create", "generate", "edit", "analyze"):
            self.assertTrue((pipeline / verb / "sfx" / "SKILL.md").is_file())
            self.assertTrue((pipeline / verb / "music" / "SKILL.md").is_file())
        self.assertFalse((pipeline / "create" / "speech").exists())
        self.assertFalse((pipeline / "source").exists())
        prompt = self.audio["agent"]["system_prompt"]
        # No blanket "audio is free" claim: speech keeps its 1+1 take grant,
        # generate-sfx is explicitly the metered, paid-approval leaf.
        self.assertIn("600-character script", prompt)
        self.assertIn("generate-sfx", prompt)
        self.assertIn("metered", prompt)
        self.assertIn("paid approval", prompt)

    def test_music_family_leaves_and_toolset(self) -> None:
        """New music subject: served, AudioCreator-only, no song/mix scope creep."""
        pipeline = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
        for verb in ("create", "generate", "edit", "analyze"):
            self.assertTrue((pipeline / verb / "music" / "SKILL.md").is_file())
        self.assertIn("music_gen", set(self.audio["toolsets"]))
        self.assertIn("music_gen", set(self.audio["platform_toolsets"]["cli"]))
        self.assertIn("music_gen", set(self.audio["platform_toolsets"]["a2a"]))
        self.assertEqual([], self.audio["platform_toolsets"]["telegram"])
        self.assertEqual([], self.audio["platform_toolsets"]["discord"])
        self.assertIn("music-gen", set(self.audio["plugins"]["enabled"]))
        plugin_yaml = yaml.safe_load(
            (HERMES_ROOT / "plugins" / "audio_gen" / "music-gen" / "plugin.yaml").read_text()
        )
        self.assertEqual("music-gen", plugin_yaml["name"])
        plugin_source = (HERMES_ROOT / "plugins" / "audio_gen" / "music-gen" / "__init__.py").read_text()
        self.assertIn('ctx.profile_name != "audio-creator"', plugin_source)
        audio_prompt = self.audio["agent"]["system_prompt"]
        self.assertIn("create-music", audio_prompt)
        self.assertIn("generate-music", audio_prompt)
        self.assertIn("edit-music", audio_prompt)
        self.assertIn("analyze-music", audio_prompt)
        self.assertIn("no skill fits", audio_prompt)
        creator_prompt = self.creator["agent"]["system_prompt"]
        self.assertIn("create-music", creator_prompt)
        self.assertIn("generate-music", creator_prompt)

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

    def test_parse_frontmatter_music_leaf_names(self) -> None:
        """agent.skill_utils.parse_frontmatter must recover each music leaf's real ``name``
        from within the first 4000 chars tools.skills_tool._find_all_skills reads — the
        closing ``---`` fence must land before that cutoff or the frontmatter parses empty
        and the skill falls back to its parent directory name ('music') for all four leaves."""
        from agent.skill_utils import parse_frontmatter

        pipeline = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
        expected_names = {
            "create": "create-music",
            "generate": "generate-music",
            "edit": "edit-music",
            "analyze": "analyze-music",
        }
        for verb, expected_name in expected_names.items():
            text = (pipeline / verb / "music" / "SKILL.md").read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(text[:4000])
            self.assertEqual(expected_name, frontmatter.get("name"))

    def test_find_all_skills_discovers_music_leaves_once_each(self) -> None:
        """tools.skills_tool._find_all_skills, scoped to only this profile's skill root, must
        discover the pipeline root plus all 11 leaves (3 speech + 4 sfx + 4 music) with their
        real distinct names — no generic 'music' fallback, no first-wins duplicate dropped."""
        import tools.skills_tool as skills_tool

        pipeline = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
        with patch.object(skills_tool, "_skill_search_dirs", return_value=([], [pipeline], pipeline)), \
             patch.object(skills_tool, "_get_disabled_skill_names", return_value=set()), \
             patch.object(skills_tool, "_SKILLS_CACHE", {}):
            skills = skills_tool._find_all_skills()

        names = [s["name"] for s in skills]
        self.assertEqual(12, len(names))
        self.assertEqual(12, len(set(names)))
        self.assertNotIn("music", names)
        for expected_name in (
            "audio-creator-pipeline",
            "generate-speech", "edit-speech", "analyze-speech",
            "create-sfx", "generate-sfx", "edit-sfx", "analyze-sfx",
            "create-music", "generate-music", "edit-music", "analyze-music",
        ):
            self.assertEqual(1, names.count(expected_name))

    def _assert_toolset_profile_scoped(self, tool_name: str, toolset_name: str) -> None:
        """Shared body: *tool_name* registered under *toolset_name* only in the audio-creator
        scope must resolve there and nowhere else, across alternating scope lookups (guards the
        profile-scoped memo, not just a single lookup)."""
        import toolsets
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from tools.registry import ToolRegistry

        reg = ToolRegistry()
        with tempfile.TemporaryDirectory() as temp, patch("tools.registry.registry", reg), patch.object(toolsets, "_resolve_toolset_memo", {}):
            audio_home = Path(temp) / "audio"
            token = set_hermes_home_override(audio_home)
            try:
                reg.register(
                    name=tool_name, toolset=toolset_name,
                    schema={"name": tool_name, "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
                    handler=lambda args, **kwargs: "{}", scope=reg.current_scope_key(),
                )
            finally:
                reset_hermes_home_override(token)
            for home in (Path(temp) / "creator", audio_home, Path(temp) / "creator", audio_home):
                token = set_hermes_home_override(home)
                try:
                    self.assertEqual(
                        home == audio_home, tool_name in toolsets.resolve_toolset(toolset_name),
                        f"Hermes resolve_toolset cache must keep {toolset_name} scoped to audio-creator",
                    )
                finally:
                    reset_hermes_home_override(token)

    def test_runtime_toolset_cache_keeps_sfx_gen_profile_scoped(self) -> None:
        """sfx_gen must resolve only for audio-creator's scope, same fix as tts."""
        self._assert_toolset_profile_scoped("sfx_engines", "sfx_gen")

    def test_runtime_toolset_cache_keeps_music_gen_profile_scoped(self) -> None:
        """music_gen must resolve only for audio-creator's scope, same fix as sfx_gen/tts:
        the toolset-cache memo must key on profile scope, not just registry generation."""
        self._assert_toolset_profile_scoped("music_engines", "music_gen")

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
