"""The public wrapper must work without a private overlay, including from a link."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
PUBLIC = HERE.parents[3]


def pinned_python(tmp):
    """A PATH whose ``python3`` is this interpreter.

    The launcher ends in ``exec python3``. On a machine where that resolves to a
    version-manager shim, the shim resolves its tools from ``HOME``; the test's
    temporary HOME has none cached, so every launch asks the package registry for
    each ``latest`` tool and the suite crawls (or never ends when that fails).
    """
    shim = Path(tmp) / "pinned-bin"
    shim.mkdir()
    (shim / "python3").symlink_to(sys.executable)
    return f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"


class LauncherTest(unittest.TestCase):
    def test_wrapper_from_a_symlink_uses_its_own_public_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            public = home / "checkout"
            plugin = public / "hermes/plugins/workspace/workspace-registry"
            plugin.mkdir(parents=True)
            bin_dir = public / "bin"
            bin_dir.mkdir()
            for name in ("registry.py", "wsreg"):
                shutil.copy2(HERE / name, plugin / name)
            shutil.copy2(PUBLIC / "bin/wsreg", bin_dir / "wsreg")
            entry = home / "wsreg"
            entry.symlink_to(bin_dir / "wsreg")
            env = dict(os.environ)
            env.update(HOME=str(home), WSREG_ROOT=str(home / "Workspaces"),
                       WSREG_DIR=str(home / "Workspaces/.registry"), PATH=pinned_python(tmp))
            env.pop("WSREG_BIN", None)
            env.pop("DOTCONFIG", None)
            result = subprocess.run([str(entry), "init"], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])
            result = subprocess.run([str(entry), "persons", "--json"], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["data"], {"persons": []})
            self.assertFalse((home / ".config/private").exists())

    def test_explicit_engine_override_is_still_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp) / "synthetic-wsreg"
            engine.write_text('import json\nprint(json.dumps({"override": True}))\n', encoding="utf-8")
            engine.chmod(0o755)
            result = subprocess.run([str(PUBLIC / "bin/wsreg"), "persons"],
                                    env={**os.environ, "WSREG_BIN": str(engine), "PATH": pinned_python(tmp)},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"override": True})

    def test_dotconfig_override_selects_the_intended_public_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "hermes/plugins/workspace/workspace-registry"
            plugin.mkdir(parents=True)
            (plugin / "wsreg").write_text('import json\nprint(json.dumps({"selected": True}))\n',
                                          encoding="utf-8")
            env = {**os.environ, "DOTCONFIG": tmp, "PATH": pinned_python(tmp)}
            env.pop("WSREG_BIN", None)
            result = subprocess.run([str(PUBLIC / "bin/wsreg"), "persons"], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"selected": True})


if __name__ == "__main__":
    unittest.main()
