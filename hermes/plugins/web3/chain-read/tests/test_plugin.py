import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("web3_chain_read_plugin_test", ROOT / "__init__.py")


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    python = tmp_path / "python"
    python.write_text("")
    monkeypatch.setattr(plugin, "VENV_PYTHON", python)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "assistant")


def fake_engine(monkeypatch, reply, seen=None):
    def run(cmd, **kwargs):
        if seen is not None:
            seen.append({"cmd": cmd, **kwargs})
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(reply), stderr="")
    monkeypatch.setattr(plugin.subprocess, "run", run)


def test_four_profiles_get_the_read_tool():
    for profile in ("creator", "writer", "engineer", "default"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        tool = ctx.tools["chain"]
        assert tool["toolset"] == "web3_read" and tool["schema"]["name"] == "chain"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action", "chain"]
        assert set(params["properties"]["chain"]["enum"]) == set(plugin.chains.CHAINS)
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]


def test_there_is_no_write_action():
    actions = set(plugin.EVM_ACTIONS) | set(plugin.SOLANA_ACTIONS)
    assert not {"send", "transfer", "sign", "approve", "swap", "quote"} & actions


def test_untrusted_text_is_named_in_the_description():
    assert "untrusted" in plugin.DESCRIPTION and "never followed" in plugin.DESCRIPTION


def test_unknown_chain_and_unavailable_action_are_refused(monkeypatch):
    fake_engine(monkeypatch, {"ok": True, "data": {}})
    tool = plugin.handler_for("assistant")
    reply = json.loads(tool({"action": "block", "chain": "dogechain"}))
    assert reply["ok"] is False and "unknown chain" in reply["error"]
    reply = json.loads(tool({"action": "logs", "chain": "solana"}))
    assert reply["ok"] is False and "not available on solana" in reply["error"]
    gate = plugin.gate_for("assistant")
    assert gate(tool_name="chain", args={"action": "logs", "chain": "solana"})["action"] == "block"
    assert gate(tool_name="chain", args={"action": "tx", "chain": "base", "hash": "0x" + "1" * 64}) is None


def test_only_schema_fields_reach_the_engine(monkeypatch):
    seen = []
    fake_engine(monkeypatch, {"ok": True, "data": {"number": 1}}, seen)
    reply = json.loads(plugin.handler_for("searcher")(
        {"action": "block", "chain": "sepolia", "_rpc": "http://evil", "_offline": True, "block": "latest"}))
    assert reply == {"ok": True, "data": {"number": 1}}
    payload = json.loads(seen[0]["input"])
    assert payload == {"action": "block", "chain": "sepolia", "block": "latest"}
    env = seen[0]["env"]
    assert set(env) == {"HOME", "PATH", "LANG", "PYTHONDONTWRITEBYTECODE"}
    assert seen[0]["cmd"][1].endswith("_shared/reader.py")


def test_missing_engine_and_oversized_results_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "VENV_PYTHON", tmp_path / "missing")
    reply = json.loads(plugin.handler_for("assistant")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "web3.sh install" in reply["error"]
    monkeypatch.setattr(plugin, "VENV_PYTHON", tmp_path / "python")
    fake_engine(monkeypatch, {"ok": True, "data": {"x": "y" * (plugin.LIMIT + 10)}})
    reply = json.loads(plugin.handler_for("assistant")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "narrow it" in reply["error"]


def test_inbound_a2a_reads_only_on_the_specialists(monkeypatch, tmp_path):
    fake_engine(monkeypatch, {"ok": True, "data": {}})
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "assistant")
    reply = json.loads(plugin.handler_for("assistant")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "inbound A2A" in reply["error"]
    for profile in ("researcher", "searcher", "marketer"):
        monkeypatch.setattr(plugin, "_home", lambda p=profile: tmp_path / p)
        assert json.loads(plugin.handler_for(profile)({"action": "gas", "chain": "base"}))["ok"] is True


def test_gate_blocks_ways_around_the_tool():
    gate = plugin.gate_for("marketer")
    blocked = [
        ("terminal", {"command": "secret get ALCHEMY_API_KEY -p hermes --scope web3-rpc"}),
        ("terminal", {"command": "~/.config/hermes/local/web3/venv/bin/python reader.py"}),
        ("terminal", {"command": "security find-generic-password -s x"}),
        ("execute_code", {"code": "import os; os.system('secret show HELIUS_API_KEY')"}),
        ("read_file", {"path": "~/.config/hermes/local/web3/venv/pyvenv.cfg"}),
    ]
    for tool, args in blocked:
        directive = gate(tool_name=tool, args=args)
        assert directive and directive["action"] == "block", (tool, args)
    allowed = [
        ("terminal", {"command": "ls ~/Workspaces"}),
        ("read_file", {"path": "/Users/u/.config/hermes/plugins/web3/_shared/evm.py"}),
        ("web_search", {"query": "web3-rpc providers"}),
    ]
    for tool, args in allowed:
        assert gate(tool_name=tool, args=args) is None, (tool, args)
