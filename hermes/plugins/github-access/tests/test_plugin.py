import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("github_access_plugin_test", ROOT / "__init__.py")


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_the_progress_line_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda tool, **args: display.build_tool_preview(tool, args, max_len=0)  # noqa: E731
    assert line("github_issue", action="list", repo="acme/secret", query="someone's name") == "list"
    assert line("github_issue", action="view", issue="acme/secret#3") == "view"
    assert line("github_board", action="items", project="Private plans", search="layoffs") == "items"
    for tool in ("github_issue", "github_board"):
        assert line(tool, action="anything else", query="someone's name") is None


def test_only_the_assistant_gets_the_tools():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == set(plugin.ENGINES)
    assert {t["toolset"] for t in ctx.tools.values()} == {"github_access"}
    for name, tool in ctx.tools.items():
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == plugin.REQUIRED[name]


def test_action_enums_match_the_engine():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    props = {name: tool["schema"]["parameters"]["properties"] for name, tool in ctx.tools.items()}
    assert props["github_issue"]["action"]["enum"] == list(plugin.access.ISSUE_ACTIONS)
    assert props["github_board"]["action"]["enum"] == list(plugin.access.BOARD_ACTIONS)


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    result = json.loads(plugin.github_board({"action": "items"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handlers_return_json_errors_and_refuse_oversized_results(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    result = json.loads(plugin.github_issue({"action": "view"}))
    assert result == {"ok": False, "error": "issue is required"}
    monkeypatch.setitem(plugin.ENGINES, "github_board", lambda args: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.github_board({"action": "items"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_the_skills_reach_only_the_assistant():
    for profile, names in (("assistant", set(plugin.SKILLS)), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
