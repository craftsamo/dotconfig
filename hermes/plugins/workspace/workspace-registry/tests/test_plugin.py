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
        self.profile_name, self.tools, self.skills = profile, [], {}

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = (path, description)


class RegisterTest(unittest.TestCase):
    def test_only_the_assistant_gets_the_tool(self):
        for profile, n in (("assistant", 1), ("engineer", 0), ("creator", 0)):
            ctx = Ctx(profile)
            plugin.register(ctx)
            self.assertEqual(len(ctx.tools), n, profile)
            self.assertEqual(len(ctx.skills), n, profile)

    def test_skill_is_registered_with_its_own_path(self):
        ctx = Ctx("assistant")
        plugin.register(ctx)
        path, description = ctx.skills["workspace-registry"]
        self.assertEqual(path, HERE / "skills" / "workspace-registry" / "SKILL.md")
        self.assertTrue(description)

    def test_register_skills_skips_other_profiles(self):
        for profile in ("engineer", "creator"):
            ctx = Ctx(profile)
            plugin.register_skills(ctx, profile)
            plugin.register_skills(ctx, profile)
            self.assertEqual(ctx.skills, {}, profile)

    def test_failed_skill_registration_keeps_the_tool(self):
        ctx = Ctx("assistant")
        with mock.patch.dict("sys.modules", {"agent": mock.Mock(), "agent.skill_utils": mock.Mock(
                parse_frontmatter=mock.Mock(side_effect=ValueError("bad")))}):
            with self.assertLogs(plugin.logger, "WARNING") as logs:
                plugin.register(ctx)
        self.assertEqual(len(ctx.tools), 1)
        self.assertEqual(ctx.skills, {})
        self.assertIn("workspace-registry", logs.output[0])

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
