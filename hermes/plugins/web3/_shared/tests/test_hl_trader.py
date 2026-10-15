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
SPARE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"  # MAIN #1: own
STRANGER = "0x5e5E5e5e5E5e5E5E5e5E5E5e5e5E5E5E5e5E5E5e"
USDC_ID = "0x6d1e7cde53ba9467b783cb7c530ce054"
HYPE_ID = "0x0d01dc56dcaaca66ad901c959b4011ec"


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
                  "exchange": "ok", "open_orders": [], "withdrawable": "100", "mode": "default", "after_margin": None,
                  "spot": [("USDC", 0, "30", "5"), ("HYPE", 1, "2.5", "0"), ("DUP", 3, "5", "0"),
                           ("LONG", 4, "1.0000000001", "0"),
                           ("A_DEPLOYER_CHOSE_THIS_VERY_LONG_TOKEN_NAME", 6, "9", "0")]})
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
                 "tokens": [{"name": "USDC", "szDecimals": 8, "weiDecimals": 8, "index": 0, "tokenId": USDC_ID},
                            {"name": "HYPE", "szDecimals": 2, "weiDecimals": 8, "index": 1, "tokenId": HYPE_ID},
                            {"name": "DUP", "szDecimals": 0, "weiDecimals": 0, "index": 2, "tokenId": "0x" + "d1" * 16},
                            {"name": "DUP", "szDecimals": 0, "weiDecimals": 0, "index": 3, "tokenId": "0x" + "d2" * 16},
                            {"name": "LONG", "szDecimals": 2, "weiDecimals": 10, "index": 4, "tokenId": "0x" + "e4" * 16},
                            # a deployer's look-alike: the venue's USDC is token 0, never found by name
                            {"name": "USDC", "szDecimals": 2, "weiDecimals": 8, "index": 5,
                             "tokenId": "0x" + "f5" * 16},
                            {"name": "A_DEPLOYER_CHOSE_THIS_VERY_LONG_TOKEN_NAME", "szDecimals": 2, "weiDecimals": 8,
                             "index": 6, "tokenId": "0x" + "f6" * 16}]},
                [{"coin": "@107", "markPx": "40", "midPx": "40"}]]
    if kind == "clearinghouseState":
        marks = {"BTC": 99000, "ETH": 2500}
        return {"assetPositions": [{"position": {"coin": c, "szi": s, "positionValue": str(abs(float(s)) * marks[c])}}
                                   for c, s in VENUE["positions"].items()], "withdrawable": VENUE["withdrawable"]}
    if kind == "spotClearinghouseState":
        found = {"balances": [{"coin": c, "token": i, "total": t, "hold": h} for c, i, t, h in VENUE["spot"]]}
        if VENUE["after_margin"] is not None:
            found["tokenToAvailableAfterMaintenance"] = [[0, VENUE["after_margin"]]]
        return found
    if kind == "userAbstraction":
        return VENUE["mode"]
    if kind == "frontendOpenOrders":
        return VENUE["open_orders"]
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
            elif "trigger" in order["t"]:
                legs.append(VENUE.get("waiting", "waitingForTrigger"))  # a TP/SL leg the venue accepted
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
    tpsl = quote(run, kind="tpsl", coin="ETH", tp="2300", sl="2700")
    assert [(leg["leg"], leg["size"]) for leg in tpsl["summary"]["legs"]] == [("tp", "1.5"), ("sl", "1.5")]
    done = ok(submit(run, tpsl["quote"], "reduce"))
    assert done["submitted"] is True and done["statuses"] == [{"status": "waiting for trigger"}] * 2
    VENUE["waiting"] = "waitingForFill"
    again = quote(run, kind="tpsl", coin="ETH", tp="2300", sl="2700")
    assert ok(submit(run, again["quote"], "reduce"))["statuses"] == [{"status": "waiting for fill"}] * 2


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


# --- mandates -----------------------------------------------------------------------------------

TERMS = {"markets": ["BTC"], "max_order_usd": "200", "max_exposure_usd": "1000", "max_leverage": 10, "per_hour": 5,
         "days": 7, "purpose": "Testnet momentum checks"}


def mandate(run, **terms) -> str:
    q = quote(run, kind="mandate", **{**TERMS, **terms})
    return ok(submit(run, q["quote"], "card"))["mandate"]


def buy_btc(run, usd="100"):
    return quote(run, coin="BTC", side="buy", usd=usd, type="market")


def verdict(run, quote_id):
    return ok(run("verify", quote=quote_id)).get("mandate")


def test_a_mandate_is_made_only_on_its_own_card(run):
    q = quote(run, kind="mandate", **TERMS)
    assert q["effect"] == "increase" and exchanged() == []
    card = q["card"]
    assert "MANDATE: orders without a card" in card and "Markets: BTC (perps)" in card
    assert "Per order: up to 200 USDC · held in total: up to 1000 USDC" in card
    assert "Leverage: up to 10x · at most 5 orders an hour" in card and "(7 days)" in card
    assert "Purpose: Testnet momentum checks" in card and "Hyperliquid testnet" in card
    assert verdict(run, q["quote"]) is None  # a mandate never approves another mandate
    for approval in ("reduce", "mandate"):
        mac = ok(run("verify", quote=q["quote"]))["mac"]
        reply = run("submit", quote=q["quote"], approval=approval, mac=mac)
        assert not reply["ok"] and "only on its own approval card" in reply["error"]
    made = ok(submit(run, q["quote"], "card"))
    assert made["made"] is True and made["markets"] == ["BTC"] and exchanged() == []
    listed = ok(run("mandates"))["mandates"]
    assert [(m["mandate"], m["standing"], m["used_this_hour"]) for m in listed] == [(made["mandate"], "active", 0)]


@pytest.mark.parametrize("terms, needle", [
    ({"markets": ["HYPE/USDC"]}, "perps only"),
    ({"markets": ["DOGE"]}, "no perp 'DOGE'"),
    ({"markets": []}, "list of 1 to 20"),
    ({"max_order_usd": "5"}, "at least 10"),
    ({"max_exposure_usd": "100"}, "at least max_order_usd"),
    ({"days": 31}, "from 1 to 30"),
    ({"per_hour": 31}, "from 1 to 30"),
    ({"purpose": ""}, "purpose is required"),
])
def test_a_mandate_s_terms_are_checked(run, terms, needle):
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="mandate", **{**TERMS, **terms})
    assert not reply["ok"] and needle in reply["error"], reply


def test_an_order_inside_the_mandate_runs_on_it_and_is_checked_again(run):
    made = mandate(run)
    q = buy_btc(run)
    assert verdict(run, q["quote"]) == {"id": made, "fits": True, "reason": "inside the mandate"}
    done = ok(submit(run, q["quote"], "mandate"))
    assert done["submitted"] is True and done["under_mandate"] == made
    rows = [json.loads(line) for line in (run.state / "hyperliquid.jsonl").read_text().splitlines()]
    assert rows[-1]["mandate"] == made and rows[-1]["approval"] == "mandate"
    assert ok(run("mandates"))["mandates"][0]["used_this_hour"] == 1


@pytest.mark.parametrize("setup, fields, needle", [
    ({}, {"coin": "BTC", "side": "buy", "usd": "300", "type": "market"}, "above the mandate's 200"),
    ({}, {"coin": "ETH", "side": "buy", "usd": "100", "type": "market"}, "not among the mandate's markets"),
    ({}, {"coin": "HYPE/USDC", "side": "buy", "size": "1", "price": "40"}, "does not cover spot"),
    ({}, {"kind": "margin", "coin": "ETH", "amount": "5", "remove": True}, "does not cover margin"),
    ({"max_leverage": 5}, {"coin": "BTC", "side": "buy", "usd": "100", "type": "market"}, "leverage is above"),
    ({"markets": ["BTC", "ETH"]}, {"coin": "BTC", "side": "buy", "usd": "100", "type": "market"}, "would hold"),
    ({}, {"kind": "leverage", "coin": "BTC", "leverage": 12}, "12x is above"),
])
def test_what_lies_outside_the_mandate_asks_on_its_card(run, setup, fields, needle):
    mandate(run, **setup)
    q = quote(run, **fields)
    found = verdict(run, q["quote"])
    assert found["fits"] is False and needle in found["reason"], found
    reply = submit(run, q["quote"], "mandate")
    assert not reply["ok"] and "needs the approval card" in reply["error"] and exchanged() == []


def test_resting_orders_count_toward_the_mandate_s_exposure(run):
    mandate(run)
    VENUE["open_orders"] = [{"coin": "BTC", "reduceOnly": False, "isTrigger": False, "sz": "0.01", "limitPx": "95000"},
                            {"coin": "BTC", "reduceOnly": True, "isTrigger": False, "sz": "1", "limitPx": "95000"}]
    assert verdict(run, buy_btc(run)["quote"])["fits"] is False  # 950 + 99.99 > 1000; reduce-only is not counted
    VENUE["open_orders"] = VENUE["open_orders"][1:]
    assert verdict(run, buy_btc(run)["quote"])["fits"] is True


def test_a_leverage_change_inside_the_mandate_fits(run):
    made = mandate(run)
    assert verdict(run, quote(run, kind="leverage", coin="BTC", leverage=8)["quote"])["id"] == made


def test_the_mandate_s_hourly_orders_run_out(run):
    mandate(run, per_hour=1)
    ok(submit(run, buy_btc(run)["quote"], "mandate"))
    found = verdict(run, buy_btc(run)["quote"])
    assert found["fits"] is False and "1 orders this hour are used" in found["reason"]


def test_a_revoked_mandate_approves_nothing_at_once(run):
    made = mandate(run)
    q = buy_btc(run)
    assert verdict(run, q["quote"])["fits"] is True
    revoked = ok(run("revoke", mandate=made))
    assert revoked["standing"] == "revoked"
    reply = submit(run, q["quote"], "mandate")  # approved on the mandate before it was revoked
    assert not reply["ok"] and "no mandate is in force" in reply["error"] and exchanged() == []
    assert verdict(run, buy_btc(run)["quote"]) is None
    assert ok(run("mandates"))["mandates"][0]["standing"] == "revoked"
    assert ok(run("revoke", mandate=made))["standing"] == "not in force"
    assert not run("revoke", mandate="m00000000")["ok"]
    (run.state / "hl-mandates.jsonl").unlink()  # the history is not what keeps it revoked
    assert verdict(run, buy_btc(run)["quote"]) is None


def test_a_sell_is_valued_at_the_market_not_its_lower_limit(run):
    mandate(run, max_order_usd="200", max_exposure_usd="200")
    q = quote(run, coin="BTC", side="sell", usd="200", type="market")  # limit 99000, mid 100000
    found = verdict(run, q["quote"])
    assert found["fits"] is False and "worth 202" in found["reason"]


def test_a_modify_frees_only_what_the_order_still_counts_for(run):
    VENUE["positions"] = {}
    mandate(run, markets=["ETH"], max_order_usd="3000", max_exposure_usd="3000")
    VENUE["open_orders"] = [{"coin": "ETH", "oid": 42, "reduceOnly": False, "sz": "1", "limitPx": "2400"}]
    q = quote(run, kind="modify", oid=42, price="2410")
    assert verdict(run, q["quote"])["fits"] is True
    VENUE["open_orders"] = [{"coin": "ETH", "oid": 42, "reduceOnly": False, "sz": "0.5", "limitPx": "2400"}]
    VENUE["positions"] = {"ETH": "0.5"}  # half filled meanwhile: 1250 held, 1200 still resting
    found = verdict(run, q["quote"])
    assert found["fits"] is False and "would hold 3750.05" in found["reason"]
    VENUE["open_orders"] = []
    assert "no longer open" in verdict(run, q["quote"])["reason"]


def test_an_entry_trigger_counts_toward_exposure(run):
    mandate(run)
    VENUE["open_orders"] = [{"coin": "BTC", "oid": 9, "reduceOnly": False, "isTrigger": True, "sz": "0.01",
                             "limitPx": "95000", "triggerPx": "96000"}]
    assert verdict(run, buy_btc(run)["quote"])["fits"] is False  # 960 + 99.99 > 1000


def test_a_leverage_change_needs_the_markets_within_bounds(run):
    mandate(run, markets=["BTC", "ETH"])  # ETH already holds 3750
    found = verdict(run, quote(run, kind="leverage", coin="BTC", leverage=8)["quote"])
    assert found["fits"] is False and "hold 3750" in found["reason"]


def test_the_mandate_ends_when_its_card_said(run):
    q = quote(run, kind="mandate", **TERMS)
    made = ok(submit(run, q["quote"], "card"))["mandate"]
    stored = json.loads((run.state / "hl-mandates" / f"{made}.json").read_text())
    created = json.loads((run.state / "hl-quotes" / f"{q['quote']}.json").read_text())["created"]
    assert stored["expires"] == created + 7 * 86400


def test_a_mandate_quoted_before_another_was_made_is_refused(run):
    first = quote(run, kind="mandate", **TERMS)
    mandate(run)  # made meanwhile: the first card no longer says what it would replace
    reply = submit(run, first["quote"], "card")
    assert not reply["ok"] and "changed since this card was shown" in reply["error"]


def test_an_edited_head_or_a_broken_file_puts_nothing_in_force(run):
    made = mandate(run)
    (head,) = (run.state / "hl-mandates").glob("head-*.json")
    body = json.loads(head.read_text())
    body["mandate"] = "m00000001"
    head.write_text(json.dumps(body))
    assert verdict(run, buy_btc(run)["quote"]) is None
    second = mandate(run)  # the head is rewritten by the next card; the broken one never decided anything
    (run.state / "hl-mandates" / f"{second}.json").write_text("{not json")
    assert verdict(run, buy_btc(run)["quote"]) is None
    standing = {m["mandate"]: m["standing"] for m in ok(run("mandates"))["mandates"]}
    assert standing[second] == "unreadable" and made in standing


def test_a_mandate_in_force_is_listed_and_revocable_without_its_history(run):
    made = mandate(run)
    (run.state / "hl-mandates.jsonl").unlink()
    listed = ok(run("mandates"))["mandates"]
    assert [(m["mandate"], m["standing"]) for m in listed] == [(made, "active")]
    assert ok(run("revoke", mandate=made))["standing"] == "revoked"
    assert verdict(run, buy_btc(run)["quote"]) is None


def test_a_malformed_mandate_file_is_listed_as_unreadable_beside_the_others(run):
    broken = mandate(run)
    path = run.state / "hl-mandates" / f"{broken}.json"
    body = json.loads(path.read_text())
    body["source"] = []
    path.write_text(json.dumps(body))
    good = mandate(run, purpose="Second")
    standing = {m["mandate"]: m["standing"] for m in ok(run("mandates"))["mandates"]}
    assert standing == {broken: "unreadable", good: "active"}


def test_both_mandate_cards_carry_every_bound_within_their_budgets(run):
    mandate(run)
    q = quote(run, kind="mandate", **{**TERMS, "markets": ["BTC", "ETH"]})
    short = json.loads((run.state / "hl-quotes" / f"{q['quote']}.json").read_text())["card_short"]
    for needle in ("testnet MANDATE", "Perps: BTC,ETH", "Order ≤200 · total ≤1000 USDC · ≤10x · 5/h", "Until ",
                   OPS, "Replaces m"):
        assert needle in short, needle
    units = len(short.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").encode("utf-16-le")) // 2
    assert units <= 290


def test_a_new_mandate_replaces_the_old_one(run):
    first = mandate(run)
    q = quote(run, kind="mandate", **{**TERMS, "max_order_usd": "50"})
    assert f"Replaces: {first}" in q["card"]
    second = ok(submit(run, q["quote"], "card"))["mandate"]
    standing = {m["mandate"]: m["standing"] for m in ok(run("mandates"))["mandates"]}
    assert standing == {first: "replaced", second: "active"}
    found = verdict(run, buy_btc(run)["quote"])
    assert found["id"] == second and found["fits"] is False  # 99.99 is above the new 50


def test_an_edited_mandate_is_not_in_force(run):
    made = mandate(run)
    path = run.state / "hl-mandates" / f"{made}.json"
    stored = json.loads(path.read_text())
    stored["max_order_usd"] = "1000000"
    path.write_text(json.dumps(stored))
    assert verdict(run, buy_btc(run)["quote"]) is None
    assert ok(run("mandates"))["mandates"][0]["standing"] == "unreadable"


# --- moving funds -------------------------------------------------------------------------------

def sends(run) -> list[dict]:
    path = run.state / "ledger.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_a_withdrawal_to_the_account_itself_runs_as_own_and_counts_as_a_transfer(run):
    q = quote(run, kind="withdraw", amount="50")
    assert q["effect"] == "own" and q["summary"]["destination"] == USER and q["summary"]["arrives"] == "49"
    assert "Withdraw: 50 USDC from the perp balance to Arbitrum Sepolia" in q["card"]
    assert f"To (own): {USER}" in q["card"] and "Effect: stays in the user's Hermes wallets" in q["card"]
    done = ok(submit(run, q["quote"], "own"))
    assert done["submitted"] is True and "Arbitrum" in done["note"]
    (body,) = exchanged()
    action = body["action"]
    assert action["type"] == "withdraw3" and action["destination"] == USER and action["amount"] == "50"
    assert action["time"] == body["nonce"] and action["hyperliquidChain"] == "Testnet"
    assert action["signatureChainId"] == "0x66eee" and body["expiresAfter"] is None and body["vaultAddress"] is None
    rows = sends(run)
    assert [r["outcome"] for r in rows] == ["unknown", "sent"] and rows[-1]["kind"] == "hyperliquid-withdraw"
    assert rows[-1]["own"] is True and rows[-1]["chain"] == "hyperliquid-testnet"


def test_funds_to_anyone_else_need_the_card(run):
    q = quote(run, kind="withdraw", amount="50", destination=STRANGER)
    assert q["effect"] == "external" and "Effect: funds LEAVE the user's Hermes wallets" in q["card"]
    assert ok(run("verify", quote=q["quote"]))["effect"] == "external"
    for approval in ("own", "mandate", "reduce"):
        mac = ok(run("verify", quote=q["quote"]))["mac"]
        reply = run("submit", quote=q["quote"], approval=approval, mac=mac)
        assert not reply["ok"] and exchanged() == []
    assert ok(submit(run, q["quote"], "card"))["submitted"] is True


def test_sends_go_from_perp_usdc_or_a_named_spot_token(run):
    perp = quote(run, kind="send", amount="20", destination=SPARE)
    assert perp["effect"] == "own" and perp["summary"]["token"] == "USDC (perp)"
    ok(submit(run, perp["quote"], "own"))
    spot = quote(run, kind="send", amount="1.5", destination=STRANGER, token="hype")
    assert spot["effect"] == "external" and f"(spot, {HYPE_ID})" in spot["card"]
    ok(submit(run, spot["quote"], "card"))
    first, second = (body["action"] for body in exchanged())
    assert first["type"] == "usdSend" and first["destination"] == SPARE.lower() and first["amount"] == "20"
    assert second["type"] == "spotSend" and second["token"] == f"HYPE:{HYPE_ID}" and second["amount"] == "1.5"


def test_a_unified_account_sends_from_its_one_balance(run):
    VENUE["mode"] = "unifiedAccount"
    VENUE["withdrawable"] = "0"  # the perp state of a unified account counts nothing
    perp = quote(run, kind="send", amount="20", destination=SPARE)
    assert perp["effect"] == "own" and perp["summary"]["available"] == "25"
    assert f"Send on Hyperliquid: 20 USDC ({USDC_ID})" in perp["card"]
    assert "From the unified balance to their perp balance" in perp["card"]
    short = json.loads((run.state / "hl-quotes" / f"{perp['quote']}.json").read_text())["card_short"]
    assert "Unified → their perp" in short and len(short.replace("&", "&amp;").encode("utf-16-le")) // 2 <= 290
    ok(submit(run, perp["quote"], "own"))
    spot = quote(run, kind="send", amount="1.5", destination=STRANGER, token="hype")
    assert "From the unified balance to their spot balance" in spot["card"]
    ok(submit(run, spot["quote"], "card"))
    first, second = (body["action"] for body in exchanged())
    assert first == {"type": "sendAsset", "destination": SPARE.lower(), "sourceDex": "spot", "destinationDex": "",
                     "token": f"USDC:{USDC_ID}", "amount": "20", "fromSubAccount": "", "nonce": first["nonce"],
                     "signatureChainId": "0x66eee", "hyperliquidChain": "Testnet"}
    assert second["type"] == "sendAsset" and second["destinationDex"] == "spot" and second["token"] == f"HYPE:{HYPE_ID}"
    rows = sends(run)
    assert rows[-1]["kind"] == "hyperliquid-send" and rows[-1]["outcome"] == "sent"
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="send", amount="1", destination=STRANGER,
                token="USDC")  # named, it is ambiguous: only the implicit USDC is token 0
    assert not reply["ok"] and "give it as NAME:tokenId" in reply["error"]


def test_an_external_unified_send_s_compact_card_fits_discord_whole(run):
    VENUE["mode"] = "unifiedAccount"
    long_name = "hermes/HERMES_TRADING_WALLET_WITH_A_LONG_NAME"  # past the 40 the compact card shows
    sources = [SOURCES[0], item(long_name, TEAM_WORDS)]
    q = ok(run("quote", account=f"{long_name}#0", network="mainnet", kind="send", amount="0.123456",
               destination=STRANGER, _sources=sources))
    short = json.loads((run.state / "hl-quotes" / f"{q['quote']}.json").read_text())["card_short"]
    assert q["effect"] == "external" and len(short.replace("&", "&amp;").encode("utf-16-le")) // 2 <= 290
    for part in ("0.123456 USDC", USDC_ID, "Unified → their perp", STRANGER.lower(), "MAINNET"):
        assert part in short, part
    reply = run("quote", account=f"{long_name}#0", network="mainnet", kind="send", amount="1.12345678",
                destination=STRANGER, token="A_DEPLOYER_CHOSE_THIS_VERY_LONG_TOKEN_NAME", _sources=sources)
    assert not reply["ok"] and "would not fit Discord's limit" in reply["error"]  # refused, never shown cut


def test_a_unified_account_withdraws_from_its_one_balance_and_has_nothing_to_transfer(run):
    VENUE["mode"] = "portfolioMargin"
    VENUE["withdrawable"] = "0"
    q = quote(run, kind="withdraw", amount="20")
    assert "Withdraw: 20 USDC from the unified balance to Arbitrum Sepolia" in q["card"]
    assert q["summary"]["available"] == "25"
    VENUE["after_margin"] = "12"  # positions hold the rest
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="withdraw", amount="20")
    assert not reply["ok"] and "can withdraw 12 USDC now (unified balance after margin)" in reply["error"]
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="transfer", amount="5", to_perp=True)
    assert not reply["ok"] and "unified account" in reply["error"] and "nothing to move" in reply["error"]


def test_a_spot_perp_transfer_stays_in_the_account(run):
    q = quote(run, kind="transfer", amount="25", to_perp=True)
    assert q["effect"] == "own" and "Move: 25 USDC spot → perp (same account)" in q["card"]
    ok(submit(run, q["quote"], "own"))
    (body,) = exchanged()
    assert body["action"]["type"] == "usdClassTransfer" and body["action"]["toPerp"] is True
    assert body["action"]["nonce"] == body["nonce"]


@pytest.mark.parametrize("fields, needle", [
    ({"kind": "withdraw", "amount": "500"}, "can withdraw 100 USDC"),
    ({"kind": "withdraw", "amount": "1"}, "1 USDC fee"),
    ({"kind": "withdraw", "amount": "5", "destination": "0x08cfc1B6b2dCF36A1480b99353A354AA8AC56f89"}, "deposit bridge"),
    ({"kind": "withdraw", "amount": "5", "destination": "0x" + "00" * 20}, "zero address"),
    ({"kind": "withdraw", "amount": "5", "destination": "alice.eth"}, "40 hex digits"),
    ({"kind": "withdraw", "amount": "5.0000001"}, "6 decimal places"),
    ({"kind": "send", "amount": "5", "destination": OPS}, "sending account itself"),
    ({"kind": "send", "amount": "5", "destination": STRANGER, "token": "HYPE"}, "can send 2.5 HYPE"),
    ({"kind": "send", "amount": "1", "destination": STRANGER, "token": "DUP"}, "give it as NAME:tokenId"),
    ({"kind": "send", "amount": "1", "destination": STRANGER, "token": "NOPE"}, "no spot token"),
    ({"kind": "send", "amount": "0.5", "destination": STRANGER, "token": f"DUP:0x{'d1' * 16}"}, "0 decimal places"),
    ({"kind": "transfer", "amount": "26", "to_perp": True}, "spot balance can move 25"),
    ({"kind": "transfer", "amount": "5"}, "to_perp is true"),
])
def test_moves_the_venue_would_refuse_or_that_would_lose_funds_are_refused(run, fields, needle):
    reply = run("quote", account=f"{MAIN}#0", network="testnet", **fields)
    assert not reply["ok"] and needle in reply["error"], reply


def test_moves_count_in_the_wallet_s_hourly_transfer_cap(run):
    run.state.mkdir(parents=True, exist_ok=True)
    now = time.time()
    with open(run.state / "ledger.jsonl", "w") as handle:
        for n in range(10):
            handle.write(json.dumps({"time": now, "attempt": f"t{n}", "quote": f"q{n:08x}", "outcome": "sent"}) + "\n")
    q = quote(run, kind="transfer", amount="5", to_perp=False)
    reply = submit(run, q["quote"], "own")
    assert not reply["ok"] and "10 transfers in the last hour" in reply["error"] and exchanged() == []


def test_a_refused_move_moved_nothing_in_either_ledger(run):
    VENUE["exchange"] = "err"
    q = quote(run, kind="withdraw", amount="50")
    reply = submit(run, q["quote"], "own")
    assert not reply["ok"] and "Insufficient margin" in reply["error"]
    assert [r["outcome"] for r in sends(run)] == ["unknown", "rejected"]


def test_an_unanswered_move_stays_unknown(run):
    VENUE["exchange"] = "502"
    q = quote(run, kind="send", amount="20", destination=SPARE)
    done = ok(submit(run, q["quote"], "own"))
    assert done["submitted"] == "unknown" and "never submit it again" in done["note"]
    assert [r["outcome"] for r in sends(run)] == ["unknown"]


def test_a_spot_token_s_balance_is_the_one_its_id_names(run):
    second = quote(run, kind="send", amount="1", destination=STRANGER, token=f"DUP:0x{'d2' * 16}")
    assert second["summary"]["available"] == "5"
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="send", amount="1", destination=STRANGER,
                token=f"DUP:0x{'d1' * 16}")
    assert not reply["ok"] and "can send 0 DUP" in reply["error"]


def test_a_balance_finer_than_a_signed_amount_is_still_shown(run):
    q = quote(run, kind="send", amount="1", destination=STRANGER, token="LONG")
    assert q["summary"]["available"] == "1.0000000001"
    reply = run("quote", account=f"{MAIN}#0", network="testnet", kind="send", amount="0.000000001",
                destination=STRANGER, token="LONG")
    assert not reply["ok"] and "8 decimal places" in reply["error"]


KEY_SOURCE = {"id": "hermes/HERMES_KEY", "project": "hermes", "scope": None, "name": "HERMES_KEY",
              "label": "PRIVATE_KEY", "role": "key", "value": "0x" + "4c" * 32, "memo": None}


def test_a_move_whose_destination_changed_ownership_is_never_shown_or_sent(run):
    with_key = SOURCES + [KEY_SOURCE]
    key_address = ok(run("quote", account="hermes/HERMES_KEY", network="testnet", kind="withdraw", amount="5",
                         _sources=with_key))["summary"]["destination"]
    q = quote(run, kind="send", amount="20", destination=key_address)  # without that key: external
    assert q["effect"] == "external"
    reply = run("verify", quote=q["quote"], _sources=with_key)  # the key became a Hermes wallet: own now
    assert not reply["ok"] and "changed since this quote" in reply["error"]
    mac = ok(run("verify", quote=q["quote"]))["mac"]
    reply = run("submit", quote=q["quote"], approval="card", mac=mac, _sources=with_key)
    assert not reply["ok"] and "changed since this quote" in reply["error"] and exchanged() == []


def test_the_compact_card_of_a_move_fits_discord(run):
    q = quote(run, kind="withdraw", amount="50", destination=STRANGER)
    short = json.loads((run.state / "hl-quotes" / f"{q['quote']}.json").read_text())["card_short"]
    assert STRANGER.lower() in short and "Withdraw: 50 USDC" in short and "Fee:" not in short
    assert len(short.replace("&", "&amp;").encode("utf-16-le")) // 2 <= 290
