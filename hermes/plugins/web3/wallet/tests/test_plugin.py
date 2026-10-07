import importlib.util
import json
from pathlib import Path
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("web3_wallet_plugin_test", ROOT / "__init__.py")


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
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "home")
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_platform", lambda: "telegram")
    monkeypatch.setattr(plugin, "_no_human", lambda: None)
    plugin._DECISIONS.clear()


def write_quote(tmp_path, quote_id="q0000000a", **fields) -> dict:
    quote = {"id": quote_id, "own": False, "expires": time.time() + 600, "card": "DETAILED CARD",
             "card_short": "SHORT CARD", **fields}
    folder = tmp_path / "home" / "web3-wallet" / "quotes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{quote_id}.json").write_text(json.dumps(quote))
    return quote


def fake_engine(monkeypatch, reply=None):
    seen = []

    def run(cmd, **kwargs):
        seen.append({"cmd": cmd, "payload": json.loads(kwargs["input"]), "env": kwargs["env"]})
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(reply or {"ok": True, "data": {}}), stderr="")

    monkeypatch.setattr(plugin.subprocess, "run", run)
    return seen


def gate(**kwargs):
    return plugin.check(**kwargs)


def transfer(quote_id="q0000000a"):
    return {"action": "transfer", "quote": quote_id}


# --- registration -------------------------------------------------------------------------------

def test_only_the_assistant_gets_the_wallet():
    for profile in ("researcher", "searcher", "marketer", "creator", "default"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    tool = ctx.tools["wallet"]
    assert tool["toolset"] == "web3_wallet" and tool["schema"]["parameters"]["additionalProperties"] is False
    assert tool["schema"]["parameters"]["properties"]["action"]["enum"] == ["accounts", "quote", "transfer", "status"]
    assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]


def test_the_description_says_who_starts_a_transfer():
    assert "only the user's own request" in plugin.DESCRIPTION and "'once'" in plugin.DESCRIPTION


# --- the approval decision ----------------------------------------------------------------------

def test_a_transfer_to_an_own_wallet_runs_without_a_card(tmp_path):
    write_quote(tmp_path, own=True)
    assert gate(tool_name="wallet", args=transfer()) is None
    assert plugin._DECISIONS["q0000000a"][0] == "own"


def test_an_external_transfer_asks_with_the_detailed_card_keyed_to_its_quote(tmp_path):
    write_quote(tmp_path)
    directive = gate(tool_name="wallet", args=transfer())
    assert directive == {"action": "approve", "message": "DETAILED CARD", "rule_key": "web3-wallet:transfer:q0000000a"}
    assert plugin._DECISIONS["q0000000a"][0] == "card"


def test_discord_gets_the_compact_card(tmp_path, monkeypatch):
    write_quote(tmp_path)
    monkeypatch.setattr(plugin, "_platform", lambda: "discord")
    assert gate(tool_name="wallet", args=transfer())["message"] == "SHORT CARD"


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
def test_without_a_human_an_external_transfer_is_blocked_but_an_own_one_runs(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(plugin, "_no_human", lambda: reason)
    write_quote(tmp_path)
    directive = gate(tool_name="wallet", args=transfer())
    assert directive["action"] == "block" and reason in directive["message"]
    assert "q0000000a" not in plugin._DECISIONS
    write_quote(tmp_path, "q0000000b", own=True)
    assert gate(tool_name="wallet", args=transfer("q0000000b")) is None


def test_the_presence_check_fails_closed(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "tools":
            raise ImportError("no hermes here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)
    assert _load("web3_wallet_plugin_fresh", ROOT / "__init__.py")._no_human() == \
        "Hermes' approval context could not be read"


@pytest.mark.parametrize("fields, message", [
    ({"consumed": 1}, "already used"), ({"expires": 1}, "expired"), ({"card": ""}, "no approval card")])
def test_unusable_quotes_are_blocked_before_asking(tmp_path, fields, message):
    write_quote(tmp_path, **fields)
    directive = gate(tool_name="wallet", args=transfer())
    assert directive["action"] == "block" and message in directive["message"]


def test_a_missing_or_malformed_quote_is_blocked(tmp_path):
    for quote_id in ("q0000000f", "../../etc/passwd", None):
        assert gate(tool_name="wallet", args=transfer(quote_id))["action"] == "block"


def test_other_wallet_actions_need_no_approval():
    for action in ("accounts", "quote", "status"):
        assert gate(tool_name="wallet", args={"action": action}) is None


# --- the tool -----------------------------------------------------------------------------------

def test_a_transfer_the_hook_did_not_decide_never_reaches_the_signer(tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    write_quote(tmp_path)
    reply = json.loads(plugin.wallet(transfer()))
    assert reply["ok"] is False and "not decided by the approval hook" in reply["error"] and seen == []


def test_the_hooks_decision_travels_to_the_signer_once(tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"sent": True}})
    write_quote(tmp_path)
    gate(tool_name="wallet", args=transfer())
    assert json.loads(plugin.wallet(transfer()))["ok"] is True
    assert seen[0]["payload"] == {"op": "send", "quote": "q0000000a", "approval": "card",
                                  "state": str(tmp_path / "home" / "web3-wallet")}
    assert seen[0]["cmd"][1].endswith("wallet/signer.py")
    assert set(seen[0]["env"]) == {"HOME", "PATH", "LANG", "PYTHONDONTWRITEBYTECODE"}
    assert json.loads(plugin.wallet(transfer()))["ok"] is False and len(seen) == 1


def test_a_stale_decision_is_not_used(tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    plugin._DECISIONS["q0000000a"] = ("own", time.time() - plugin.DECISION_TTL - 1)
    assert json.loads(plugin.wallet(transfer()))["ok"] is False and seen == []


def test_only_each_actions_fields_reach_the_signer(monkeypatch):
    seen = fake_engine(monkeypatch)
    plugin.wallet({"action": "quote", "account": "hermes/HERMES_MAIN#0", "chain": "sepolia", "to": "0xabc",
                   "amount": "1", "quote": "q0000000a", "_sources": [], "_rpc": "http://evil"})
    payload = seen[0]["payload"]
    assert set(payload) == {"op", "account", "chain", "to", "amount", "state"} and payload["op"] == "quote"


def test_inbound_a2a_never_reaches_the_wallet(monkeypatch):
    seen = fake_engine(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert json.loads(plugin.wallet({"action": "accounts"}))["ok"] is False and seen == []
    assert gate(tool_name="wallet", args={"action": "accounts"})["action"] == "block"


def test_a_missing_engine_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "VENV_PYTHON", tmp_path / "missing")
    reply = json.loads(plugin.wallet({"action": "accounts"}))
    assert reply["ok"] is False and "web3.sh install" in reply["error"]


# --- ways around --------------------------------------------------------------------------------

def test_the_keychain_and_the_signer_are_out_of_the_terminals_reach(tmp_path):
    state = str(tmp_path / "home" / "web3-wallet")
    blocked = [
        ("terminal", {"command": "secret get HERMES_MAIN -p hermes --shared"}),
        ("terminal", {"command": "secret rm HERMES_MAIN -p hermes -f"}),
        ("terminal", {"command": "secret set HERMES_MAIN -p hermes -D MNEMONIC"}),
        ("terminal", {"command": "security find-generic-password -s secret.hermes -w"}),
        ("terminal", {"command": "security delete-generic-password -a X"}),
        ("terminal", {"command": "~/.config/hermes/scripts/web3.sh addresses"}),
        ("terminal", {"command": "cast send 0xabc --private-key $K"}),
        ("execute_code", {"code": "open('" + state + "/quotes/q1.json').read()"}),
        ("write_file", {"path": state + "/quotes/q1.json", "content": "{}"}),
        ("terminal", {"command": "python signer.py"}),
    ]
    for tool, args in blocked:
        directive = gate(tool_name=tool, args=args)
        assert directive and directive["action"] == "block", (tool, args)
    allowed = [("terminal", {"command": "secret ls -p hermes"}), ("terminal", {"command": "git status"}),
               ("read_file", {"path": "/x/hermes/plugins/web3/wallet/signer.py"})]
    for tool, args in allowed:
        assert gate(tool_name=tool, args=args) is None, (tool, args)
