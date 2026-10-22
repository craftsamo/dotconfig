"""The backtest read and the strategies' cron gate end to end in the web3 venv, against a fake /info
server and a fake Binance klines endpoint (no network)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import parse_qs, urlparse

import pytest

HERMES = Path(__file__).resolve().parents[4]
SHARED = HERMES / "plugins" / "web3" / "_shared"
RUNTIME_ROOT = Path(os.environ.get("HERMES_LOCAL") or Path.home() / ".hermes" / "local")
PYTHON = RUNTIME_ROOT / "web3" / "venv" / "bin" / "python"
SCRIPT = HERMES / "profiles" / "assistant" / "scripts" / "hl-strategy-gate.sh"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

HOUR = 3_600_000
H4 = 4 * HOUR
STEPS = {"4h": H4, "1d": 24 * HOUR}
NOW = 1_790_000_000_000 - 1_790_000_000_000 % H4 + HOUR  # an hour into a forming 4h bar
USER = "0x" + "ab" * 20


def generated(t: int) -> dict:
    """A rising market with a pullback every 200 bars, for the backtest."""
    k = t // H4
    price = 100 * (1.002 ** (k % 1000)) * (0.9 if (k // 200) % 2 else 1.0)
    return {"t": t, "o": price, "h": price * 1.004, "l": price * 0.996, "c": price * 1.001}


def series(closes: list[float], end: int) -> list[dict]:
    """Completed 4h bars ending at the bar before ``end``'s bar, with the given closes."""
    last = end - end % H4 - H4
    start = last - (len(closes) - 1) * H4
    rows, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        rows.append({"t": start + i * H4, "o": o, "h": max(o, c) + 0.5, "l": min(o, c) - 0.5, "c": c})
        prev = c
    return rows


STATE: dict = {}


def reset():
    STATE.clear()
    STATE.update({
        "bars": {"BTC": series([100.0] * 40 + [110.0], NOW), "ETH": series([50.0] * 41, NOW)},
        "positions": [], "orders": [], "leverage": 20, "equity": "1000", "fills": [], "funding": []})


def candle(t: int, step: int = H4) -> dict:
    b = generated(t)
    return {"t": t, "T": t + step - 1, "o": str(b["o"]), "h": str(b["h"]), "l": str(b["l"]), "c": str(b["c"]),
            "v": "1", "n": 1}


def handle(body: dict):
    kind = body.get("type")
    if kind == "candleSnapshot":
        req = body["req"]
        start, end = req["startTime"], req["endTime"]
        if req["coin"] == "UP":
            step = STEPS[req["interval"]]  # a young venue: 5000 4h bars of history, fewer daily ones
            since = NOW - NOW % step - (5000 * H4) // step * step
            first = max(start - start % step, since)
            return [candle(t, step) for t in range(first, end + 1, step) if t >= start][:5000]
        rows = STATE["bars"].get(req["coin"], [])
        return [{k: (str(v) if k != "t" else v) for k, v in r.items()} for r in rows if start <= r["t"] <= end]
    if kind == "fundingHistory":
        start, end = body["startTime"], body.get("endTime", NOW)
        first = start + (-start) % HOUR
        return [{"coin": body["coin"], "fundingRate": "0.00001", "premium": "0", "time": t}
                for t in range(first, end + 1, HOUR)][:500]
    if kind == "clearinghouseState":
        if STATE.get("account_broken"):
            return {"error": "unexpected"}
        return {"assetPositions": [{"position": p, "type": "oneWay"} for p in STATE["positions"]],
                "marginSummary": {"accountValue": STATE["equity"], "totalMarginUsed": "0", "totalNtlPos": "0"},
                "crossMarginSummary": {"accountValue": STATE["equity"]}, "withdrawable": STATE["equity"],
                "time": STATE.get("time", NOW)}
    if kind == "userAbstraction":
        return "default"
    if kind == "frontendOpenOrders":
        return STATE["orders"]
    if kind == "activeAssetData":
        return {"leverage": {"type": "cross", "value": STATE["leverage"]}}
    if kind in ("userFillsByTime", "userFunding"):  # oldest first, capped like the venue's pages
        if STATE.get("ledger_broken"):
            return {"error": "not a list"}
        rows = STATE["fills" if kind == "userFillsByTime" else "funding"]
        found = sorted((r for r in rows if body["startTime"] <= r["time"] <= body.get("endTime", NOW)),
                       key=lambda r: r["time"])
        return found[:2000 if kind == "userFillsByTime" else 500]
    return None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body.get("type") == "activeAssetData" and STATE.get("leverage_fails"):
            self.send_response(429)
            self.end_headers()
            return
        self.reply(handle(body))

    def do_GET(self):  # Binance's public klines
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        start = int(query.get("startTime", -1))
        # Binance answers 400 to an unknown symbol and to a negative startTime alike
        if url.path != "/api/v3/klines" or query.get("symbol") != "UPUSDT" or start < 0:
            self.send_response(400)
            self.end_headers()
            return
        end, limit = int(query["endTime"]), int(query["limit"])
        step = STEPS[query["interval"]]
        first = max(start + (-start) % step, NOW - 9000 * step)
        rows = []
        for t in range(first, end + 1, step):
            b = generated(t)
            rows.append([t, str(b["o"]), str(b["h"]), str(b["l"]), str(b["c"]), "1", t + step - 1])
            if len(rows) == limit:
                break
        self.reply(rows)

    def reply(self, value):
        out = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture(autouse=True)
def fresh_venue():
    reset()


@pytest.fixture(scope="module")
def api():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def env(tmp_path: Path, api: str, now: int = NOW) -> dict:
    return {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "WEB3_ENGINE_TEST": "1",
            "HERMES_LOCAL": str(RUNTIME_ROOT), "HL_GATE_API": api, "HL_GATE_NOW": str(now)}


# --- the backtest read --------------------------------------------------------------------------

RULES = {"kind": "breakout", "entry": 20, "exit": 10, "atr": 14, "stop_atr": 2, "risk_pct": 1}


def backtest(payload: dict, api: str, tmp_path: Path) -> dict:
    request = {"action": "backtest", "network": "testnet", "_api": api, "_long": api, "coin": "UP", "rules": RULES,
               "end_time": NOW, **payload}
    proc = subprocess.run([str(PYTHON), str(SHARED / "hl.py")], input=json.dumps(request), capture_output=True,
                          text=True, timeout=120, env=env(tmp_path, api))
    return json.loads(proc.stdout)


def test_a_backtest_trades_the_venues_candles_and_names_its_rules(api, tmp_path):
    reply = backtest({}, api, tmp_path)
    assert reply["ok"], reply
    data = reply["data"]
    assert data["schema"] == "hermes-hyperliquid-backtest/1" and data["data"]["bars"] == 4999
    assert [s["source"] for s in data["data"]["sources"]] == ["Hyperliquid testnet UP"]
    assert data["result"]["trades"] > 5 and len(data["trades"]["newest"]) <= 20
    assert len(data["fingerprint"]) == 16 and data["costs"]["taker_bps"] == 4.5
    assert data["data"]["funding"]["hours_read"] == 4000 and data["data"]["funding"]["mean_sign"] == "longs pay"
    mc = data["result"]["monte_carlo"]
    assert mc["trades"] == data["result"]["trades"] and mc["runs"] == 1000
    assert mc["max_drawdown_pct"]["p50"] <= mc["max_drawdown_pct"]["p95"] <= mc["max_drawdown_pct"]["p99"]
    again = backtest({}, api, tmp_path)["data"]
    assert again["result"] == data["result"] and again["fingerprint"] == data["fingerprint"]  # the same spread too
    other = backtest({"costs": {"slippage_bps": 6}}, api, tmp_path)["data"]["result"]["monte_carlo"]
    assert other["max_drawdown_pct"] != mc["max_drawdown_pct"]  # another request draws its own


def test_long_history_adds_older_binance_prices_and_walk_forward_reports_unseen_windows(api, tmp_path):
    reply = backtest({"long_history": True, "walk_forward": {"grid": {"entry": [20, 40]}, "folds": 3}}, api, tmp_path)
    assert reply["ok"], reply
    data = reply["data"]
    sources = data["data"]["sources"]
    assert sources[0]["source"].startswith("Binance spot UPUSDT") and sources[0]["end"] < sources[1]["start"]
    assert data["data"]["bars"] > 8000 and any("took the mean rate" in u for u in data["unread"])
    folds = data["walk_forward"]["folds"]
    assert len(folds) == 3 and all(f["train"]["end"] < f["test"]["start"] for f in folds)
    oos = data["walk_forward"]["out_of_sample"]
    assert oos["monte_carlo"]["trades"] == oos["trades"] and oos["monte_carlo"] != data["result"]["monte_carlo"]


def test_daily_long_history_starts_where_the_exchange_does_not_before_the_epoch(api, tmp_path):
    reply = backtest({"interval": "1d", "long_history": True}, api, tmp_path)
    assert reply["ok"], reply
    data = reply["data"]
    sources = data["data"]["sources"]
    assert sources[0]["source"].startswith("Binance spot UPUSDT") and sources[0]["start"] >= "2017-07-14"
    assert not any("has no UPUSDT" in u for u in data.get("unread", []))


def test_a_backtest_refuses_what_it_cannot_trade(api, tmp_path):
    for payload, why in (({"coin": "PURR/USDC"}, "main-dex perp"), ({"rules": {"kind": "rsi"}}, "kind is one of"),
                         ({"interval": "1m"}, "15m"), ({"long_history": "yes"}, "long_history"),
                         ({"coin": "NONE"}, "too few")):
        reply = backtest(payload, api, tmp_path)
        assert not reply["ok"] and why in reply["error"], (payload, reply)
    other = backtest({"coin": "NONE", "long_history": True}, api, tmp_path)
    assert not other["ok"]


# --- the gate -----------------------------------------------------------------------------------

OOS = {"return_pct": 40.1, "max_drawdown_pct": 18.5, "mar": 0.9, "trades": 64}


BREAKER = {"max_drawdown_pct": 25}


def strategy_dir(root: Path, mandate: bool = True, stance: dict | None = None, oos: bool = True,
                 breaker: dict | None = BREAKER, **rule_over) -> Path:
    import importlib.util

    spec_mod = importlib.util.spec_from_file_location("hs_for_engine_test", SHARED / "hl_strategy.py")
    hs = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(hs)
    rules = {"kind": "breakout", "entry": 20, "exit": 10, "atr": 14, "stop_atr": 2, "risk_pct": 1, **rule_over}
    validated = {"fingerprint": hs.fingerprint(hs.rules(rules), "4h"), **({"out_of_sample": OOS} if oos else {})}
    spec = {"schema": hs.SPEC_SCHEMA, "name": "trend", "network": "testnet", "account": "hermes/HERMES_MAIN#0",
            "address": USER, "markets": ["BTC", "ETH"], "interval": "4h",
            "variants": {"t20": {"rules": rules, "validated": validated}},
            "limits": {"exposure_pct": 70, "max_leverage": 2},
            "mandate": ({"id": "m1", "max_order_usd": "300", "max_exposure_usd": "600", "max_leverage": 2,
                         "expires": NOW + 20 * 24 * HOUR} if mandate else None),
            **({"breaker": breaker} if breaker is not None else {})}
    directory = root / "trend"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spec.json").write_text(json.dumps(spec))
    if stance is not None:
        (directory / "stance.json").write_text(json.dumps(stance))
    return directory


def gate(root: Path, api: str, tmp_path: Path, now: int = NOW, snapshot: int | None = None) -> dict:
    STATE["time"] = snapshot or now  # the venue's time of the account read, a little after the run starts
    proc = subprocess.run([str(PYTHON), str(SHARED / "hl_gate.py"), str(root)], capture_output=True, text=True,
                          timeout=60, env=env(tmp_path, api, now))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_a_breakout_wakes_the_assistant_with_exact_quotes_once_per_bar(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    report = gate(root, api, tmp_path)
    assert report["wakeAgent"] is True
    part = report["strategies"][0]
    assert part["account"] == "hermes/HERMES_MAIN#0" and part["address"] == USER.lower()  # the run's reads take it
    intents = part["intents"]
    assert [i["id"].split(":")[-1] for i in intents] == ["leverage", "open"]
    lev, entry = intents[0]["quote"], intents[1]["quote"]
    assert lev == {"action": "quote", "account": "hermes/HERMES_MAIN#0", "network": "testnet", "kind": "leverage",
                   "coin": "BTC", "leverage": 2, "margin_mode": "cross"}
    assert entry["kind"] == "order" and entry["side"] == "buy" and entry["type"] == "market"
    assert float(entry["sl"]) < 110 and 10 <= float(entry["usd"]) <= 300 * 0.98
    assert all(i["effect"] == "increase" for i in intents)
    assert gate(root, api, tmp_path) == {"wakeAgent": False}  # the same bar is read once


def test_without_a_mandate_an_entry_is_only_noted_and_said_once(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    strategy_dir(root, mandate=False)
    report = gate(root, api, tmp_path)
    part = report["strategies"][0]
    assert part["intents"] == [] and any("no mandate in force" in n for n in part["new_notices"])
    assert any("the rules open a long" in n for n in part["notes"])
    assert gate(root, api, tmp_path) == {"wakeAgent": False}


def test_a_variant_without_an_out_of_sample_record_opens_nothing_but_still_protects(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root, oos=False)
    part = gate(root, api, tmp_path)["strategies"][0]
    assert [(i["market"], i["quote"]["kind"]) for i in part["intents"]] == [("ETH", "tpsl")]
    assert [n for n in part["new_notices"] if "t20" in n or "BTC" in n] == [
        "variant t20 has no walk-forward out_of_sample recorded in the spec: its markets open nothing until it is; "
        "closes and stops go on"]
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    assert gate(root, api, tmp_path) == {"wakeAgent": False}  # said once
    # the next bar breaks out again: still nothing to say, so no model wakes
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0], NOW + H4)
    STATE["bars"]["ETH"] = series([50.0] * 42, NOW + H4)
    assert gate(root, api, tmp_path, NOW + H4) == {"wakeAgent": False}


def kinds(report: dict) -> list[str]:
    return [i["id"].split(":")[-1] for s in report.get("strategies", []) for i in s["intents"]]


def test_without_a_usable_breaker_entries_are_held_and_said_once_while_stops_go_on(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    root = tmp_path / "hl-strategies"
    directory = strategy_dir(root, breaker=None)
    part = gate(root, api, tmp_path)["strategies"][0]
    assert kinds({"strategies": [part]}) == ["protect"]
    assert any(n.startswith("no breaker in the spec") for n in part["new_notices"]) and part["breaker"]["tripped"] is None
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    assert gate(root, api, tmp_path) == {"wakeAgent": False}
    spec = json.loads((directory / "spec.json").read_text())
    (directory / "spec.json").write_text(json.dumps({**spec, "breaker": {"max_drawdown_pct": 200}}))
    part = gate(root, api, tmp_path)["strategies"][0]
    assert part["intents"] == [] and any(n.startswith("breaker not used: breaker.max_drawdown_pct") for n in part["new_notices"])


def test_the_breaker_trips_on_the_strategys_own_losses_and_only_a_later_reset_resumes(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    directory = strategy_dir(root)
    first = gate(root, api, tmp_path)["strategies"][0]
    assert kinds({"strategies": [first]}) == ["leverage", "open"]  # the first run only sets the baseline
    assert first["breaker"]["drawdown_pct"] == 0 and first["breaker"]["max_drawdown_pct"] == 25
    # another market loses, and an ETH short is 10 down against the 1000 the account held then: only the
    # short counts; a deposit that doubles the account moves nothing
    STATE["fills"] = [{"coin": "SOL", "time": NOW + HOUR, "closedPnl": "-500", "fee": "1", "feeToken": "USDC",
                       "tid": 1, "oid": 1, "sz": "1", "px": "1"}]
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "60", "unrealizedPnl": "-10"}]
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "75"}]
    STATE["equity"] = "2000"
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0], NOW + H4)
    second = gate(root, api, tmp_path, NOW + H4)["strategies"][0]
    assert second["breaker"]["drawdown_pct"] == 1.0 and kinds({"strategies": [second]}) == ["leverage", "open"]
    # the short closes at that loss (its fill's result replaces its unrealized one, nothing twice); BTC
    # loses 590 with 5 in fees and pays 5 in funding: 600 of the 2000 the account held, a 30% fall from
    # the 1% already down
    STATE["positions"], STATE["orders"] = [], []
    STATE["fills"] += [{"coin": "ETH", "time": NOW + H4 + HOUR, "closedPnl": "-10", "fee": "0", "feeToken": "USDC",
                        "tid": 2, "oid": 2, "sz": "1", "px": "60"},
                       {"coin": "BTC", "time": NOW + H4 + HOUR, "closedPnl": "-590", "fee": "5", "feeToken": "USDC",
                        "tid": 3, "oid": 3, "sz": "1", "px": "100"}]
    STATE["funding"] = [{"time": NOW + H4 + 2 * HOUR, "hash": "0x01",
                         "delta": {"type": "funding", "coin": "BTC", "usdc": "-5", "szi": "1", "fundingRate": "0.0001"}}]
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0], NOW + 2 * H4)
    third = gate(root, api, tmp_path, NOW + 2 * H4)["strategies"][0]
    assert third["breaker"]["drawdown_pct"] == pytest.approx(30.7)
    assert third["breaker"]["tripped"] is not None and kinds({"strategies": [third]}) == []
    assert any(n.startswith("breaker tripped at") and "30.7% below its high" in n for n in third["new_notices"])
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0, 116.0], NOW + 3 * H4)
    assert gate(root, api, tmp_path, NOW + 3 * H4) == {"wakeAgent": False}  # still held, said once
    # a reset written before the trip resumes nothing; one after it does, from the index now
    spec = json.loads((directory / "spec.json").read_text())
    tripped_at = NOW + 2 * H4
    (directory / "spec.json").write_text(json.dumps({**spec, "breaker": {"max_drawdown_pct": 25, "reset": tripped_at - 1}}))
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0, 116.0, 118.0], NOW + 4 * H4)
    assert gate(root, api, tmp_path, NOW + 4 * H4) == {"wakeAgent": False}
    (directory / "spec.json").write_text(json.dumps({**spec, "breaker": {"max_drawdown_pct": 25, "reset": NOW + 4 * H4}}))
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0, 116.0, 118.0, 120.0], NOW + 5 * H4)
    resumed = gate(root, api, tmp_path, NOW + 5 * H4)["strategies"][0]
    assert kinds({"strategies": [resumed]}) == ["leverage", "open"] and resumed["breaker"]["drawdown_pct"] == 0
    assert any(n.startswith("breaker reset at") for n in resumed["new_notices"])


def test_an_entry_waits_for_a_run_that_can_read_the_breaker(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    STATE["ledger_broken"] = True
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0], NOW + H4)
    part = gate(root, api, tmp_path, NOW + H4)["strategies"][0]
    assert part["intents"] == [] and "fills or funding could not be read" in part["problems"][0]
    assert "breaker" not in part
    STATE["ledger_broken"] = False
    assert kinds(gate(root, api, tmp_path, NOW + H4)) == ["leverage", "open"]  # the same bar, read again


def test_the_breaker_reads_up_to_the_account_read_so_nothing_falls_between(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    # a BTC position closes at a 300 loss after the run starts but before its account read: the fill is
    # counted with the read that no longer shows the position
    STATE["fills"] = [{"coin": "BTC", "time": NOW + H4 + 2000, "closedPnl": "-300", "fee": "0", "feeToken": "USDC",
                       "tid": 1, "oid": 1, "sz": "1", "px": "100"}]
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0], NOW + H4)
    part = gate(root, api, tmp_path, NOW + H4, snapshot=NOW + H4 + 5000)["strategies"][0]
    assert part["breaker"]["drawdown_pct"] == 30.0 and part["breaker"]["tripped"] is not None and part["intents"] == []


def test_fills_are_paged_without_counting_a_shared_millisecond_twice_and_a_held_position_is_the_baseline(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "100", "unrealizedPnl": "-50"}]
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "120"}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root, breaker={"max_drawdown_pct": 60})
    assert gate(root, api, tmp_path)["strategies"][0]["breaker"]["drawdown_pct"] == 0  # the open loss is the start

    def at(i):  # ten fills share the millisecond the first page ends on
        return NOW + 1000 + i if i < 1995 else NOW + 2995 if i < 2005 else NOW + 3000 + i
    STATE["fills"] = [{"coin": "BTC", "time": at(i), "closedPnl": "-0.2", "fee": "0", "feeToken": "USDC",
                       "tid": i, "oid": i, "sz": "1", "px": "100"} for i in range(2500)]
    assert gate(root, api, tmp_path, NOW + H4) == {"wakeAgent": False}  # nothing to do or say
    memory = json.loads((root / "trend" / "state.json").read_text())["breaker"]
    assert memory["index"] == pytest.approx(0.5) and memory["tripped"] is None  # 500 of 1000, every fill once
    STATE["funding"] = [{"time": NOW + H4 + 10 + i, "hash": f"0x{i:04x}",
                         "delta": {"type": "funding", "coin": "BTC", "usdc": "-0.01"}} for i in range(2600)]
    part = gate(root, api, tmp_path, NOW + 2 * H4)["strategies"][0]
    assert "more userFunding rows than 5 reads cover" in part["problems"][0] and "breaker" not in part


def test_a_breaker_whose_memory_was_lost_holds_entries_until_the_user_resumes_it(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    directory = strategy_dir(root)
    gate(root, api, tmp_path)
    (directory / "state.json").write_text("{")
    STATE["account_broken"] = True  # the run that finds it cannot read the account either: the loss is kept
    assert "could not be read" in gate(root, api, tmp_path, NOW + H4)["strategies"][0]["problems"][0]
    STATE["account_broken"] = False
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]  # with no stop
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0], NOW + H4)
    part = gate(root, api, tmp_path, NOW + H4)["strategies"][0]
    assert kinds({"strategies": [part]}) == ["protect"] and part["breaker"]["tripped"] is not None  # no entry
    assert any(n.startswith("breaker holding since") and "drawdown is unknown" in n for n in part["new_notices"])
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0], NOW + 2 * H4)
    assert gate(root, api, tmp_path, NOW + 2 * H4) == {"wakeAgent": False}
    spec = json.loads((directory / "spec.json").read_text())
    (directory / "spec.json").write_text(json.dumps({**spec, "breaker": {**BREAKER, "reset": NOW + 2 * H4}}))
    STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0, 112.0, 114.0, 116.0], NOW + 3 * H4)
    assert kinds(gate(root, api, tmp_path, NOW + 3 * H4)) == ["leverage", "open"]
    # a state that is not an object, or a breaker missing a field the gate reads, is lost the same way
    good = json.loads((directory / "state.json").read_text())
    memory = good["breaker"]
    for n, broken in enumerate(("null", "[]", json.dumps({**good, "breaker": {**memory, "index": "high"}}),
                                json.dumps({**good, "breaker": {k: v for k, v in memory.items() if k != "tripped"}}),
                                json.dumps({**good, "breaker": {**memory, "tripped": {"at": NOW}}}),
                                json.dumps({**good, "breaker": {**memory, "equity": 10 ** 400}}))):
        (directory / "state.json").write_text(broken)
        later = NOW + (4 + n) * H4
        STATE["bars"]["BTC"] = series([100.0] * 40 + [110.0] + [112.0 + 2 * k for k in range(5 + n)], later)
        part = gate(root, api, tmp_path, later)["strategies"][0]
        assert part["intents"] == [] and part["breaker"]["tripped"] is not None, broken


def fill(coin, t, direction, side, px, sz, fee, oid, crossed=True, pnl="0"):
    return {"coin": coin, "time": t, "dir": direction, "side": side, "px": px, "sz": sz, "fee": fee, "feeToken": "USDC",
            "crossed": crossed, "closedPnl": pnl, "tid": oid * 10, "oid": oid}


def test_the_gate_measures_what_each_order_cost_against_what_the_strategy_expected(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    assert kinds(gate(root, api, tmp_path)) == ["leverage", "open"]  # a long on the close at 110
    # the run bought at 110.55 in two parts (50 bps past the close, taker), and someone shorted ETH by hand
    STATE["fills"] = [fill("BTC", NOW + 1000, "Open Long", "B", "110.5", "0.5", "0.025", 1),
                      fill("BTC", NOW + 1001, "Open Long", "B", "110.6", "0.5", "0.025", 1),
                      fill("ETH", NOW + 2000, "Open Short", "A", "50", "1", "0.01", 2, crossed=False)]
    STATE["positions"] = [{"coin": "BTC", "szi": "1", "entryPx": "110.55", "positionValue": "110.55"},
                          {"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    STATE["orders"] = [{"coin": "BTC", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "105"},
                       {"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    gate(root, api, tmp_path, NOW + H4)
    memory = json.loads((root / "trend" / "state.json").read_text())["execution"]
    assert memory["totals"]["entry"]["slippage_usd"] == pytest.approx(0.55) and memory["expect"] == {}
    assert memory["stops"]["BTC"][-1] == {"side": "sell", "ref": 105.0, "oid": None}  # the one in force, newest
    # the BTC stop fires at 104.5, half a dollar under its trigger: the position is gone, so the run wakes
    STATE["fills"].append(fill("BTC", NOW + H4 + 1000, "Close Long", "A", "104.5", "1", "0.047", 3, pnl="-6.05"))
    STATE["positions"] = [p for p in STATE["positions"] if p["coin"] == "ETH"]
    STATE["orders"] = STATE["orders"][1:]
    part = gate(root, api, tmp_path, NOW + 2 * H4)["strategies"][0]
    assert part["fills_measured"] == [{"market": "BTC", "kind": "stop", "side": "sell", "size": "1", "price": "104.5",
                                       "reference": "105", "slippage_bps": 47.62, "fee_bps": 4.5, "maker_pct": 0.0}]
    costs = part["execution"]["costs"]
    assert costs["entry"] == {"orders": 1, "slippage_bps": 50.0, "fee_bps": 4.52, "maker_pct": 0.0}
    assert costs["stop"]["slippage_bps"] == 47.62 and costs["other"] == {"orders": 1, "slippage_bps": None,
                                                                         "fee_bps": 2.0, "maker_pct": 100.0}
    # a memory of a shape the gate never writes starts again rather than stopping the gate
    state = json.loads((root / "trend" / "state.json").read_text())
    for n, broken in enumerate(({"totals": {"entry": {"orders": "x"}}, "since": NOW},
                                {"expect": {"BTC": {"entry": {"side": "buy", "ref": 0}}}},
                                {"stops": {"BTC": [{"side": "sell", "ref": 90, "oid": "7"}]}},
                                {"since": 10 ** 400, "expect": {"BTC": {"entry": [{"side": "buy", "ref": 10 ** 400}]}}},
                                {"since": 1e30, "totals": {"entry": dict.fromkeys(
                                    ("orders", "notional_usd", "fees_usd", "maker_notional_usd",
                                     "reference_notional_usd", "slippage_usd"), 1)}},
                                {"totals": {"entry": dict.fromkeys(("orders", "notional_usd", "fees_usd",
                                                                   "maker_notional_usd", "reference_notional_usd",
                                                                   "slippage_usd"), 1)}})):
        (root / "trend" / "state.json").write_text(json.dumps({**state, "execution": broken}))
        gate(root, api, tmp_path, NOW + (3 + n) * H4)
        kept = json.loads((root / "trend" / "state.json").read_text())["execution"]
        assert "entry" not in kept.get("totals", {}) and "BTC" not in kept.get("expect", {}), broken


def test_a_reversal_prices_its_close_and_its_entry_and_a_split_order_counts_once(api, tmp_path):
    reset()
    # a long the rules now exit and turn short; ETH is held long with a stop far below
    STATE["bars"] = {"BTC": series([100.0] * 40 + [95.0], NOW), "ETH": series([50.0] * 41, NOW)}
    STATE["positions"] = [{"coin": "BTC", "szi": "1", "entryPx": "100", "positionValue": "95"},
                          {"coin": "ETH", "szi": "1", "entryPx": "50", "positionValue": "50"}]
    STATE["orders"] = [{"coin": "BTC", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "90", "oid": 7},
                       {"coin": "ETH", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "40", "oid": 8}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    assert kinds(gate(root, api, tmp_path)) == ["close", "leverage", "open"]  # both on the close at 95
    # the close sold at 94.8; the short sold half at 94.7 (taker) and the rest only after the next read
    # (maker); ETH was sold by hand at 60, far above its stop: not a stop
    STATE["fills"] = [fill("BTC", NOW + 1000, "Close Long", "A", "94.8", "1", "0.04", 11),
                      fill("BTC", NOW + 2000, "Open Short", "A", "94.7", "0.5", "0.02", 12),
                      fill("ETH", NOW + 3000, "Close Long", "A", "60", "1", "0.03", 13)]
    STATE["positions"] = [{"coin": "BTC", "szi": "-0.5", "entryPx": "94.7", "positionValue": "47.35"}]
    STATE["orders"] = []
    gate(root, api, tmp_path, NOW + H4)
    STATE["fills"].append(fill("BTC", NOW + H4 + 1000, "Open Short", "A", "94.9", "0.5", "-0.001", 12, crossed=False))
    gate(root, api, tmp_path, NOW + 2 * H4)
    totals = json.loads((root / "trend" / "state.json").read_text())["execution"]["totals"]
    assert totals["close"]["orders"] == 1 and totals["close"]["slippage_usd"] == pytest.approx(0.2)
    assert totals["entry"]["orders"] == 1 and totals["entry"]["slippage_usd"] == pytest.approx(0.2)  # 0.15 + 0.05
    assert totals["entry"]["maker_notional_usd"] == pytest.approx(47.45)  # the half that rested
    assert totals["other"]["orders"] == 1 and "stop" not in totals


def held_long(stop_oid: int = 7) -> None:
    STATE["positions"] = [{"coin": "BTC", "szi": "1", "entryPx": "100", "positionValue": "100"}]
    STATE["orders"] = [{"coin": "BTC", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "90", "oid": stop_oid}]


def totals_now(root: Path) -> dict:
    return json.loads((root / "trend" / "state.json").read_text())["execution"]["totals"]


def test_closes_listed_while_fills_go_unread_are_each_priced_against_their_own_bar(api, tmp_path):
    reset()
    held_long()
    STATE["bars"] = {"BTC": series([100.0] * 40 + [95.0], NOW), "ETH": series([50.0] * 41, NOW)}
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    assert "close" in kinds(gate(root, api, tmp_path))  # against 95
    STATE["fills"] = [fill("BTC", NOW + 1000, "Close Long", "A", "94.5", "0.5", "0", 21)]  # half of it
    STATE["positions"] = [{"coin": "BTC", "szi": "0.5", "entryPx": "100", "positionValue": "47.5"}]
    STATE["ledger_broken"] = True
    STATE["bars"]["BTC"] = series([100.0] * 40 + [95.0, 90.0], NOW + H4)
    assert "close" in kinds(gate(root, api, tmp_path, NOW + H4))  # against 90, while the first is unread
    STATE["fills"].append(fill("BTC", NOW + H4 + 1000, "Close Long", "A", "89.8", "0.5", "0", 22))
    STATE["positions"], STATE["orders"], STATE["ledger_broken"] = [], [], False
    gate(root, api, tmp_path, NOW + 2 * H4)
    close = totals_now(root)["close"]
    assert close["orders"] == 2 and close["slippage_usd"] == pytest.approx(0.25 + 0.1)
    assert close["reference_notional_usd"] == pytest.approx(95 * 0.5 + 90 * 0.5)


def test_one_order_that_closes_and_reverses_is_priced_as_the_entry(api, tmp_path):
    reset()
    held_long()
    STATE["bars"] = {"BTC": series([100.0] * 40 + [95.0], NOW), "ETH": series([50.0] * 41, NOW)}
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    STATE["fills"] = [fill("BTC", NOW + 1000, "Close Long", "A", "94.9", "1", "0.04", 31),
                      fill("BTC", NOW + 1001, "Open Short", "A", "94.9", "0.5", "0.02", 31)]
    STATE["positions"] = [{"coin": "BTC", "szi": "-0.5", "entryPx": "94.9", "positionValue": "47.45"}]
    STATE["orders"] = []
    gate(root, api, tmp_path, NOW + H4)
    totals = totals_now(root)
    assert set(totals) == {"entry"} and totals["entry"]["orders"] == 1
    assert totals["entry"]["slippage_usd"] == pytest.approx(0.1 * 1.5)


def test_a_close_by_hand_is_not_taken_for_a_stop_whose_order_is_known(api, tmp_path):
    reset()
    held_long()
    STATE["bars"] = {"BTC": series([100.0] * 41, NOW), "ETH": series([50.0] * 41, NOW)}
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    STATE["fills"] = [fill("BTC", NOW + 1000, "Close Long", "A", "89.5", "1", "0.04", 8)]  # not the stop's order 7
    STATE["positions"], STATE["orders"] = [], []
    gate(root, api, tmp_path, NOW + H4)
    assert set(totals_now(root)) == {"other"}


def test_a_stop_that_fires_while_fills_cannot_be_read_is_priced_once_they_can(api, tmp_path):
    reset()
    STATE["bars"] = {"BTC": series([100.0] * 41, NOW), "ETH": series([50.0] * 41, NOW)}
    STATE["positions"] = [{"coin": "BTC", "szi": "1", "entryPx": "100", "positionValue": "100"}]
    STATE["orders"] = [{"coin": "BTC", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "90", "oid": 7}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    STATE["positions"], STATE["orders"], STATE["ledger_broken"] = [], [], True
    STATE["fills"] = [fill("BTC", NOW + 1000, "Close Long", "A", "89.5", "1", "0.04", 7, pnl="-10.5")]
    gate(root, api, tmp_path, NOW + H4)
    STATE["ledger_broken"] = False
    assert gate(root, api, tmp_path, NOW + 2 * H4) == {"wakeAgent": False}  # the position's end was said already
    stop = json.loads((root / "trend" / "state.json").read_text())["execution"]["totals"]["stop"]
    assert stop["slippage_usd"] == pytest.approx(0.5) and stop["reference_notional_usd"] == 90  # by its order id


def test_the_gate_keeps_the_start_equity_and_notices_a_position_the_venue_closed(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    first = gate(root, api, tmp_path)["strategies"][0]
    assert first["start_equity_usd"] == "1000.00" and first["equity_usd"] == "1000.00"
    state = json.loads((root / "trend" / "state.json").read_text())
    assert state["start_equity_usd"] == "1000.00" and state["positions"]["ETH"]["side"] == "short"
    since = state["positions"]["ETH"]["since"]
    STATE["equity"] = "990"  # the position stays; the start does not move, nor does since
    later = gate(root, api, tmp_path, NOW + H4)
    state = json.loads((root / "trend" / "state.json").read_text())
    assert state["start_equity_usd"] == "1000.00" and state["positions"]["ETH"]["since"] == since
    assert not any(i["market"] == "ETH" for s in later.get("strategies", []) for i in s["intents"])
    STATE["positions"], STATE["orders"] = [], []  # the stop fired on the venue: gone, with no intent
    gone = gate(root, api, tmp_path, NOW + 2 * H4)["strategies"][0]
    assert any("ETH: the short of 1 @ 50 seen since" in n and "gone from the account" in n for n in gone["new_notices"])
    assert "ETH" not in json.loads((root / "trend" / "state.json").read_text())["positions"]
    assert gate(root, api, tmp_path, NOW + 3 * H4) == {"wakeAgent": False}  # said once


def test_a_close_the_gate_listed_is_not_noticed_again_and_an_empty_account_sets_no_start(api, tmp_path):
    reset()
    STATE["equity"] = "0"
    root = tmp_path / "hl-strategies"
    stance = {"schema": "hermes-hyperliquid-stance/1", "strategy": "trend", "issued": NOW - 24 * HOUR,
              "expires": NOW + 48 * HOUR, "markets": {"ETH": {"direction": "flat"}},
              "basis": [{"claim": "risk off", "source": "an advisor", "as_of": NOW - 30 * HOUR}]}
    strategy_dir(root, stance=stance)
    first = gate(root, api, tmp_path)
    state = json.loads((root / "trend" / "state.json").read_text())
    assert "start_equity_usd" not in state and "start_equity_usd" not in first.get("strategies", [{}])[0]
    STATE["equity"] = "1000"
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    (root / "trend" / "state.json").unlink()
    listed = gate(root, api, tmp_path)["strategies"][0]
    assert [i["quote"]["kind"] for i in listed["intents"] if i["market"] == "ETH"] == ["close"]
    state = json.loads((root / "trend" / "state.json").read_text())
    assert state["start_equity_usd"] == "1000.00" and state["positions"]["ETH"]["closing"] is True
    STATE["positions"] = []  # the Assistant sent the close and reported it: the next run says nothing
    assert gate(root, api, tmp_path, NOW + H4) == {"wakeAgent": False}
    assert "ETH" not in json.loads((root / "trend" / "state.json").read_text())["positions"]


def test_a_position_that_flipped_side_between_runs_is_noticed(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    STATE["orders"] = [{"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "60"}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    gate(root, api, tmp_path)
    STATE["positions"] = [{"coin": "ETH", "szi": "2", "entryPx": "51", "positionValue": "102"}]
    STATE["orders"] = [{"coin": "ETH", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "2", "triggerPx": "40"}]
    part = gate(root, api, tmp_path, NOW + H4)["strategies"][0]
    assert any("ETH: the short of 1 @ 50 seen since" in n for n in part["new_notices"])
    kept = json.loads((root / "trend" / "state.json").read_text())["positions"]["ETH"]
    assert kept["side"] == "long" and kept["since"] == NOW + H4


def test_a_flat_stance_closes_and_a_position_without_a_stop_is_protected(api, tmp_path):
    reset()
    STATE["positions"] = [{"coin": "BTC", "szi": "0.01", "entryPx": "100", "positionValue": "1.1"},
                          {"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    stance = {"schema": "hermes-hyperliquid-stance/1", "strategy": "trend",
              "issued": NOW - 24 * HOUR, "expires": NOW + 48 * HOUR,
              "markets": {"BTC": {"direction": "flat"}},
              "basis": [{"claim": "risk off", "source": "an advisor", "as_of": NOW - 30 * HOUR}]}
    root = tmp_path / "hl-strategies"
    strategy_dir(root, stance=stance)
    intents = {i["market"]: i for i in gate(root, api, tmp_path)["strategies"][0]["intents"]}
    assert intents["BTC"]["quote"]["kind"] == "close" and intents["BTC"]["effect"] == "reduce"
    assert intents["ETH"]["quote"]["kind"] == "tpsl" and float(intents["ETH"]["quote"]["sl"]) > 50
    STATE["orders"] = [{"coin": "ETH", "reduceOnly": True, "isTrigger": True, "sz": "1", "triggerPx": "60"}]
    later = gate(root, api, tmp_path, NOW + H4)
    kinds = [i["quote"]["kind"] for s in later["strategies"] for i in s["intents"]]
    assert kinds == ["close"]  # the close repeats while the position stands; the stop is there now


def test_an_unusable_spec_or_stance_is_said_once_and_never_traded(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    directory = strategy_dir(root, stance={"schema": "nope"})
    first = gate(root, api, tmp_path)["strategies"][0]
    assert any("advisor stance not used" in n for n in first["new_notices"]) and first["stance"]["BTC"]["source"] == "default"
    spec = json.loads((directory / "spec.json").read_text())
    spec["variants"]["t20"]["rules"]["entry"] = 21
    (directory / "spec.json").write_text(json.dumps(spec))
    part = gate(root, api, tmp_path)["strategies"][0]
    assert part["intents"] == [] and "not backtested as written" in part["problems"][0]
    assert gate(root, api, tmp_path) == {"wakeAgent": False}


def test_a_paused_strategy_is_not_read(api, tmp_path):
    reset()
    root = tmp_path / "hl-strategies"
    directory = strategy_dir(root)
    spec = json.loads((directory / "spec.json").read_text())
    (directory / "spec.json").write_text(json.dumps({**spec, "active": False}))
    assert gate(root, api, tmp_path) == {"wakeAgent": False}
    assert not (directory / "state.json").exists()


def test_a_take_profit_is_not_a_stop_but_a_whole_position_stop_is(api, tmp_path):
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    take_profit = {"coin": "ETH", "side": "B", "orderType": "Take Profit Market", "reduceOnly": True,
                   "isTrigger": True, "sz": "1", "triggerPx": "40"}
    wrong_side = {**take_profit, "orderType": "Stop Market", "side": "A", "triggerPx": "60"}
    small = {**wrong_side, "side": "B", "sz": "0.5"}
    STATE["orders"] = [take_profit, wrong_side, small]
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    kinds = [i["quote"]["kind"] for i in gate(root, api, tmp_path)["strategies"][0]["intents"] if i["market"] == "ETH"]
    assert kinds == ["tpsl"]
    STATE["orders"] = [take_profit, {**small, "sz": "0", "isPositionTpsl": True}]
    (root / "trend" / "state.json").unlink()
    report = gate(root, api, tmp_path)
    assert not any(i["market"] == "ETH" for s in report.get("strategies", []) for i in s["intents"])


def test_a_trailing_rule_replaces_a_looser_stop_once_per_bar_new_stop_first(api, tmp_path):
    STATE["positions"] = [{"coin": "ETH", "szi": "-1", "entryPx": "50", "positionValue": "50"}]
    loose = {"coin": "ETH", "side": "B", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
             "sz": "1", "triggerPx": "60", "oid": 777}
    stale = {**loose, "triggerPx": "65", "oid": 778}  # left from a run whose cancel did not go
    STATE["orders"] = [stale, loose]
    root = tmp_path / "hl-strategies"
    strategy_dir(root, trail_atr=2)  # ETH's bars are flat at 50 with a range of 1: the trail sits at 52
    intents = [i for i in gate(root, api, tmp_path)["strategies"][0]["intents"] if i["market"] == "ETH"]
    assert [i["id"].split(":")[-1] for i in intents] == ["trail", "untrail", "untrail1"]
    assert intents[0]["quote"]["kind"] == "tpsl" and float(intents[0]["quote"]["sl"]) == 52
    assert "from 60 to 52" in intents[0]["why"]
    assert intents[1]["quote"] == {"action": "quote", "account": "hermes/HERMES_MAIN#0", "network": "testnet",
                                   "kind": "cancel", "oid": 777}
    assert intents[2]["quote"]["oid"] == 778 and "at 65" in intents[2]["why"]
    assert all(i["after"] == intents[0]["id"] for i in intents[1:]) and all(i["effect"] == "reduce" for i in intents)
    assert gate(root, api, tmp_path) == {"wakeAgent": False}  # the same bar is read once
    STATE["orders"] = [{**loose, "triggerPx": "51.5"}]  # a stop already tighter than the trail stays
    (root / "trend" / "state.json").unlink()
    again = gate(root, api, tmp_path)
    assert not any(i["market"] == "ETH" for s in again.get("strategies", []) for i in s["intents"])
    STATE["orders"] = []  # without any stop the protection placed is the trailed level, not the entry's
    (root / "trend" / "state.json").unlink()
    intents = [i for i in gate(root, api, tmp_path)["strategies"][0]["intents"] if i["market"] == "ETH"]
    assert [i["id"].split(":")[-1] for i in intents] == ["protect"] and float(intents[0]["quote"]["sl"]) == 52


def test_a_trailed_stop_in_one_market_leaves_the_next_markets_entry_sized(api, tmp_path):
    reset()
    STATE["bars"] = {"BTC": series([100.0] * 41, NOW), "ETH": series([50.0] * 40 + [55.0], NOW)}
    STATE["positions"] = [{"coin": "BTC", "szi": "1", "entryPx": "100", "positionValue": "100"}]
    STATE["orders"] = [{"coin": "BTC", "side": "A", "orderType": "Stop Market", "reduceOnly": True, "isTrigger": True,
                        "sz": "1", "triggerPx": "90", "oid": 7}]
    root = tmp_path / "hl-strategies"
    strategy_dir(root, trail_atr=2)
    intents = gate(root, api, tmp_path)["strategies"][0]["intents"]
    assert [(i["market"], i["id"].split(":")[-1]) for i in intents] == [
        ("BTC", "trail"), ("BTC", "untrail"), ("ETH", "leverage"), ("ETH", "open")]
    assert 10 <= float(intents[-1]["quote"]["usd"]) <= 300 * 0.98


def test_an_entry_whose_leverage_could_not_be_read_is_tried_again_next_run(api, tmp_path):
    STATE["leverage_fails"] = True
    root = tmp_path / "hl-strategies"
    strategy_dir(root)
    first = gate(root, api, tmp_path)["strategies"][0]
    assert first["intents"] == [] and "tried again next run" in first["problems"][0]
    STATE["leverage_fails"] = False
    kinds = [i["quote"]["kind"] for i in gate(root, api, tmp_path)["strategies"][0]["intents"]]
    assert kinds == ["leverage", "order"]


def test_no_strategies_is_silent(api, tmp_path):
    assert gate(tmp_path / "missing", api, tmp_path) == {"wakeAgent": False}


def test_the_cron_script_reads_its_own_profile_home_and_finds_the_engine_through_plugins(api, tmp_path):
    """install.sh copies the script into <HERMES_HOME>/scripts (cron resolves real paths): the
    strategies are read from that home, whatever HERMES_HOME says; hl_gate.py is found in the
    repository through the home's plugins tree, the engine under the HERMES_LOCAL runtime root."""
    assert SCRIPT.stat().st_mode & 0o111
    home = tmp_path / ".hermes" / "profiles" / "assistant"
    (home / "scripts").mkdir(parents=True)
    copied = home / "scripts" / SCRIPT.name
    shutil.copy2(SCRIPT, copied)
    (home / "plugins" / "web3").mkdir(parents=True)
    (home / "plugins" / "web3" / "_shared").symlink_to(SHARED, target_is_directory=True)
    strategy_dir(home / "hl-strategies")

    def run(extra):
        proc = subprocess.run(["/bin/bash", str(copied)], capture_output=True, text=True, timeout=60,
                              env={**env(tmp_path, api), **extra}, cwd=str(copied.parent))
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip().splitlines()[-1])

    assert run({})["wakeAgent"] is True
    (home / "hl-strategies" / "trend" / "state.json").unlink()
    other = tmp_path / "elsewhere" / "profiles" / "assistant"
    other.mkdir(parents=True)
    assert run({"HERMES_HOME": str(other)})["wakeAgent"] is True  # the gateway's env names no other home

    # The engine is found through the runtime root, not the plugins tree: an empty root is "not installed".
    proc = subprocess.run(["/bin/bash", str(copied)], capture_output=True, text=True, timeout=60,
                          env={**env(tmp_path, api), "HERMES_LOCAL": str(tmp_path / "empty-root")}, cwd=str(copied.parent))
    assert proc.returncode == 1 and "web3 engine is not installed" in proc.stderr
