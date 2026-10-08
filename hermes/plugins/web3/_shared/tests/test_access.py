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


access = _load("web3_access_test", ROOT / "access.py")

VERIFIED = {"quote": "q0000000a", "chain": "sepolia", "own": False, "card": "DETAILED CARD",
            "card_short": "SHORT CARD", "mac": "m" * 64}
CHECKED = {"wallet": {"name": "HERMES_TESTNET"}, "digest": "d" * 64, "card": "WALLET CARD",
           "card_short": "SHORT WALLET CARD"}
NEW = {"action": "create_wallet", "name": "HERMES_TESTNET", "purpose": "Testnet checks"}


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
    monkeypatch.setattr(access, "_platform", lambda: "telegram")
    monkeypatch.setattr(access, "_no_human", lambda: None)
    access._DECISIONS.clear()


def fake_engine(monkeypatch, verify=None, reply=None, check=None):
    """reader.py answers ``reply``; signer.py answers verify with ``verify`` and wallet_check with ``check``
    (a dict, or an error string) and anything else with ``reply``."""
    seen = []

    def run(cmd, **kwargs):
        payload = json.loads(kwargs["input"])
        seen.append({"script": Path(cmd[1]).name, "payload": payload, "env": kwargs["env"]})
        if payload.get("op") in ("verify", "wallet_check"):
            answer = (verify if verify is not None else VERIFIED) if payload["op"] == "verify" else \
                (check if check is not None else CHECKED)
            out = {"ok": False, "error": answer} if isinstance(answer, str) else {"ok": True, "data": answer}
        else:
            out = reply or {"ok": True, "data": {}}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(out), stderr="")

    monkeypatch.setattr(access.subprocess, "run", run)
    return seen


def tool(family, profile="assistant"):
    return lambda args: access.run(family, profile, args)


def gate(family="evm", profile="assistant", **kwargs):
    return access.check(family, profile, **kwargs)


def transfer(quote_id="q0000000a"):
    return {"action": "transfer", "quote": quote_id}


# --- registration and actions -------------------------------------------------------------------

@pytest.mark.parametrize("family, name, toolset", [("evm", "evm", "evm_access"),
                                                   ("solana", "solana", "solana_access")])
def test_four_profiles_get_the_familys_tool(family, name, toolset):
    for profile in ("creator", "writer", "engineer", "default"):
        ctx = Ctx(profile)
        access.register(ctx, family)
        assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        access.register(ctx, family)
        registered = ctx.tools[name]
        params = registered["schema"]["parameters"]
        assert registered["toolset"] == toolset and params["additionalProperties"] is False
        assert params["properties"]["chain"]["enum"] == access.FAMILY[family]["chains"]
        assert [hook for hook, _ in ctx.hooks] == ["pre_tool_call"]


def test_only_the_assistant_gets_the_wallet_actions():
    for family in ("evm", "solana"):
        reads = access.READS[family]
        assert access.actions_for(family, "assistant") == reads + access.WALLET
        for profile in ("researcher", "searcher", "marketer"):
            schema = access.schema_for(family, profile)
            assert schema["parameters"]["properties"]["action"]["enum"] == list(reads)
            assert "quote" not in schema["parameters"]["properties"] and "nothing is signed" in schema["description"]
        assert "'once'" in access.schema_for(family, "assistant")["description"]
    assert "logs" in access.READS["evm"] and "logs" not in access.READS["solana"]
    assert "chains" not in access.schema_for("solana", "assistant")["parameters"]["properties"]


def test_every_profile_analyses_contracts_and_programs():
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        evm = access.schema_for("evm", profile)["parameters"]["properties"]
        sol = access.schema_for("solana", profile)["parameters"]["properties"]
        assert {"contract", "call", "storage"} <= set(evm["action"]["enum"])
        assert "program" in sol["action"]["enum"] and "call" not in sol["action"]["enum"]
        assert {"function", "args", "from", "slot", "amount"} <= set(evm)
        assert not {"function", "args", "from", "slot"} & set(sol)
        assert ("amount" in sol) == (profile == "assistant")  # a quote's amount, never a call's
    assert "call" in access.schema_for("evm", "assistant")["parameters"]["properties"]["amount"]["description"]
    assert "call" not in access.schema_for("solana", "assistant")["parameters"]["properties"]["amount"]["description"]


def test_a_call_reaches_the_reader_with_its_fields(monkeypatch):
    seen = fake_engine(monkeypatch)
    args = {"action": "call", "chain": "base", "address": "0xabc", "function": "balanceOf", "args": ["0xdef"],
            "from": "0x123", "amount": "0.1", "block": "latest", "slot": "1"}
    tool("evm", "searcher")(args)
    assert seen[0]["script"] == "reader.py" and seen[0]["payload"] == args


def test_untrusted_text_is_named_in_every_description():
    for family in ("evm", "solana"):
        for profile in ("assistant", "searcher"):
            assert "never followed" in access.schema_for(family, profile)["description"]


def test_wrong_chains_and_unavailable_actions_are_refused(monkeypatch):
    seen = fake_engine(monkeypatch)
    cases = [("evm", {"action": "block", "chain": "solana"}, "chain must be one of"),
             ("solana", {"action": "block", "chain": "base"}, "chain must be one of"),
             ("solana", {"action": "logs", "chain": "solana"}, "not available here"),
             ("evm", {"action": "block"}, "chain must be one of"),
             ("evm", {"action": "accounts", "chain": "solana-devnet"}, "chain must be one of")]
    for family, args, message in cases:
        reply = json.loads(tool(family)(args))
        assert reply["ok"] is False and message in reply["error"], (family, args)
        assert gate(family, tool_name=access.FAMILY[family]["tool"], args=args)["action"] == "block"
    reply = json.loads(tool("evm", "searcher")({"action": "quote", "chain": "sepolia"}))
    assert reply["ok"] is False and "not available here" in reply["error"]
    assert seen == []


# --- reads --------------------------------------------------------------------------------------

def test_reads_run_the_reader_with_only_schema_fields(monkeypatch):
    seen = fake_engine(monkeypatch, reply={"ok": True, "data": {"number": 1}})
    reply = json.loads(tool("evm", "searcher")({"action": "block", "chain": "sepolia", "block": "latest",
                                                "_rpc": "http://evil", "_offline": True, "quote": "q0000000a"}))
    assert reply == {"ok": True, "data": {"number": 1}}
    assert seen[0]["script"] == "reader.py"
    assert seen[0]["payload"] == {"action": "block", "chain": "sepolia", "block": "latest"}
    assert set(seen[0]["env"]) == {"HOME", "PATH", "LANG", "PYTHONDONTWRITEBYTECODE"}


def test_a_missing_engine_and_oversized_results_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(access, "VENV_PYTHON", tmp_path / "missing")
    reply = json.loads(tool("evm")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "web3.sh install" in reply["error"]
    monkeypatch.setattr(access, "VENV_PYTHON", tmp_path / "python")
    fake_engine(monkeypatch, reply={"ok": True, "data": {"x": "y" * (access.LIMIT + 10)}})
    reply = json.loads(tool("evm")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "narrow it" in reply["error"]


def test_inbound_a2a_reads_only_on_the_specialists_and_never_sends(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch)
    monkeypatch.setattr(access, "_inbound_peer", lambda: True)
    reply = json.loads(tool("evm")({"action": "gas", "chain": "base"}))
    assert reply["ok"] is False and "inbound A2A" in reply["error"]
    assert gate(tool_name="evm", args=transfer())["action"] == "block"
    assert json.loads(tool("evm")({"action": "accounts"}))["ok"] is False
    for profile in ("researcher", "searcher", "marketer"):
        monkeypatch.setattr(access, "_home", lambda p=profile: tmp_path / p)
        assert json.loads(tool("solana", profile)({"action": "gas", "chain": "solana"}))["ok"] is True
    assert [s["script"] for s in seen] == ["reader.py"] * 3


# --- wallet actions -----------------------------------------------------------------------------

def test_wallet_actions_run_the_signer_with_their_own_fields(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch)
    tool("evm")({"action": "quote", "account": "hermes/HERMES_MAIN#0", "chain": "sepolia", "to": "0xabc",
                 "amount": "1", "quote": "q0000000a", "mac": "x", "block": "latest"})
    tool("solana")({"action": "accounts", "count": 2})
    quote, accounts = seen[0], seen[1]
    assert quote["script"] == "signer.py"
    assert quote["payload"] == {"op": "quote", "account": "hermes/HERMES_MAIN#0", "chain": "sepolia", "to": "0xabc",
                                "amount": "1", "state": str(tmp_path / "assistant" / "web3-wallet")}
    assert accounts["payload"] == {"op": "accounts", "count": 2, "family": "solana",
                                   "state": str(tmp_path / "assistant" / "web3-wallet")}


def test_the_hook_asks_the_signer_to_verify_the_quote(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch)
    gate(tool_name="evm", args=transfer())
    assert seen[0]["script"] == "signer.py"
    assert seen[0]["payload"] == {"op": "verify", "quote": "q0000000a",
                                  "state": str(tmp_path / "assistant" / "web3-wallet")}


def test_a_transfer_to_an_own_wallet_runs_without_a_card(monkeypatch):
    fake_engine(monkeypatch, verify={**VERIFIED, "own": True})
    assert gate(tool_name="evm", args=transfer()) is None
    assert access._DECISIONS["q0000000a"][:2] == ("own", "m" * 64)


def test_an_external_transfer_asks_with_the_verified_card_under_a_fresh_key(monkeypatch):
    fake_engine(monkeypatch)
    first = gate(tool_name="evm", args=transfer())
    second = gate(tool_name="evm", args=transfer())
    assert first["action"] == "approve" and first["message"] == "DETAILED CARD"
    assert first["rule_key"].startswith("web3-wallet:transfer:q0000000a:")
    assert first["rule_key"] != second["rule_key"]  # a session/always grant never answers another card
    assert access._DECISIONS["q0000000a"][:2] == ("card", "m" * 64)


def test_discord_gets_the_compact_card(monkeypatch):
    fake_engine(monkeypatch)
    monkeypatch.setattr(access, "_platform", lambda: "discord")
    assert gate(tool_name="evm", args=transfer())["message"] == "SHORT CARD"


def test_a_quote_is_sent_only_by_its_own_familys_tool(monkeypatch):
    fake_engine(monkeypatch)
    directive = gate("solana", tool_name="solana", args=transfer())
    assert directive["action"] == "block" and "send it with the tool of its chain" in directive["message"]
    assert "q0000000a" not in access._DECISIONS


def test_a_quote_the_signer_refuses_is_blocked_before_any_card(monkeypatch):
    fake_engine(monkeypatch, verify="this quote was changed after it was made; it is refused")
    directive = gate(tool_name="evm", args=transfer())
    assert directive["action"] == "block" and "changed after it was made" in directive["message"]
    assert "q0000000a" not in access._DECISIONS


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
def test_without_a_human_an_external_transfer_is_blocked_but_an_own_one_runs(monkeypatch, reason):
    monkeypatch.setattr(access, "_no_human", lambda: reason)
    fake_engine(monkeypatch)
    directive = gate(tool_name="evm", args=transfer())
    assert directive["action"] == "block" and reason in directive["message"]
    assert "q0000000a" not in access._DECISIONS
    fake_engine(monkeypatch, verify={**VERIFIED, "own": True})
    assert gate(tool_name="evm", args=transfer()) is None


def test_the_presence_check_fails_closed(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "tools":
            raise ImportError("no hermes here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)
    assert _load("web3_access_fresh", ROOT / "access.py")._no_human() == \
        "Hermes' approval context could not be read"


def test_a_malformed_quote_id_never_reaches_the_signer(monkeypatch):
    seen = fake_engine(monkeypatch)
    for quote_id in ("../../etc/passwd", None, "Q0000000A"):
        assert gate(tool_name="evm", args=transfer(quote_id))["action"] == "block"
    assert seen == []


def test_a_verified_quote_without_a_card_or_mac_is_blocked(monkeypatch):
    fake_engine(monkeypatch, verify={**VERIFIED, "card": ""})
    assert gate(tool_name="evm", args=transfer())["action"] == "block"
    fake_engine(monkeypatch, verify={**VERIFIED, "mac": None})
    assert gate(tool_name="evm", args=transfer())["action"] == "block"


def test_a_transfer_the_hook_did_not_decide_never_reaches_the_signer(monkeypatch):
    seen = fake_engine(monkeypatch)
    reply = json.loads(tool("evm")(transfer()))
    assert reply["ok"] is False and "not decided by the approval hook" in reply["error"] and seen == []


def test_the_hooks_decision_and_the_approved_mac_travel_to_the_signer_once(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch, reply={"ok": True, "data": {"sent": True}})
    gate(tool_name="evm", args=transfer())
    assert json.loads(tool("evm")(transfer()))["ok"] is True
    assert seen[1]["payload"] == {"op": "send", "quote": "q0000000a", "approval": "card", "mac": "m" * 64,
                                  "state": str(tmp_path / "assistant" / "web3-wallet")}
    assert json.loads(tool("evm")(transfer()))["ok"] is False and len(seen) == 2


def test_a_stale_decision_is_not_used(monkeypatch):
    seen = fake_engine(monkeypatch)
    access._DECISIONS["q0000000a"] = ("own", "m" * 64, time.time() - access.DECISION_TTL - 1)
    assert json.loads(tool("evm")(transfer()))["ok"] is False and seen == []


def test_other_actions_need_no_approval(monkeypatch):
    seen = fake_engine(monkeypatch)
    for args in ({"action": "accounts"}, {"action": "quote", "chain": "sepolia"},
                 {"action": "status", "chain": "sepolia"}, {"action": "gas", "chain": "sepolia"}):
        assert gate(tool_name="evm", args=args) is None
    assert seen == []


# --- new wallets --------------------------------------------------------------------------------

def test_a_new_wallet_is_always_asked_on_the_card_of_its_checked_metadata(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch)
    first = gate(tool_name="evm", args={**NEW, "words": 12, "scope": "testnet", "mac": "x"})
    second = gate("solana", tool_name="solana", args=NEW)
    assert first["action"] == "approve" and first["message"] == "WALLET CARD"
    assert first["rule_key"].startswith("web3-wallet:create:dddddddddddd:") and first["rule_key"] != second["rule_key"]
    assert seen[0]["payload"] == {"op": "wallet_check", "name": "HERMES_TESTNET", "purpose": "Testnet checks",
                                  "words": 12, "scope": "testnet", "state": str(tmp_path / "assistant" / "web3-wallet")}
    monkeypatch.setattr(access, "_platform", lambda: "discord")
    assert gate(tool_name="evm", args=NEW)["message"] == "SHORT WALLET CARD"


def test_the_approved_digest_travels_to_the_creation_once(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch, reply={"ok": True, "data": {"created": True}})
    gate(tool_name="evm", args=NEW)
    assert json.loads(tool("evm")(NEW))["ok"] is True
    assert seen[1]["payload"] == {"op": "wallet_create", "name": "HERMES_TESTNET", "purpose": "Testnet checks",
                                  "digest": "d" * 64, "state": str(tmp_path / "assistant" / "web3-wallet")}
    again = json.loads(tool("evm")(NEW))
    assert again["ok"] is False and "nothing was created" in again["error"] and len(seen) == 2


def test_a_wallet_the_hook_did_not_approve_is_never_made(monkeypatch):
    seen = fake_engine(monkeypatch)
    gate(tool_name="evm", args=NEW)
    reply = json.loads(tool("evm")({**NEW, "name": "HERMES_OTHER"}))
    assert reply["ok"] is False and "not approved" in reply["error"]
    assert [s["payload"]["op"] for s in seen] == ["wallet_check"]


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "this is a single-query run",
                                    "approvals are off (approvals.mode: off)"])
def test_without_a_human_no_wallet_is_made(monkeypatch, reason):
    monkeypatch.setattr(access, "_no_human", lambda: reason)
    seen = fake_engine(monkeypatch)
    directive = gate(tool_name="evm", args=NEW)
    assert directive["action"] == "block" and reason in directive["message"] and seen == []
    assert access._DECISIONS == {}


def test_a_wallet_the_signer_refuses_is_blocked_before_any_card(monkeypatch):
    fake_engine(monkeypatch, check="a Hermes wallet's name has HERMES as one of its words")
    directive = gate(tool_name="evm", args={**NEW, "name": "TESTNET"})
    assert directive["action"] == "block" and "HERMES as one of its words" in directive["message"]
    assert access._DECISIONS == {}


def test_only_the_assistant_and_never_an_inbound_peer_creates_wallets(monkeypatch):
    seen = fake_engine(monkeypatch)
    for profile in ("researcher", "searcher", "marketer"):
        assert "name" not in access.schema_for("evm", profile)["parameters"]["properties"]
        assert json.loads(tool("evm", profile)(NEW))["ok"] is False
    props = access.schema_for("solana", "assistant")["parameters"]["properties"]
    assert {"name", "purpose", "project", "scope", "words"} <= set(props)
    monkeypatch.setattr(access, "_inbound_peer", lambda: True)
    assert gate(tool_name="evm", args=NEW)["action"] == "block" and seen == []


# --- ways around --------------------------------------------------------------------------------

def test_a_profile_that_sends_keeps_the_keychain_and_the_signer_out_of_reach(tmp_path):
    state = str(tmp_path / "assistant" / "web3-wallet")
    blocked = [
        ("terminal", {"command": "secret get HERMES_MAIN -p hermes --shared"}),
        ("terminal", {"command": "secret env -p work --scope deploy"}),
        ("terminal", {"command": "secret rm HERMES_MAIN -p hermes -f"}),
        ("terminal", {"command": "secret set HERMES_MAIN -p hermes -D MNEMONIC"}),
        ("terminal", {"command": "secret update HERMES_MAIN -p hermes --env"}),
        ("terminal", {"command": "security find-generic-password -s secret.hermes -w"}),
        ("terminal", {"command": "security delete-generic-password -a X"}),
        ("terminal", {"command": "~/.config/hermes/scripts/web3.sh addresses"}),
        ("terminal", {"command": "cast send 0xabc --private-key $K"}),
        ("execute_code", {"code": "open('" + state + "/quotes/q1.json').read()"}),
        ("write_file", {"path": state + "/quotes/q1.json", "content": "{}"}),
        ("terminal", {"command": "python signer.py"}),
        ("terminal", {"command": "python seeds.py"}),
        ("terminal", {"command": "secret get ALCHEMY_API_KEY -p hermes --scope web3-rpc"}),
    ]
    for family in ("evm", "solana"):
        for name, args in blocked:
            directive = gate(family, tool_name=name, args=args)
            assert directive and directive["action"] == "block", (family, name, args)
    allowed = [("terminal", {"command": "secret ls -p hermes"}), ("terminal", {"command": "git status"}),
               ("read_file", {"path": "/x/hermes/plugins/web3/_shared/signer.py"})]
    for name, args in allowed:
        assert gate(tool_name=name, args=args) is None, (name, args)


def test_a_reading_profile_blocks_only_the_engine_and_the_rpc_keys():
    blocked = [("terminal", {"command": "secret get ALCHEMY_API_KEY -p hermes --scope web3-rpc"}),
               ("terminal", {"command": "secret get ETHERSCAN_API_KEY -p hermes"}),
               ("terminal", {"command": "~/.config/hermes/local/web3/venv/bin/python reader.py"}),
               ("execute_code", {"code": "import os; os.system('secret show HELIUS_API_KEY')"}),
               ("read_file", {"path": "~/.config/hermes/local/web3/venv/pyvenv.cfg"})]
    for name, args in blocked:
        assert gate("evm", "marketer", tool_name=name, args=args)["action"] == "block", (name, args)
    assert gate("evm", "marketer", tool_name="terminal", args={"command": "ls ~/Workspaces"}) is None
    assert gate("evm", "marketer", tool_name="web_search", args={"query": "web3-rpc"}) is None
