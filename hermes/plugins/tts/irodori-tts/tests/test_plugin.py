from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("irodori_tts", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
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
