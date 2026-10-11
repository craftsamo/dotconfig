"""Tests for the workspace_registry tool. Run: python3 -m unittest discover -s <this dir>"""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workspace_registry_plugin_under_test", HERE / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class Ctx:
    def __init__(self, profile):
        self.profile_name, self.tools = profile, []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class RegisterTest(unittest.TestCase):
    def test_only_the_assistant_gets_the_tool(self):
        for profile, n in (("assistant", 1), ("engineer", 0), ("creator", 0)):
            ctx = Ctx(profile)
            plugin.register(ctx)
            self.assertEqual(len(ctx.tools), n, profile)

    def test_schema_matches_the_engine(self):
        ctx = Ctx("assistant")
        plugin.register(ctx)
        tool = ctx.tools[0]
        self.assertEqual((tool["name"], tool["toolset"]), ("workspace_registry", "workspace_registry"))
        params = tool["schema"]["parameters"]
        self.assertEqual(params["required"], ["action"])
        self.assertFalse(params["additionalProperties"])
        self.assertEqual(params["properties"]["action"]["enum"], list(plugin.registry.ACTIONS))
        # every non-action key the engine reads must be declared, or the model can never send it
        for key in ("id", "person", "project", "name", "new_id", "query", "status", "kind", "organization",
                    "facet", "value", "channel", "proficiency", "axis", "label", "primary", "date", "fields"):
            self.assertIn(key, params["properties"])


class HandlerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "Projects").mkdir()
        self._env = mock.patch.dict(os.environ, {"WSREG_ROOT": str(self.root)})
        self._env.start()
        os.environ.pop("WSREG_DIR", None)
        plugin.registry.init(self.root)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def call(self, **args):
        return json.loads(plugin.workspace_registry(args))

    def test_round_trip_through_the_handler(self):
        out = self.call(action="person_set", id="ann", fields={"display_name": "Ann"})
        self.assertTrue(out["ok"])
        self.assertEqual(self.call(action="whois", query="ann")["matches"][0]["id"], "ann")

    def test_errors_are_json_not_exceptions(self):
        out = self.call(action="person", id="nobody")
        self.assertEqual(out, {"ok": False, "error": "no person 'nobody'"})
        self.assertIn("action must be one of", self.call(action="drop_everything")["error"])

    def test_inbound_a2a_is_refused(self):
        with mock.patch.object(plugin, "_inbound_peer", return_value=True):
            out = self.call(action="persons")
        self.assertIn("not available to inbound A2A", out["error"])


if __name__ == "__main__":
    unittest.main()
