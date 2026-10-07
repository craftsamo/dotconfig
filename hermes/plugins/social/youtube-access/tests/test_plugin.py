"""The youtube-access plugin: per-profile schemas, the approval gate, A2A and unattended refusals."""

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


plugin = _load("youtube_access_plugin_test", ROOT / "__init__.py")
ya = plugin.ya
CID = "UC" + "a" * 22
VID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(ya, "STORE", tmp_path / "store")
    monkeypatch.setattr(ya, "VENV_PYTHON", tmp_path / "python")
    monkeypatch.setattr(ya, "_video_title", lambda cid, vid: "My video")
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin, "_approvals_bypassed", lambda: False)
    home = tmp_path / "assistant"
    home.mkdir()
    monkeypatch.setattr(plugin, "_home", lambda: home)
    ya._save_channels({CID: {"title": "Mine", "handle": "@mine"}})
    return home


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_registration_per_profile():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        tool = ctx.tools["youtube"]
        assert tool["toolset"] == "youtube_access"
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"] * (2 if profile == "assistant" else 1)
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
    marketer = Ctx("marketer")
    plugin.register(marketer)
    params = marketer.tools["youtube"]["schema"]["parameters"]
    assert set(params["properties"]["action"]["enum"]) == set(ya.READS)
    assert not set(plugin.WRITE_PROPERTIES) & set(params["properties"])
    assert "never change" in marketer.tools["youtube"]["description"]
    assistant = Ctx("assistant")
    plugin.register(assistant)
    assert set(assistant.tools["youtube"]["schema"]["parameters"]["properties"]["action"]["enum"]) == set(ya.ACTIONS)


PRIVATE_ACTIONS = ("my_videos", "analytics", "my_channel", "captions", "download", *ya.WRITES)


def test_searcher_gets_public_youtube_only():
    ctx = Ctx("searcher")
    plugin.register(ctx)
    tool = ctx.tools["youtube"]
    params = tool["schema"]["parameters"]["properties"]
    assert tool["toolset"] == "youtube_access" and [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    assert params["action"]["enum"] == list(ya.PUBLIC_READS)
    assert set(params) == {"action", *plugin.PUBLIC_PROPERTIES}
    assert "channel" not in params and params["kind"]["enum"] == list(ya.SEARCH_KINDS)
    assert not set(plugin.WRITE_PROPERTIES) & set(params)
    for word in ("my_videos (", "analytics (", "my_channel (", "download (", "captions (", "update ("):
        assert word not in tool["description"]
    assert "Nothing can be changed" in tool["description"]


@pytest.mark.parametrize("action", PRIVATE_ACTIONS)
def test_searcher_cannot_reach_own_channel_data_or_writes(action):
    args = {"action": action, "video": VID, "title": "x", "comment": "Ugx" + "c" * 20, "text": "hi"}
    decision = plugin.gate("searcher", tool_name="youtube", args=args)
    assert decision["action"] == "block"
    out = json.loads(plugin.handle("searcher", args))
    assert out["ok"] is False and "action must be one of" in out["error"]
    assert "status" in out["error"] and action not in out["error"].split("one of")[1]


def test_searcher_reads_pass_the_gate_and_bypass_guard_stays():
    for action in ya.PUBLIC_READS:
        assert plugin.gate("searcher", tool_name="youtube", args={"action": action}) is None
    blocked = plugin.gate("searcher", tool_name="terminal", args={"command": "cat ~/.youtube-access/state.json"})
    assert blocked["action"] == "block"


def test_inbound_a2a_never_reaches_searcher(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    searcher_home = tmp_path / "searcher"
    searcher_home.mkdir()
    monkeypatch.setattr(plugin, "_home", lambda: searcher_home)
    blocked = plugin.gate("searcher", tool_name="youtube", args={"action": "status"})
    assert blocked["action"] == "block" and "A2A" in blocked["message"]
    out = json.loads(plugin.handle("searcher", {"action": "status"}))
    assert out["ok"] is False and "A2A" in out["error"]


def test_marketer_handler_refuses_writes():
    out = json.loads(plugin.handle("marketer", {"action": "update", "video": VID, "title": "x"}))
    assert out["ok"] is False and "action must be one of" in out["error"]


def test_gate_asks_for_writes_only():
    assert plugin.gate("assistant", tool_name="youtube", args={"action": "status"}) is None
    decision = plugin.gate("assistant", tool_name="youtube", args={"action": "update", "video": VID, "title": "New"})
    assert decision["action"] == "approve" and decision["rule_key"] == f"youtube-access:edit:{CID}:{VID}"
    assert "My video" in decision["message"] and "title → New" in decision["message"]
    bad = plugin.gate("assistant", tool_name="youtube", args={"action": "update", "video": "nope", "title": "x"})
    assert bad["action"] == "block"
    assert plugin.gate("marketer", tool_name="youtube", args={"action": "reply"})["action"] == "block"


def test_channel_settings_ask_every_time(monkeypatch):
    decision = plugin.gate("assistant", tool_name="youtube", args={"action": "channel_update", "country": "JP"})
    assert decision["action"] == "approve" and decision["rule_key"].startswith("youtube-access:channel_update:")
    assert "country → JP" in decision["message"]
    assert plugin.gate("marketer", tool_name="youtube", args={"action": "channel_update",
                                                              "country": "JP"})["action"] == "block"
    assert plugin.gate("marketer", tool_name="youtube", args={"action": "my_channel"}) is None
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert plugin.gate("assistant", tool_name="youtube", args={"action": "moderate", "comment": "Ugx" + "c" * 20,
                                                               "moderation": "hold"})["message"] == plugin.UNATTENDED


def test_writes_refused_without_a_person(monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    decision = plugin.gate("assistant", tool_name="youtube", args={"action": "update", "video": VID, "title": "x"})
    assert decision == {"action": "block", "message": plugin.UNATTENDED}
    assert plugin.gate("assistant", tool_name="youtube", args={"action": "status"}) is None
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin, "_approvals_bypassed", lambda: True)
    decision = plugin.gate("assistant", tool_name="youtube", args={"action": "reply", "comment": "Ugx" + "c" * 20,
                                                                    "text": "hi"})
    assert decision == {"action": "block", "message": plugin.BYPASSED}
    out = json.loads(plugin.handle("assistant", {"action": "reply", "comment": "Ugx" + "c" * 20, "text": "hi"}))
    assert out["error"] == plugin.BYPASSED


def test_inbound_a2a(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    blocked = plugin.gate("assistant", tool_name="youtube", args={"action": "status"})
    assert blocked["action"] == "block" and "A2A" in blocked["message"]
    # Marketer reads for a peer only when the turn is bound to its own home.
    assert plugin.gate("marketer", tool_name="youtube", args={"action": "status"})["action"] == "block"
    marketer_home = tmp_path / "marketer"
    marketer_home.mkdir()
    monkeypatch.setattr(plugin, "_home", lambda: marketer_home)
    assert plugin.gate("marketer", tool_name="youtube", args={"action": "status"}) is None
    assert json.loads(plugin.handle("marketer", {"action": "status"}))["ok"] is True


def test_gate_blocks_ways_around():
    decision = plugin.gate("marketer", tool_name="terminal", args={"command": "yt-dlp -x https://youtu.be/x"})
    assert decision == {"action": "block", "message": ya.BYPASS_MESSAGE}
    assert plugin.gate("marketer", tool_name="terminal", args={"command": "ls"}) is None


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(ya, "execute", lambda args, home=None, profile=None, bound=False: {"ok": True, "x": "y" * plugin.LIMIT})
    out = json.loads(plugin.handle("assistant", {"action": "status"}))
    assert out["ok"] is False and "narrow" in out["error"]


def test_status_without_a_channel_is_a_hint(monkeypatch):
    ya._save_channels({})
    out = json.loads(plugin.handle("assistant", {"action": "status"}))
    assert out["authorized"] is False and "yaccess auth" in out["note"]


def test_bind_hook_pins_writes_only():
    assert plugin.bind("assistant", tool_name="youtube", args={"action": "status"}) is None
    assert plugin.bind("assistant", tool_name="terminal", args={"command": "ls"}) is None
    pinned = plugin.bind("assistant", tool_name="youtube", args={"action": "reply", "comment": "Ugx" + "c" * 20,
                                                                  "text": "hi"})
    assert pinned == {"action": "modify", "args": {"_bound": {"channel": CID}}}
    out = json.loads(plugin.handle("assistant", {"action": "reply", "comment": "Ugx" + "c" * 20, "text": "hi"}))
    assert out["ok"] is False and "not bound" in out["error"]
