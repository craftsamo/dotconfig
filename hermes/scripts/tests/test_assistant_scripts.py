from __future__ import annotations

import unittest
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[2]


class AssistantScriptTest(unittest.TestCase):
    def test_gateway_launcher_strips_messaging_keys_from_process_env(self) -> None:
        """The multiplex launcher hosts every bot in one process: the
        messaging tokens must NOT reach the process env (each profile's
        secret scope fetches its own bot token via secrets.command), or the
        default profile would poll the assistant's bot and collide with it."""
        launcher = HERMES_ROOT / "launchd" / "bin" / "hermes-gateway-multiplex"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("grep -v -E '^export (TELEGRAM_|DISCORD_)'", text)
        # launchd owns respawns: the supervised child never re-arms a takeover.
        self.assertIn("gateway run --accept-hooks --external-supervisor", text)
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("--replace", code)
        self.assertIn("export HERMES_SUPERVISED_CHILD=1", text)
        self.assertNotIn(" -p assistant", text)
        self.assertFalse((HERMES_ROOT / "launchd" / "hermes-gateway-assistant").exists())


if __name__ == "__main__":
    unittest.main()
