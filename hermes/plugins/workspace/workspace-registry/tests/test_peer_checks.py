"""Standalone and opt-in integrations use synthetic records and local code only."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
VALID_HOOK = '''
def validate_warnings(reg, norm):
    return ["synthetic peer warning"]
def rename_note(kind, old, new):
    return "update the external reference" if kind == "person" else None
'''


class PeerChecksTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.plugin = self.base / "plugin"
        self.plugin.mkdir()
        for name in ("registry.py", "wsreg"):
            shutil.copy2(HERE / name, self.plugin / name)
        spec = importlib.util.spec_from_file_location("registry_peer_test", self.plugin / "registry.py")
        self.engine = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.engine
        self.addCleanup(lambda: sys.modules.pop(spec.name, None))
        spec.loader.exec_module(self.engine)
        self.root = self.base / "Workspaces"
        self.root.mkdir()
        env_patch = mock.patch.dict(os.environ, {"WSREG_DIR": str(self.root / ".registry"),
                                                "GHQ_ROOT": str(self.base / "ghq")})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.engine.init(self.root)
        self.run_action(action="person_set", id="ann", fields={"display_name": "Ann"})

    def run_action(self, **args):
        return self.engine.run(args, root=self.root)

    def hook(self, text=VALID_HOOK):
        private = self.base / "private"
        private.mkdir()
        target = private / "checks.py"
        target.write_text(text, encoding="utf-8")
        (self.plugin / "peer_checks.py").symlink_to(target)

    def test_absence_does_not_require_an_overlay(self):
        out = self.run_action(action="validate")
        self.assertTrue(out["ok"])
        self.assertEqual(out["warnings"], [])

    def test_real_symlink_adds_checks_and_preserves_rename_note(self):
        self.hook()
        out = self.run_action(action="validate")
        self.assertTrue(out["ok"])
        self.assertEqual(out["warnings"], ["synthetic peer warning"])
        out = self.run_action(action="rename", person="ann", new_id="ann_lee")
        self.assertEqual(out["note"], "update the external reference")
        self.assertTrue(out["ok"])

    def test_dangling_installed_link_is_not_absence(self):
        (self.plugin / "peer_checks.py").symlink_to(self.base / "missing.py")
        out = self.run_action(action="validate")
        self.assertTrue(out["ok"])
        self.assertIn("peer checks configured but unusable", out["warnings"][0])
        out = self.run_action(action="rename", person="ann", new_id="ann_lee")
        self.assertTrue(out["ok"])
        self.assertIn("peer checks configured but unusable", out["warnings"][0])
        self.assertEqual(self.run_action(action="person", id="ann_lee")["person"]["id"], "ann_lee")

    def test_invalid_interfaces_and_failures_are_visible(self):
        for text in (
            "raise RuntimeError('failed import')\n",
            "def validate_warnings(reg, norm): return []\n",
            VALID_HOOK.replace('return ["synthetic peer warning"]', "return 'not a list'"),
            VALID_HOOK.replace('return ["synthetic peer warning"]', "raise ValueError('failed check')"),
        ):
            with self.subTest(text=text):
                (self.plugin / "peer_checks.py").write_text(text, encoding="utf-8")
                out = self.run_action(action="validate")
                self.assertTrue(out["ok"])
                self.assertEqual(len(out["warnings"]), 1)
                self.assertIn("peer checks configured but unusable", out["warnings"][0])

    def test_bad_rename_result_does_not_roll_back(self):
        self.hook(VALID_HOOK.replace('return "update the external reference" if kind == "person" else None',
                                     "return 42"))
        out = self.run_action(action="rename", person="ann", new_id="ann_lee")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["note"])
        self.assertIn("rename_note must return", out["warnings"][0])

    def test_cli_and_engine_both_use_the_hook(self):
        self.hook()
        env = dict(os.environ)
        env.pop("WSREG_DIR", None)
        result = subprocess.run([sys.executable, str(self.plugin / "wsreg"), "--root", str(self.root),
                                 "validate", "--json"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 warning(s)", result.stdout)
        self.assertIn("synthetic peer warning", result.stderr)

    def test_tool_arguments_cannot_select_a_hook(self):
        self.assertEqual(self.run_action(action="validate", peer_checks="/untrusted.py")["warnings"], [])


if __name__ == "__main__":
    unittest.main()
