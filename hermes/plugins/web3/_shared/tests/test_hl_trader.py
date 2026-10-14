"""The Hyperliquid trader end to end in the web3 venv, against a fake /info and /exchange (no network,
no Keychain). The wallet is Hardhat's public test mnemonic, passed as ``_sources`` under
``WEB3_ENGINE_TEST``; nobody's funds."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import subprocess
import threading
import time

import pytest

HERMES = Path(__file__).resolve().parents[4]
PYTHON = HERMES / "local" / "web3" / "venv" / "bin" / "python"
TRADER = HERMES / "plugins" / "web3" / "_shared" / "hl_trader.py"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

MAIN_WORDS = "test test test test test test test test test test test junk"
TEAM_WORDS = "legal winner thank year wave sausage worth useful legal winner thank yellow"
MAIN, TEAM = "hermes/HERMES_MAIN", "team/PROD_MNEMONIC"
OPS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"  # MAIN #0
USER = OPS.lower()


def item(source, value):
    project, name = source.split("/")
    return {"id": source, "project": project, "scope": None, "name": name, "label": "MNEMONIC", "role": "seed",
            "value": value, "memo": None}


SOURCES = [item(MAIN, MAIN_WORDS), item(TEAM, TEAM_WORDS)]
VENUE: dict = {}
SEEN: list[dict] = []


def reset():
    VENUE.clear()
    VENUE.update({"positions": {"ETH": "-1.5"}, "leverage": {"BTC": {"type": "cross", "value": 10},
                                                              "ETH": {"type": "isolated", "value": 5}},
                  "exchange": "ok"})
    SEEN.clear()


def info(body):
    kind = body.get("type")
    if kind == "perpDexs":
        return [None]
    if kind == "metaAndAssetCtxs":
        return [{"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
                              {"name": "ETH", "szDecimals": 4, "maxLeverage": 25}]},
                [{"markPx": "99000", "midPx": "100000"}, {"markPx": "2500", "midPx": "2500.05"}]]
    if kind == "spotMetaAndAssetCtxs":
        return [{"universe": [{"tokens": [1, 0], "name": "@107", "index": 107, "isCanonical": False}],
                 "tokens": [{"name": "USDC", "szDecimals": 8, "index": 0}, {"name": "HYPE", "szDecimals": 2, "index": 1}]},
                [{"coin": "@107", "markPx": "40", "midPx": "40"}]]
    if kind == "clearinghouseState":
        return {"assetPositions": [{"position": {"coin": c, "szi": s}} for c, s in VENUE["positions"].items()]}
    if kind == "activeAssetData":
        return {"leverage": VENUE["leverage"].get(body["coin"])}
    if kind == "orderStatus":
        if body["oid"] in (42, "0x" + "42" * 16):
            return {"status": "order", "order": {"status": "open", "order": {
                "coin": "ETH", "side": "B", "limitPx": "2400", "sz": "1", "oid": 42, "orderType": "Limit",
                "reduceOnly": False, "tif": "Gtc", "cloid": "0x" + "42" * 16}}}
        if body["oid"] == 43:
            return {"status": "order", "order": {"status": "filled", "order": {"coin": "ETH", "oid": 43}}}
        return {"status": "unknownOid"}
    return None


def exchange(body):
    mode = VENUE["exchange"]
    if mode == "err":
        return 200, {"status": "err", "response": "Insufficient margin to place order."}
    if mode == "502":
        return 502, None
    if mode == "odd":
        return 200, {"status": "maybe"}
    if mode == "corrupt":
        return 200, {"status": "ok", "response": {"type": "order", "data": {"statuses": "corrupt"}}}
    action = body["action"]
    if action["type"] == "order":
        legs = []
        for order in action["orders"]:
            if "limit" in order["t"] and order["t"]["limit"]["tif"] == "Ioc":
                legs.append({"filled": {"totalSz": order["s"], "avgPx": order["p"], "oid": 7}})
            else:
                legs.append({"resting": {"oid": 8}})
        return 200, {"status": "ok", "response": {"type": "order", "data": {"statuses": legs}}}
    if action["type"] in ("cancel", "cancelByCloid"):
        return 200, {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    return 200, {"status": "ok", "response": {"type": "default"}}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "body": body})
        code, reply = exchange(body) if self.path == "/exchange" else (200, info(body))
        out = json.dumps(reply).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def api():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def run(api, tmp_path):
    reset()
    state = tmp_path / "web3-wallet"

    def call(op, **fields):
        payload = {"op": op, "state": str(state), "_sources": SOURCES, "_api": api, **fields}
        env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "WEB3_ENGINE_TEST": "1"}
        proc = subprocess.run([str(PYTHON), str(TRADER)], input=json.dumps(payload), capture_output=True, text=True,
                              timeout=90, env=env)
        return json.loads(proc.stdout)

    call.state = state
    return call


def ok(reply):
    assert reply["ok"], reply
    return reply["data"]


def quote(run, **fields):
    return ok(run("quote", account=f"{MAIN}#0", network="testnet", **fields))


def exchanged():
    return [s["body"] for s in SEEN if s["path"] == "/exchange"]


def submit(run, quote_id, approval):
    mac = ok(run("verify", quote=quote_id))["mac"]
    return run("submit", quote=quote_id, approval=approval, mac=mac)


# --- quotes -------------------------------------------------------------------------------------

def test_a_market_buy_is_rounded_to_the_venue_and_needs_the_card(run):
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    assert q["effect"] == "increase" and q["address"] == OPS
    s = q["summary"]
    assert s["price"] == "101000" and s["tif"] == "Ioc" and s["size"] == "0.00099"  # 100 / 101000, 5 decimals
    assert s["held"] == "0" and s["leverage"] == {"type": "cross", "value": 10}
    assert "Hyperliquid testnet" in q["card"] and "Buy: 0.00099 BTC perp · market, worst price 101000" in q["card"]
    assert "Effect: can add exposure" in q["card"] and OPS in q["card"]
    assert len(s["cloids"]) == 1 and s["cloids"][0].startswith("0x") and len(s["cloids"][0]) == 34


def test_a_limit_order_takes_the_tick_and_tp_sl_legs(run):
    q = quote(run, coin="ETH", side="long", size="0.123456", price="2412.345", tp="2600", sl="2300.004")
    s = q["summary"]
    assert s["price"] == "2412.3" and s["size"] == "0.1234" and s["tif"] == "Gtc"
    assert [(leg["leg"], leg["trigger"], leg["worst"]) for leg in s["legs"]] == [("tp", "2600", "2340"),
                                                                               ("sl", "2300", "2070")]
    assert len(s["cloids"]) == 3 and q["effect"] == "increase"
    assert "TP: trigger 2600, worst 2340" in q["card"]


@pytest.mark.parametrize("fields, needle", [
    ({"coin": "ETH", "side": "buy", "size": "1", "price": "2400", "sl": "2500"}, "stop-loss of a long sits below"),
    ({"coin": "ETH", "side": "sell", "size": "1", "price": "2400", "tp": "2500"}, "take-profit of a short sits below"),
    ({"coin": "BTC", "side": "buy", "usd": "5", "type": "market"}, "minimum is 10"),
    ({"coin": "BTC", "side": "buy", "size": "0.000001", "type": "market"}, "rounds to zero"),
    ({"coin": "BTC", "side": "buy", "size": "1", "usd": "100"}, "one of them"),
    ({"coin": "BTC", "side": "buy", "size": "0.01", "type": "market", "slippage": "0.2"}, "at most 0.05"),
    ({"coin": "BTC", "side": "buy", "size": "0.01", "type": "market", "price": "1"}, "takes no price"),
    ({"coin": "BTC", "side": "up", "size": "0.01"}, "side is buy or sell"),
    ({"coin": "HYPE/USDC", "side": "sell", "size": "1", "price": "40", "reduce_only": True}, "no reduce-only"),
    ({"coin": "DOGE", "side": "buy", "size": "1", "price": "1"}, "no perp 'DOGE'"),
    ({"kind": "close", "coin": "BTC"}, "holds no BTC position"),
    ({"kind": "leverage", "coin": "BTC", "leverage": 41}, "from 1 to 40"),
    ({"kind": "margin", "coin": "BTC", "amount": "5"}, "holds no BTC position"),
    ({"kind": "cancel", "oid": 43}, "is filled, not open"),
    ({"kind": "swap"}, "kind is one of"),
])
def test_what_the_venue_would_refuse_is_refused_at_quote_time(run, fields, needle):
    reply = run("quote", account=f"{MAIN}#0", network="testnet", **fields)
    assert not reply["ok"] and needle in reply["error"], reply


def test_only_a_hermes_wallet_trades(run):
    reply = run("quote", account=f"{TEAM}#0", network="testnet", coin="BTC", side="buy", usd="100", type="market")
    assert not reply["ok"] and "watch-only" in reply["error"]
    reply = run("quote", account=f"{MAIN}#0", network="devnet", coin="BTC", side="buy", usd="100")
    assert not reply["ok"] and "mainnet or testnet" in reply["error"]


@pytest.mark.parametrize("fields, effect", [
    ({"kind": "close", "coin": "ETH"}, "reduce"),
    ({"kind": "tpsl", "coin": "ETH", "sl": "2700"}, "reduce"),
    ({"coin": "ETH", "side": "buy", "size": "0.5", "price": "2400", "reduce_only": True}, "reduce"),
    ({"kind": "cancel", "oid": "42"}, "reduce"),
    ({"kind": "leverage", "coin": "ETH", "leverage": 3}, "increase"),  # unconditional at the venue: always asks
    ({"kind": "leverage", "coin": "ETH", "leverage": 8}, "increase"),
    ({"kind": "leverage", "coin": "ETH", "leverage": 3, "margin_mode": "cross"}, "increase"),
    ({"kind": "margin", "coin": "ETH", "amount": "5"}, "reduce"),
    ({"kind": "margin", "coin": "ETH", "amount": "5", "remove": True}, "increase"),
    ({"kind": "modify", "oid": 42, "price": "2410"}, "increase"),
    ({"coin": "HYPE/USDC", "side": "sell", "size": "1", "price": "40"}, "increase"),
])
def test_the_effect_follows_what_the_action_can_do(run, fields, effect):
    assert quote(run, **fields)["effect"] == effect


def test_close_and_tpsl_work_on_the_position_held(run):
    close = quote(run, kind="close", coin="ETH")["summary"]
    assert close["is_buy"] is True and close["size"] == "1.5" and close["reduce_only"] is True
    assert close["price"] == "2525"  # 2500.05 × 1.01, rounded down inside the bound
    tpsl = quote(run, kind="tpsl", coin="ETH", tp="2300", sl="2700")["summary"]
    assert [(leg["leg"], leg["size"]) for leg in tpsl["legs"]] == [("tp", "1.5"), ("sl", "1.5")]


def test_cancel_and_modify_read_the_order_first(run):
    cancel = quote(run, kind="cancel", oid=42)
    assert "Cancel: order 42 · buy 1 ETH at 2400" in cancel["card"]
    modify = quote(run, kind="modify", oid=42, price="2410.04", size="2")
    assert modify["summary"]["price"] == "2410" and modify["summary"]["size"] == "2"
    assert "Price 2400 → 2410 · size 1 → 2" in modify["card"]
    by_cloid = quote(run, kind="cancel", oid="0x" + "42" * 16)
    assert by_cloid["effect"] == "reduce"


# --- verify and submit --------------------------------------------------------------------------

def test_an_approved_order_is_signed_once_and_reports_its_fill(run):
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    done = ok(submit(run, q["quote"], "card"))
    assert done["submitted"] is True and done["statuses"] == [{"status": "filled", "size": "0.00099",
                                                               "average_price": "101000", "oid": 7}]
    (body,) = exchanged()
    assert body["action"]["type"] == "order" and body["action"]["orders"][0]["c"] == done["cloids"][0]
    assert body["vaultAddress"] is None and body["expiresAfter"] == body["nonce"] + 60_000
    assert set(body["signature"]) == {"r", "s", "v"}
    again = run("submit", quote=q["quote"], approval="card", mac="x")
    assert not again["ok"] and "already used" in again["error"] and len(exchanged()) == 1


def test_an_increase_never_goes_without_its_card(run):
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    verified = ok(run("verify", quote=q["quote"]))
    assert verified["effect"] == "increase" and verified["card"] == q["card"]
    reply = run("submit", quote=q["quote"], approval="reduce", mac=verified["mac"])
    assert not reply["ok"] and "needs the approval card" in reply["error"] and exchanged() == []


def test_a_reduce_runs_without_a_card_and_a_leverage_cut_never_does(run):
    lower = quote(run, kind="leverage", coin="ETH", leverage=3)
    assert ok(run("verify", quote=lower["quote"]))["effect"] == "increase"
    reply = submit(run, lower["quote"], "reduce")
    assert not reply["ok"] and "needs the approval card" in reply["error"] and exchanged() == []
    assert "Leverage: ETH perp 5x isolated → 3x isolated" in lower["card"]
    close = quote(run, kind="close", coin="ETH")
    assert ok(submit(run, close["quote"], "reduce"))["submitted"] is True


def test_a_stored_reduce_verdict_is_never_trusted_alone(run):
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    path = run.state / "hl-quotes" / f"{q['quote']}.json"
    stored = json.loads(path.read_text())
    stored["effect"] = "reduce"  # the MAC refuses the edit before the effect is even read
    path.write_text(json.dumps(stored))
    assert not run("verify", quote=q["quote"])["ok"]


def test_the_compact_card_keeps_every_signed_leg(run):
    q = quote(run, coin="ETH", side="buy", size="0.1", price="2400", tp="2600", sl="2300")
    path = run.state / "hl-quotes" / f"{q['quote']}.json"
    short = json.loads(path.read_text())["card_short"]
    assert "Buy: 0.1 ETH perp · limit 2400 Gtc" in short and "TP 2600→2340 · SL 2300→2070" in short
    assert "Value:" not in short and OPS in short


def test_a_spot_card_names_the_pair_the_venue_trades(run):
    q = quote(run, coin="HYPE/USDC", side="buy", size="1", price="40")
    assert "HYPE/USDC (@107) spot" in q["card"]


def test_a_market_orders_triggers_are_checked_against_the_mark(run):
    # mid 100000, mark 99000: a stop at 99500 sits below the mid but above the mark, so it would fire at once
    reply = run("quote", account=f"{MAIN}#0", network="testnet", coin="BTC", side="buy", usd="100", type="market",
                sl="99500")
    assert not reply["ok"] and "would fire at once" in reply["error"] and "99000" in reply["error"]
    VENUE["positions"]["BTC"] = "0.01"
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="tpsl", coin="BTC", sl="99500")
    assert not reply["ok"] and "would fire at once" in reply["error"]


@pytest.mark.parametrize("mode", ["odd", "corrupt"])
def test_an_answer_that_cannot_be_read_stays_unknown(run, mode):
    VENUE["exchange"] = mode
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    done = ok(submit(run, q["quote"], "card"))
    assert done["submitted"] == "unknown" and "never submit it again" in done["note"]
    rows = [json.loads(line) for line in (run.state / "hyperliquid.jsonl").read_text().splitlines()]
    assert [r["outcome"] for r in rows] == ["unknown"]


def test_leverage_and_margin_report_done_from_the_default_answer(run):
    q = quote(run, kind="margin", coin="ETH", amount="5")
    done = ok(submit(run, q["quote"], "reduce"))
    assert done["submitted"] is True and done["statuses"] == [{"status": "done"}]


def test_the_compact_card_fits_discord(run):
    q = quote(run, coin="ETH", side="buy", size="0.1", price="2400", tp="2600", sl="2300")
    short = json.loads((run.state / "hl-quotes" / f"{q['quote']}.json").read_text())["card_short"]
    escaped = short.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    assert len(escaped.encode("utf-16-le")) // 2 <= 290


def test_the_wrong_mac_or_an_edited_quote_sends_nothing(run):
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    reply = run("submit", quote=q["quote"], approval="card", mac="0" * 64)
    assert not reply["ok"] and "not the quote that was approved" in reply["error"]
    path = run.state / "hl-quotes" / f"{q['quote']}.json"
    stored = json.loads(path.read_text())
    stored["action"]["orders"][0]["s"] = "10"
    path.write_text(json.dumps(stored))
    reply = run("verify", quote=q["quote"])
    assert not reply["ok"] and "changed after it was made" in reply["error"] and exchanged() == []


def test_a_refusal_by_the_venue_is_rejected_and_never_retried(run):
    VENUE["exchange"] = "err"
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    reply = submit(run, q["quote"], "card")
    assert not reply["ok"] and "Insufficient margin" in reply["error"] and "make a new quote" in reply["error"]
    rows = [json.loads(line) for line in (run.state / "hyperliquid.jsonl").read_text().splitlines()]
    assert [r["outcome"] for r in rows] == ["unknown", "rejected"]
    assert not run("submit", quote=q["quote"], approval="card", mac="x")["ok"]


def test_no_answer_stays_unknown_and_is_looked_up_once(run):
    VENUE["exchange"] = "502"
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    done = ok(submit(run, q["quote"], "card"))
    assert done["submitted"] == "unknown" and "never submit it again" in done["note"]
    assert done["found"] == [{"cloid": q["summary"]["cloids"][0], "status": "not found (yet)"}]
    rows = [json.loads(line) for line in (run.state / "hyperliquid.jsonl").read_text().splitlines()]
    assert [r["outcome"] for r in rows] == ["unknown"] and len(exchanged()) == 1


def test_nonces_only_go_up(run):
    first = quote(run, kind="cancel", oid=42)
    second = quote(run, kind="cancel", oid=42)
    ok(submit(run, first["quote"], "reduce"))
    ok(submit(run, second["quote"], "reduce"))
    nonces = [body["nonce"] for body in exchanged()]
    assert nonces[1] > nonces[0]
    stored = json.loads((run.state / "hl-nonce.json").read_text())
    assert stored == {USER: nonces[1]}


def test_the_hourly_cap_stops_increases_but_never_a_reduce(run):
    run.state.mkdir(parents=True, exist_ok=True)
    now = time.time()
    with open(run.state / "hyperliquid.jsonl", "w") as handle:
        for n in range(30):
            handle.write(json.dumps({"time": now, "attempt": f"a{n}", "quote": f"h{n:08x}", "effect": "increase",
                                     "outcome": "sent"}) + "\n")
    q = quote(run, coin="BTC", side="buy", usd="100", type="market")
    reply = submit(run, q["quote"], "card")
    assert not reply["ok"] and "30 Hyperliquid actions that can add exposure" in reply["error"]
    close = quote(run, kind="close", coin="ETH")
    assert ok(submit(run, close["quote"], "reduce"))["submitted"] is True
