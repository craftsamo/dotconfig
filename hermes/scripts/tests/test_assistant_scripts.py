from __future__ import annotations

import re
import subprocess
import tempfile
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

    def test_gateway_launcher_starts_in_the_layout_root_or_falls_back(self) -> None:
        """The gateway's working directory is the workspace layout's root; when the layout cannot
        be read it is ~/Workspaces as before, and $HOME when that is missing."""
        launcher = (HERMES_ROOT / "launchd" / "bin" / "hermes-gateway-multiplex").read_text(encoding="utf-8")
        block = re.search(r"^WORKSPACES_DIR=.*?^unset WORKSPACES_DIR$", launcher, re.M | re.S).group(0)
        with tempfile.TemporaryDirectory() as tmp:
            home, stubs = Path(tmp) / "home", Path(tmp) / "bin"
            (home / "Elsewhere").mkdir(parents=True)
            stubs.mkdir()
            stub = stubs / "hermes-python"

            def cwd(stub_body: str) -> str:
                stub.write_text(f"#!/bin/sh\n{stub_body}\n")
                stub.chmod(0o755)
                script = f"set -e\n{block}\npwd -P\n"
                env = {"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin"}
                return subprocess.run(["sh", "-c", script], env=env, capture_output=True, text=True,
                                      check=True).stdout.strip()

            real_home = str(home.resolve())
            self.assertEqual(cwd(f"echo {home}/Elsewhere"), f"{real_home}/Elsewhere")
            self.assertEqual(cwd("exit 1"), real_home)               # no ~/Workspaces either
            (home / "Workspaces").mkdir()
            self.assertEqual(cwd("exit 1"), f"{real_home}/Workspaces")


if __name__ == "__main__":
    unittest.main()
