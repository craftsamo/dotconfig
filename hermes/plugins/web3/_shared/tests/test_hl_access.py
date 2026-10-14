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


hl_access = _load("web3_hl_access_test", ROOT / "hl_access.py")
access = hl_access.access


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
    monkeypatch.setattr(access, "VENV_PYTHON", python)
    monkeypatch.setattr(access, "_home", lambda: tmp_path / "assistant")
    monkeypatch.setattr(access, "_inbound_peer", lambda: False)


def fake_engine(monkeypatch, reply=None):
    seen = []

    def run(cmd, **kwargs):
        seen.append({"script": Path(cmd[1]).name, "payload": json.loads(kwargs["input"]), "env": kwargs["env"]})
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(reply or {"ok": True, "data": {}}), stderr="")

    monkeypatch.setattr(access.subprocess, "run", run)
    return seen


def test_the_hyperliquid_tool_shares_the_web3_modules():
    assert access is __import__("sys").modules["hermes_web3_access"]
    assert hl_access.HL.name == "hl.py" and hl_access.HL.parent == Path(access.__file__).parent


def test_the_four_reading_profiles_get_the_tool_and_others_nothing():
    for profile in ("creator", "writer", "engineer", "default"):
        ctx = Ctx(profile)
        hl_access.register(ctx)
        assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        hl_access.register(ctx)
        registered = ctx.tools["hyperliquid"]
        params = registered["schema"]["parameters"]
        assert registered["toolset"] == "hyperliquid_access" and params["additionalProperties"] is False
        assert params["required"] == ["action", "network"]
        assert params["properties"]["network"]["enum"] == ["mainnet", "testnet"]
        assert params["properties"]["action"]["enum"] == list(hl_access.READS)
        assert "nothing is signed or sent" in registered["description"]
        assert 'skill_view(name="hyperliquid-access:hyperliquid")' in registered["description"]
        assert [hook for hook, _ in ctx.hooks] == ["pre_tool_call"]


@pytest.mark.parametrize("args, needle", [
    ({"action": "order", "network": "mainnet"}, "not available here"),
    ({"action": "markets"}, "network must be mainnet or testnet"),
    ({"action": "markets", "network": "devnet"}, "network must be mainnet or testnet"),
])
def test_calls_outside_the_tool_are_refused_before_the_engine(monkeypatch, args, needle):
    seen = fake_engine(monkeypatch)
    reply = json.loads(hl_access.run("assistant", args))
    assert not reply["ok"] and needle in reply["error"] and seen == []
    assert hl_access.check("assistant", tool_name="hyperliquid", args=args)["action"] == "block"


def test_a_read_runs_the_engine_with_only_its_own_fields_and_a_minimal_environment(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"markets": []}})
    args = {"action": "markets", "network": "testnet", "sort": "oi", "chain": "base", "quote": "q00000000"}
    assert hl_access.check("researcher", tool_name="hyperliquid", args=args) is None
    assert json.loads(hl_access.run("researcher", args)) == {"ok": True, "data": {"markets": []}}
    assert seen[0]["script"] == "hl.py"
    assert seen[0]["payload"] == {"action": "markets", "network": "testnet", "sort": "oi"}
    assert set(seen[0]["env"]) == {"HOME", "PATH", "LANG", "PYTHONDONTWRITEBYTECODE"}


def test_a_result_too_long_is_refused(monkeypatch):
    fake_engine(monkeypatch, {"ok": True, "data": {"rows": "x" * (access.LIMIT + 10)}})
    reply = json.loads(hl_access.run("assistant", {"action": "candles", "network": "mainnet", "coin": "BTC"}))
    assert not reply["ok"] and "narrow it" in reply["error"]


def test_a_timed_out_read_says_nothing_moved(monkeypatch):
    fake_engine(monkeypatch, {"ok": False, "error": "the web3 engine did not finish within 150s; narrow a read. A "
                                                    "transfer may already have been sent"})
    reply = json.loads(hl_access.run("researcher", {"action": "review", "network": "mainnet", "address": "0x" + "1" * 40}))
    assert not reply["ok"] and "Hyperliquid read did not finish" in reply["error"]
    assert "transfer" not in reply["error"] and "wallet" not in reply["error"]


def test_inbound_a2a_reads_only_on_the_a2a_specialists(monkeypatch, tmp_path):
    monkeypatch.setattr(access, "_inbound_peer", lambda: True)
    args = {"action": "markets", "network": "mainnet"}
    assert "inbound A2A" in hl_access.refused("assistant", args)
    monkeypatch.setattr(access, "_home", lambda: tmp_path / "researcher")
    assert hl_access.refused("researcher", args) is None
    assert "inbound A2A" in hl_access.refused("searcher", args)  # a home that is not the searcher's


def test_ways_around_the_tools_are_blocked_on_every_reading_profile():
    blocked = hl_access.check("researcher", tool_name="terminal", args={"command": "ls ~/.config/hermes/local/web3"})
    assert blocked["action"] == "block"
    keychain = {"command": "secret get HERMES_MAIN -p wallets"}
    assert hl_access.check("assistant", tool_name="terminal", args=keychain)["action"] == "block"
    assert hl_access.check("researcher", tool_name="terminal", args={"command": "ls"}) is None
    assert hl_access.check("assistant", tool_name="web_search", args={"query": "secret get"}) is None
