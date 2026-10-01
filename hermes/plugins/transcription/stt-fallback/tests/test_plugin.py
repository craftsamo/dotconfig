from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("stt_fallback", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class KeyAvailabilityTest(unittest.TestCase):
    """Availability must read keys where the built-in transcribers read them (the profile's
    secret scope under a multiplexed gateway), not only the process environment."""

    def test_scoped_key_absent_from_process_env_still_counts(self) -> None:
        def resolver(env_var: str, provider_id: str) -> str:
            return "scoped-key" if (env_var, provider_id) == ("GROQ_API_KEY", "groq") else ""

        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch("tools.tool_backend_helpers.resolve_provider_secret", side_effect=resolver), \
                mock.patch("tools.transcription_tools._HAS_OPENAI", True):
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("ELEVENLABS_API_KEY", None)
            provider = MODULE.FallbackSTTProvider()
            self.assertTrue(provider._available("groq"))
            self.assertFalse(provider._available("elevenlabs"))


if __name__ == "__main__":
    unittest.main()
