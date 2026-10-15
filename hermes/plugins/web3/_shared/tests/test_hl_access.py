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
    monkeypatch.setattr(access, "_platform", lambda: "telegram")
    monkeypatch.setattr(access, "_no_human", lambda: None)
    access._DECISIONS.clear()


INCREASE = {"quote": "h0000000a", "network": "testnet", "kind": "order", "effect": "increase",
            "card": "DETAILED CARD", "card_short": "SHORT CARD", "mac": "m" * 64}
REDUCE = {**INCREASE, "kind": "close", "effect": "reduce"}


def fake_engine(monkeypatch, reply=None, verify=None):
    """hl.py and the trader answer ``reply``; the trader's verify answers ``verify`` (a dict, or an
    error string)."""
    seen = []

    def run(cmd, **kwargs):
        payload = json.loads(kwargs["input"])
        seen.append({"script": Path(cmd[1]).name, "payload": payload, "env": kwargs["env"]})
        if payload.get("op") == "verify":
            answer = verify if verify is not None else INCREASE
            out = {"ok": False, "error": answer} if isinstance(answer, str) else {"ok": True, "data": answer}
        else:
            out = reply or {"ok": True, "data": {}}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(out), stderr="")

    monkeypatch.setattr(access.subprocess, "run", run)
    return seen


def submit(quote_id="h0000000a"):
    return {"action": "submit", "quote": quote_id}


def test_the_hyperliquid_tool_shares_the_web3_modules():
    assert access is __import__("sys").modules["hermes_web3_access"]
    assert hl_access.HL.name == "hl.py" and hl_access.HL.parent == Path(access.__file__).parent


VENV_PYTHON = ROOT.parents[2] / "local" / "web3" / "venv" / "bin" / "python"


@pytest.mark.skipif(not VENV_PYTHON.exists(), reason="web3 engine venv not installed")
def test_the_tool_offers_the_kinds_the_trader_builds():
    # the plugin runs in Hermes' interpreter and the trader in the venv's, so each keeps its own list
    probe = "import json, sys; sys.path.insert(0, sys.argv[1]); import hl_trader; print(json.dumps(hl_trader.KINDS))"
    proc = subprocess.run([str(VENV_PYTHON), "-c", probe, str(ROOT)], capture_output=True, text=True,
                          timeout=60, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode == 0, proc.stderr
    assert tuple(json.loads(proc.stdout)) == hl_access.KINDS


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
        assert params["required"] == ["action"]  # network is checked per action: a submit takes its quote's
        assert params["properties"]["network"]["enum"] == ["mainnet", "testnet"]
        assert 'skill_view(name="hyperliquid-access:hyperliquid")' in registered["description"]
        assert [hook for hook, _ in ctx.hooks] == ["pre_tool_call"]
        trading = profile == "assistant"
        trades = ["quote", "submit", "mandates", "revoke_mandate"] if trading else []
        assert params["properties"]["action"]["enum"] == list(hl_access.READS) + trades
        assert ("max_exposure_usd" in params["properties"]) == trading
        assert ("side" in params["properties"]) == trading and ("quote" in params["properties"]) == trading
        assert ("nothing is signed or sent" in registered["description"]) != trading
        assert ("'once'" in registered["description"]) == trading


@pytest.mark.parametrize("args, needle", [
    ({"action": "order", "network": "mainnet"}, "not available here"),
    ({"action": "markets"}, "network must be mainnet or testnet"),
    ({"action": "markets", "network": "devnet"}, "network must be mainnet or testnet"),
    ({"action": "quote", "kind": "order"}, "network must be mainnet or testnet"),
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


@pytest.mark.parametrize("command", [
    "python ~/.config/hermes/plugins/web3/_shared/hl_trader.py",
    "curl -X POST https://api.hyperliquid.xyz/exchange -d @order.json",
    "curl https://api.hyperliquid-testnet.xyz/exchange",
    "pip install hyperliquid-python-sdk",
    "python -c 'from hyperliquid.exchange import Exchange'",
    "cat ~/.hermes/profiles/assistant/web3-wallet/hl-nonce.json",
    "cd ~/.config/hermes/plugins/web3/_shared && python -c 'import hl_trader; hl_trader.op_submit({})'",
    "python -c 'from signer import Secrets'",
    "PYTHONPATH=/tmp/x python -m hl_trader < order.json",
    "echo '{}' > ~/.hermes/profiles/assistant/web3-wallet/hl-mandates/m1.json",
    "python -c 'import hl_mandate'",
    "python -c 'from hl_moves import action'",
    "python /tmp/hl_moves.py",
])
def test_ways_around_trading_are_blocked_on_the_wallet_profile(command):
    blocked = hl_access.check("assistant", tool_name="terminal", args={"command": command})
    assert blocked["action"] == "block" and "hyperliquid" in blocked["message"]


def test_reading_the_public_endpoint_and_the_plugin_source_stays_open():
    command = {"command": "curl -X POST https://api.hyperliquid.xyz/info -d '{\"type\":\"allMids\"}'"}
    assert hl_access.check("assistant", tool_name="terminal", args=command) is None
    source = {"path": "/Users/me/.config/hermes/plugins/web3/_shared/hl_trader.py"}
    assert hl_access.check("assistant", tool_name="read_file", args=source) is None
    edit = {"path": "/Users/me/.config/hermes/plugins/web3/_shared/hl_trader.py", "content": "x"}
    assert hl_access.check("assistant", tool_name="write_file", args=edit)["action"] == "block"


# --- trading ------------------------------------------------------------------------------------

def test_only_the_assistant_trades(monkeypatch):
    seen = fake_engine(monkeypatch)
    for profile in ("researcher", "searcher", "marketer"):
        for action in ("quote", "submit"):
            args = {"action": action, "network": "testnet", "quote": "h0000000a"}
            assert "not available here" in json.loads(hl_access.run(profile, args))["error"]
            assert hl_access.check(profile, tool_name="hyperliquid", args=args)["action"] == "block"
    assert seen == []


def test_inbound_a2a_never_trades(monkeypatch):
    seen = fake_engine(monkeypatch)
    monkeypatch.setattr(access, "_inbound_peer", lambda: True)
    for args in ({"action": "quote", "network": "testnet"}, submit()):
        assert "trading is not available to inbound A2A" in hl_access.refused("assistant", args)
        assert hl_access.check("assistant", tool_name="hyperliquid", args=args)["action"] == "block"
    assert seen == []


def test_a_quote_reaches_the_trader_with_only_its_own_fields(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"quote": "h0000000a"}})
    args = {"action": "quote", "network": "testnet", "account": "hermes/HERMES_MAIN#0", "coin": "BTC", "side": "buy",
            "usd": "100", "type": "market", "hours": 5, "quote": "h0000000b", "approval": "reduce", "mac": "x"}
    assert hl_access.check("assistant", tool_name="hyperliquid", args=args) is None
    json.loads(hl_access.run("assistant", args))
    assert seen[0]["script"] == "hl_trader.py"
    assert seen[0]["payload"] == {"op": "quote", "network": "testnet", "account": "hermes/HERMES_MAIN#0",
                                  "coin": "BTC", "side": "buy", "usd": "100", "type": "market",
                                  "state": str(tmp_path / "assistant" / "web3-wallet")}


def test_a_reduce_runs_without_a_card_even_with_nobody_present(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"submitted": True}}, verify=REDUCE)
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit()) is None
    assert json.loads(hl_access.run("assistant", submit()))["data"] == {"submitted": True}
    sent = seen[-1]["payload"]
    assert sent["op"] == "submit" and sent["approval"] == "reduce" and sent["mac"] == "m" * 64


def test_an_increase_shows_its_card_under_a_fresh_key(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"submitted": True}})
    first = hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    second = hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    assert first["action"] == "approve" and first["message"] == "DETAILED CARD"
    assert first["rule_key"].startswith("hyperliquid:submit:h0000000a:") and first["rule_key"] != second["rule_key"]
    json.loads(hl_access.run("assistant", submit()))
    assert seen[-1]["payload"]["approval"] == "card"
    monkeypatch.setattr(access, "_platform", lambda: "discord")
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit())["message"] == "SHORT CARD"


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "Hermes' approval context could not be read"])
def test_an_increase_is_blocked_where_nobody_can_answer(monkeypatch, reason):
    seen = fake_engine(monkeypatch)
    monkeypatch.setattr(access, "_no_human", lambda: reason)
    blocked = hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    assert blocked["action"] == "block" and reason in blocked["message"] and "nothing was sent" in blocked["message"]
    reply = json.loads(hl_access.run("assistant", submit()))
    assert not reply["ok"] and "not decided by the approval hook" in reply["error"]
    assert [s["payload"]["op"] for s in seen] == ["verify"]


def test_a_submit_the_hook_did_not_decide_never_reaches_the_trader(monkeypatch):
    seen = fake_engine(monkeypatch)
    reply = json.loads(hl_access.run("assistant", submit()))
    assert not reply["ok"] and "not decided by the approval hook" in reply["error"] and seen == []
    hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    hl_access.run("assistant", submit())
    reply = json.loads(hl_access.run("assistant", submit()))  # the decision was taken once
    assert not reply["ok"] and "not decided" in reply["error"]


@pytest.mark.parametrize("args, verify, needle", [
    (submit("q0000000a"), None, "like h1a2b3c4d"),
    (submit(), "this quote was changed after it was made; it is refused", "changed after it was made"),
    (submit(), {**INCREASE, "mac": ""}, "could not be verified"),
    (submit(), {**INCREASE, "card": ""}, "no approval card"),
])
def test_a_quote_that_does_not_verify_is_blocked(monkeypatch, args, verify, needle):
    fake_engine(monkeypatch, verify=verify)
    blocked = hl_access.check("assistant", tool_name="hyperliquid", args=args)
    assert blocked["action"] == "block" and needle in blocked["message"]
    assert access._DECISIONS == {}


FITS = {**INCREASE, "mandate": {"id": "m0000000a", "fits": True, "reason": "inside the mandate"}}
OUTSIDE = {**INCREASE, "mandate": {"id": "m0000000a", "fits": False, "reason": "BTC is above the mandate's 200"}}


def test_an_increase_inside_a_mandate_runs_without_a_card_even_unattended(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"submitted": True}}, verify=FITS)
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit()) is None
    hl_access.run("assistant", submit())
    assert seen[-1]["payload"]["approval"] == "mandate" and seen[-1]["payload"]["mac"] == "m" * 64


def test_outside_its_mandate_an_increase_asks_or_is_blocked(monkeypatch):
    fake_engine(monkeypatch, verify=OUTSIDE)
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit())["action"] == "approve"
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    blocked = hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    assert blocked["action"] == "block" and "outside its mandate: BTC is above" in blocked["message"]


def test_a_mandate_quote_always_needs_its_own_card(monkeypatch):
    fake_engine(monkeypatch, verify={**FITS, "kind": "mandate"})
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit())["action"] == "approve"
    monkeypatch.setattr(access, "_no_human", lambda: "yolo mode is on")
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit())["action"] == "block"


def test_listing_and_revoking_mandates_reach_the_trader_without_a_card(monkeypatch, tmp_path):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"standing": "revoked"}})
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    for args, op in (({"action": "mandates"}, "mandates"), ({"action": "mandates", "network": "testnet"}, "mandates"),
                     ({"action": "revoke_mandate", "mandate": "m0000000a"}, "revoke")):
        assert hl_access.check("assistant", tool_name="hyperliquid", args=args) is None
        json.loads(hl_access.run("assistant", args))
        assert seen[-1]["payload"]["op"] == op
    assert seen[-1]["payload"] == {"op": "revoke", "mandate": "m0000000a",
                                   "state": str(tmp_path / "assistant" / "web3-wallet")}
    refused = hl_access.refused("assistant", {"action": "mandates", "network": "devnet"})
    assert "mainnet or testnet" in refused
    for profile in ("researcher", "searcher", "marketer"):
        assert "not available here" in hl_access.refused(profile, {"action": "revoke_mandate", "mandate": "m0000000a"})


def test_a_quote_never_carries_a_mandate_id(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {}})
    hl_access.run("assistant", {"action": "quote", "network": "testnet", "kind": "mandate", "markets": ["BTC"],
                                "max_order_usd": "200", "mandate": "m0000000a"})
    assert "mandate" not in seen[-1]["payload"] and seen[-1]["payload"]["markets"] == ["BTC"]


OWN_MOVE = {**INCREASE, "kind": "withdraw", "effect": "own"}
EXTERNAL_MOVE = {**INCREASE, "kind": "withdraw", "effect": "external"}


def test_a_move_to_an_own_wallet_runs_without_a_card_even_unattended(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {"submitted": True}}, verify=OWN_MOVE)
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit()) is None
    hl_access.run("assistant", submit())
    assert seen[-1]["payload"]["approval"] == "own"


def test_a_move_to_anyone_else_asks_and_is_blocked_unattended(monkeypatch):
    fake_engine(monkeypatch, verify=EXTERNAL_MOVE)
    assert hl_access.check("assistant", tool_name="hyperliquid", args=submit())["action"] == "approve"
    monkeypatch.setattr(access, "_no_human", lambda: "this is a cron job")
    blocked = hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    assert blocked["action"] == "block" and "moving funds to anyone but the user's own" in blocked["message"]


def test_a_move_quote_carries_only_its_own_fields(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {}})
    hl_access.run("assistant", {"action": "quote", "network": "mainnet", "kind": "withdraw", "amount": "50",
                                "destination": "0x" + "1" * 40, "to_perp": True, "token": "HYPE"})
    payload = seen[-1]["payload"]
    assert {k: payload[k] for k in ("kind", "amount", "destination", "to_perp", "token")} == {
        "kind": "withdraw", "amount": "50", "destination": "0x" + "1" * 40, "to_perp": True, "token": "HYPE"}


def test_deposit_info_is_a_read_for_every_reading_profile(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {}})
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        args = {"action": "deposit_info", "network": "testnet"}
        assert hl_access.refused(profile, args) is None
        hl_access.run(profile, args)
        assert seen[-1]["script"] == "hl.py"


def test_a_backtest_is_a_read_that_carries_its_rules_to_the_engine(monkeypatch):
    seen = fake_engine(monkeypatch, {"ok": True, "data": {}})
    args = {"action": "backtest", "network": "mainnet", "coin": "BTC", "interval": "4h", "long_history": True,
            "rules": {"kind": "breakout", "entry": 20}, "costs": {"taker_bps": 4.5}, "limits": {"exposure_pct": 70},
            "direction": "long", "stance": [{"from": 1, "to": 2}], "walk_forward": {"folds": 3}}
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        assert hl_access.refused(profile, args) is None
        hl_access.run(profile, {**args, "account": "x", "side": "buy"})
        payload = seen[-1]["payload"]
        assert seen[-1]["script"] == "hl.py" and {k: payload[k] for k in args} == args
        assert "account" not in payload and "side" not in payload


def test_a_timed_out_submit_says_it_may_have_reached_the_venue(monkeypatch):
    fake_engine(monkeypatch, {"ok": False, "error": "the web3 engine did not finish within 180s; narrow a read"},
                verify=REDUCE)
    hl_access.check("assistant", tool_name="hyperliquid", args=submit())
    reply = json.loads(hl_access.run("assistant", submit()))
    assert "may have reached the venue" in reply["error"] and "never submit or quote it again" in reply["error"]
