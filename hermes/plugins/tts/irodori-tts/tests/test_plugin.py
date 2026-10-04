from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
# Loaded as a package, the way Hermes' plugin loader does it, so the provider's
# relative import of its reading module resolves.
SPEC = importlib.util.spec_from_file_location(
    "irodori_tts", PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

JA = "えっ、本当にそれ言ってるの。"


class FakeResponse:
    """Just enough of the WAV the provider expects back."""

    def __init__(self, audio: bytes) -> None:
        self._audio = audio

    def read(self) -> bytes:
        return self._audio

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _wav() -> bytes:
    import io
    import wave

    import numpy as np

    rate = 24000
    tone = (np.sin(np.linspace(0, 400 * 2 * np.pi, rate)) * 0.5 * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(tone.tobytes())
    return buffer.getvalue()


class RequestPayloadTest(unittest.TestCase):
    """What actually goes on the wire, since style must not leak into the chain."""

    def setUp(self) -> None:
        self.provider = MODULE.IrodoriTTSProvider()
        self.audio = _wav()

    def _send(self, tmp: Path, **kwargs) -> dict:
        captured: dict = {}

        def fake_urlopen(request, *args, **kwargs):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse(self.audio)

        with patch.object(MODULE.urllib.request, "urlopen", fake_urlopen):
            self.provider.synthesize(JA, str(tmp / "out.wav"), format="wav", **kwargs)
        return captured

    def test_chain_call_sends_no_style_options(self) -> None:
        """The ordinary chain passes no style arguments and must send none."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = self._send(Path(tmp), voice="lethe")
        self.assertNotIn("irodori", payload)
        self.assertEqual({"input", "model", "voice"}, set(payload))

    def test_caption_and_seed_travel_in_the_options_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = self._send(Path(tmp), voice="lethe", caption="ゆっくり", seed=7)
        self.assertEqual({"caption": "ゆっくり", "seed": 7}, payload["irodori"])

    def test_blank_caption_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._send(Path(tmp), voice="lethe", caption="   ")

    def test_non_integer_seed_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._send(Path(tmp), voice="lethe", seed="soon")


class ReadingFrontendTest(unittest.TestCase):
    """The reading pass shapes the request text but never costs the utterance."""

    def setUp(self) -> None:
        self.provider = MODULE.IrodoriTTSProvider()
        self.audio = _wav()

    def _sent(self, text: str, config: dict | None = None) -> str:
        captured: dict = {}

        def fake_urlopen(request, *args, **kwargs):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse(self.audio)

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE.urllib.request, "urlopen", fake_urlopen
        ), patch.object(MODULE.IrodoriTTSProvider, "_config", lambda self: config or {}):
            self.provider.synthesize(text, str(Path(tmp) / "out.wav"), format="wav")
        return captured["input"]

    def test_misread_number_forms_are_rewritten_before_the_request(self) -> None:
        sent = self._sent("会員は1,234,567人、成長率は70%です。")
        self.assertEqual("会員は123万4567人、成長率は70パーセントです。", sent)

    def test_numeral_style_comes_from_config(self) -> None:
        sent = self._sent("会議は3月5日です。", {"numerals": "kana"})
        self.assertEqual("会議はさんがついつかです。", sent)

    def test_unknown_numeral_style_falls_back_to_the_default(self) -> None:
        sent = self._sent("会員は1,234,567人です。", {"numerals": "roman"})
        self.assertEqual("会員は123万4567人です。", sent)

    def test_toggle_off_sends_the_text_as_is(self) -> None:
        sent = self._sent("会員は1,234,567人です。", {"reading_frontend": False})
        self.assertEqual("会員は1,234,567人です。", sent)

    def test_emoji_survive_for_the_engine_to_perform(self) -> None:
        text = "えっ\U0001F92D、3回も言ったの。"
        self.assertEqual(text, self._sent(text))

    def test_a_frontend_bug_falls_back_to_the_lexicon_only_text(self) -> None:
        real = MODULE.prepare_text

        def broken(text, **kwargs):
            if kwargs.get("frontend", True):
                raise RuntimeError("boom")
            return real(text, **kwargs)

        with patch.object(MODULE, "prepare_text", broken):
            self.assertEqual("会議は3月5日です。", self._sent("会議は3月5日です。"))


class StyleFeatureTest(unittest.TestCase):
    def test_advertises_the_controls_the_character_tools_ask_about(self) -> None:
        self.assertEqual(
            {"caption", "emoji", "seed"},
            set(MODULE.IrodoriTTSProvider().style_features),
        )


class LanguageGateTest(unittest.TestCase):
    """Emoji must not shift the Japanese-ratio gate that routes the chain."""

    def test_emoji_do_not_count_as_script(self) -> None:
        self.assertEqual(
            MODULE.japanese_ratio(JA),
            MODULE.japanese_ratio(f"えっ\U0001F92D、本当にそれ言ってるの。\U0001F3B5"),
        )

    def test_english_is_still_declined(self) -> None:
        self.assertFalse(MODULE.is_japanese_enough("This is an English sentence."))


if __name__ == "__main__":
    unittest.main()
