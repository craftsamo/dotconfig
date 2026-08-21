from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("character_voice", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

LAUGH = "\U0001F92D"
SIGH = "\U0001F62E\u200D\U0001F4A8"
HEART = "\u2764\uFE0F"


class StubProvider:
    """Minimal provider: records what the tool decided to send it."""

    def __init__(self, features: set[str]) -> None:
        self._features = frozenset(features)
        self.calls: list[dict] = []

    @property
    def style_features(self) -> frozenset:
        return self._features

    def is_available(self) -> bool:
        return True

    def list_voices(self) -> list[dict]:
        return [{"id": "lethe"}]

    def synthesize(self, text: str, output_path: str, **kwargs) -> str:
        self.calls.append({"text": text, **kwargs})
        Path(output_path).write_bytes(b"stub-audio")
        return output_path


class SpokenScriptTest(unittest.TestCase):
    """Emoji survive the shared cleaner only when the engine performs them."""

    def test_emoji_removed_by_default(self) -> None:
        self.assertEqual(
            "えっ、本当にそれ言ってるの。",
            MODULE._spoken(f"えっ{LAUGH}、本当にそれ言ってるの。"),
        )

    def test_emoji_kept_when_requested(self) -> None:
        text = f"えっ{LAUGH}、本当にそれ言ってるの。"
        self.assertEqual(text, MODULE._spoken(text, keep_emoji=True))

    def test_keeps_whole_cluster(self) -> None:
        """A ZWJ sequence is one gesture; half of it is not a smaller gesture."""
        for cluster in (SIGH, HEART):
            with self.subTest(cluster=cluster):
                kept = MODULE._spoken(f"はぁ{cluster}、まあいいけどね。", keep_emoji=True)
                self.assertIn(cluster, kept)

    def test_placeholder_never_survives(self) -> None:
        kept = MODULE._spoken(f"{LAUGH}{LAUGH}{LAUGH} 三連。", keep_emoji=True)
        self.assertNotIn("zqxj", kept)
        self.assertEqual(3, len(MODULE._EMOJI_CLUSTER.findall(kept)))

    def test_script_containing_the_placeholder_is_not_corrupted(self) -> None:
        """Restoration is a plain replace, so the token must not occur already."""
        collide = MODULE._EMOJI_SLOT_SEED
        kept = MODULE._spoken(f"{collide}0{collide} と {LAUGH}", keep_emoji=True)
        self.assertEqual(1, len(MODULE._EMOJI_CLUSTER.findall(kept)))
        self.assertIn(f"{collide}0{collide}", kept)

    def test_cleaner_still_applies_on_the_keep_path(self) -> None:
        """Parking emoji must not cost the script its normal cleanup."""
        kept = MODULE._spoken(f"## 見出し\n**強調**した文。25°C だって。{LAUGH}", keep_emoji=True)
        self.assertNotIn("#", kept)
        self.assertNotIn("**", kept)
        self.assertNotIn("\n", kept)
        self.assertIn("degrees Celsius", kept)
        self.assertIn(LAUGH, kept)

    def test_empty_after_cleanup_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            MODULE._spoken("   ", keep_emoji=True)


class StyleContractTest(unittest.TestCase):
    """A control the named engine does not advertise is an error, not a no-op."""

    def setUp(self) -> None:
        self.styled = StubProvider({"caption", "emoji", "seed"})
        self.plain = StubProvider(set())
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._real_provider = MODULE._provider
        MODULE._provider = lambda engine: (
            self.styled if engine == "irodori-tts" else self.plain
        )
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(setattr, MODULE, "_provider", self._real_provider)

    def render(self, **args) -> dict:
        args.setdefault("text", f"えっ{LAUGH}、本当にそれ言ってるの。")
        args.setdefault("output_path", str(self.tmp / f"take{len(self.styled.calls)}.ogg"))
        return json.loads(MODULE._character_text_to_speech(args))

    def test_styled_engine_receives_caption_and_keeps_emoji(self) -> None:
        result = self.render(voice="irodori-tts:lethe", style="ゆっくり")
        self.assertTrue(result["success"])
        call = self.styled.calls[-1]
        self.assertEqual("ゆっくり", call["caption"])
        self.assertIn(LAUGH, call["text"])
        self.assertEqual("ゆっくり", result["style"])

    def test_named_voice_is_sent_verbatim(self) -> None:
        """The caller pinned the sound; nothing here may substitute it."""
        result = self.render(voice="irodori-tts:lethe", speed=1.1)
        self.assertEqual("lethe", self.styled.calls[-1]["voice"])
        self.assertEqual(1.1, self.styled.calls[-1]["speed"])
        self.assertEqual("irodori-tts:lethe", result["id"])

    def test_engine_failure_is_an_error_not_a_hand_off(self) -> None:
        """A pinned engine has no next tier, so a failure must read as final."""

        def boom(*args, **kwargs):
            raise RuntimeError("server unavailable")

        self.styled.synthesize = boom
        with self.assertLogs(MODULE.logger, level="ERROR"):
            result = self.render(voice="irodori-tts:lethe")
        self.assertFalse(result["success"])
        self.assertIn("no other engine was tried", result["error"])
        self.assertEqual([], self.plain.calls)

    def test_seed_is_always_pinned_and_reported(self) -> None:
        """An unpinned take cannot be matched by a later part, so never leave one."""
        result = self.render(voice="irodori-tts:lethe")
        self.assertIsInstance(result["seed"], int)
        self.assertEqual(result["seed"], self.styled.calls[-1]["seed"])

    def test_explicit_seed_passes_through(self) -> None:
        result = self.render(voice="irodori-tts:lethe", seed=4242)
        self.assertEqual(4242, result["seed"])
        self.assertEqual(4242, self.styled.calls[-1]["seed"])

    def test_plain_engine_strips_emoji_and_gets_no_style_arguments(self) -> None:
        result = self.render(voice="qwen3-tts:lethe")
        call = self.plain.calls[-1]
        self.assertNotIn(LAUGH, call["text"])
        self.assertNotIn("caption", call)
        self.assertNotIn("seed", call)
        self.assertNotIn("seed", result)

    def test_style_on_unsupporting_engine_is_refused(self) -> None:
        result = self.render(voice="qwen3-tts:lethe", style="ゆっくり")
        self.assertFalse(result["success"])
        self.assertIn("qwen3-tts", result["error"])
        self.assertEqual([], self.plain.calls)

    def test_seed_on_unsupporting_engine_is_refused(self) -> None:
        result = self.render(voice="qwen3-tts:lethe", seed=1)
        self.assertFalse(result["success"])
        self.assertEqual([], self.plain.calls)

    def test_malformed_style_is_refused_not_read_as_absent(self) -> None:
        """Silently treating a bad control as "none" renders the wrong take."""
        for bad in ([], "", "   ", 7, {"tone": "calm"}):
            with self.subTest(style=bad):
                result = self.render(voice="irodori-tts:lethe", style=bad)
                self.assertFalse(result["success"])
                self.assertIn("style", result["error"])

    def test_malformed_seed_is_refused(self) -> None:
        for bad in (7.9, "7", True, [7]):
            with self.subTest(seed=bad):
                result = self.render(voice="irodori-tts:lethe", seed=bad)
                self.assertFalse(result["success"])
                self.assertIn("seed", result["error"])

    def test_explicit_null_reads_as_not_supplied(self) -> None:
        """`{"style": null}` from a model means "none" -- refusing it would
        reject a well-formed call, so it must behave exactly like omitting it."""
        null = self.render(voice="irodori-tts:lethe", style=None, seed=None)
        self.assertTrue(null["success"])
        self.assertNotIn("caption", self.styled.calls[-1])
        self.assertIn("seed", self.styled.calls[-1])  # still auto-pinned

        omitted = self.render(voice="irodori-tts:lethe")
        self.assertEqual(
            "caption" in self.styled.calls[-1], "caption" in self.styled.calls[-2]
        )

    def test_explicit_null_seed_is_accepted_on_a_seedless_engine(self) -> None:
        """Null is absence, so it must not trip the unsupported-control refusal."""
        result = self.render(voice="qwen3-tts:lethe", style=None, seed=None)
        self.assertTrue(result["success"])
        self.assertNotIn("seed", self.plain.calls[-1])

    def test_refused_render_leaves_no_file(self) -> None:
        path = self.tmp / "refused.ogg"
        result = self.render(voice="qwen3-tts:lethe", style="x", output_path=str(path))
        self.assertFalse(result["success"])
        self.assertFalse(path.exists())

    def test_engine_listing_reports_style_features(self) -> None:
        payload = json.loads(MODULE._character_voices())
        features = {e["name"]: e["style"] for e in payload["engines"]}
        self.assertEqual(["caption", "emoji", "seed"], features["irodori-tts"])
        self.assertEqual([], features["qwen3-tts"])


class RegistrationTest(unittest.TestCase):
    """Creator owns character assets; nothing else may spend an engine on one."""

    class FakeContext:
        def __init__(self, profile_name: str) -> None:
            self.profile_name = profile_name
            self.tools: list[str] = []

        def register_tool(self, *, name: str, **kwargs) -> None:
            self.tools.append(name)

    def test_registered_only_for_creator(self) -> None:
        creator = self.FakeContext("creator")
        assistant = self.FakeContext("assistant")
        MODULE.register(creator)
        MODULE.register(assistant)
        self.assertEqual(
            ["character_voices", "character_text_to_speech"], creator.tools
        )
        self.assertEqual([], assistant.tools)


if __name__ == "__main__":
    unittest.main()
