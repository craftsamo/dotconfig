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
