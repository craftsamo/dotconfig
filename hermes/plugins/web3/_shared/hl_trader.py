"""The Hyperliquid trader: one operation per process, run by the web3 venv's interpreter.

Part of the wallet's signer (docs/hyperliquid.md "Trading"): it reads the Hermes wallets' keys through
``signer.Secrets`` (only names with HERMES sign) and keeps them in this process; replies carry quotes,
cards, order ids and statuses, scrubbed of every value read.

    {"op": "quote" | "verify" | "submit" | "mandates" | "revoke", "state": "<the wallet's state directory>",
     …the op's arguments}
    → {"ok": true, "data": {…}} or {"ok": false, "error": "…"}

The Hyperliquid account of a wallet account is its EVM address. ``quote`` reads the market and the
account, builds the exact action (orders with their sizes and prices already rounded to what the venue
accepts), decides its ``effect`` and stores it as a single-use quote with an HMAC keyed from its signing
secret, so neither the action nor its card can change between approval and submit:

- ``reduce``: the signed action itself can only lower exposure, as the venue enforces it — a cancel,
  a perp order whose every leg is reduce-only, a modify of a reduce-only order, or adding isolated
  margin.
- ``increase``: anything else — every spot order and every leverage change included.

``submit`` re-checks the MAC, the expiry, the hourly caps and the effect (recomputed from the
authenticated action, never taken from the stored verdict alone), signs with a fresh nonce and an
``expiresAfter`` a minute ahead, recovers the signer from the signature, writes the ledger row as
``unknown`` and only then posts to ``/exchange``. An answer that never came stays ``unknown``: the
orders' client ids are looked up once, and nothing is ever re-sent.

An increase may also go on a mandate (``hl_mandate.py``): ``verify`` says whether the quote fits the
account's mandate as the account stands now, and a submit approved that way is checked again under
the lock, against the account read then. A mandate is itself a quote (kind ``mandate``) that only its
own card makes; ``mandates`` lists them and ``revoke`` ends one at once. ``_api`` and ``_sources`` are
honoured only under the engine's tests (``WEB3_ENGINE_TEST=1``).
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP, Decimal
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets as random
import socket
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hl  # noqa: E402
import hl_mandate  # noqa: E402
import hl_sign  # noqa: E402
import ledger  # noqa: E402
import rpc  # noqa: E402
import signer  # noqa: E402
from rpc import ChainError  # noqa: E402

QUOTES = "hl-quotes"
LEDGER = "hyperliquid.jsonl"
NONCES = "hl-nonce.json"
QUOTE_ID = re.compile(r"^h[0-9a-f]{8}$")
QUOTE_TTL = 900                 # outlives the 600 s approval wait
PRUNE_AFTER = 3600
EXPIRES_AFTER_MS = 60_000       # a signed action the venue has not seen within a minute is void
POST_TIMEOUT = 30
INCREASE_PER_HOUR = 30          # actions that may add exposure, every account together
ALL_PER_HOUR = 200              # every action, reduce included: a loop stops here
KINDS = ("order", "close", "tpsl", "modify", "cancel", "leverage", "margin", "mandate")
SIDES = {"buy": True, "long": True, "sell": False, "short": False}
SLIPPAGE_DEFAULT = Decimal("0.01")
SLIPPAGE_MAX = Decimal("0.05")
TRIGGER_SLIPPAGE = Decimal("0.10")  # the worst price of a TP/SL once it fires as a market order
MIN_NOTIONAL = Decimal("10")        # the venue's minimum order value, in USDC
MARGIN_MODES = ("cross", "isolated")
NOTES = {
    "reduce": "this can only lower exposure: it runs without an approval card",
    "increase": "this can add exposure: the user approves it on a card",
}


def _state(payload: dict) -> Path:
    state = signer._state(payload)
    (state / QUOTES).mkdir(mode=0o700, exist_ok=True)
    return state


def _network(value) -> str:
    if value not in hl.NETWORKS:
        raise ChainError("network must be mainnet or testnet")
    return value


def _ctx(payload: dict, network: str) -> hl.Ctx:
    return hl.Ctx(network, {"_api": payload.get("_api")} if rpc.testing() else {})


def _decimal(payload: dict, key: str, required: bool = False) -> Decimal | None:
    value = payload.get(key)
    if value in (None, ""):
        if required:
            raise ChainError(f"{key} is required")
        return None
    try:
        number = hl_sign.decimal(value, key)
    except hl_sign.SignError as exc:
        raise ChainError(str(exc)) from None
    if number <= 0:
        raise ChainError(f"{key} must be above zero")
    return number


def plain(number: Decimal) -> str:
    return hl_sign.wire(number)


# --- markets ------------------------------------------------------------------------------------

def market(ctx: hl.Ctx, coin) -> dict:
    """What an order on a coin needs: its asset id, decimals, kind and a reference price."""
    if not isinstance(coin, str) or not coin.strip():
        raise ChainError("coin is required: a perp like BTC, a builder perp like xyz:GOLD, or a spot pair like "
                         "HYPE/USDC")
    coin = coin.strip()
    if hl.is_spot(coin):
        name = ctx.spot_coin(coin)
        pair = next(p for p in ctx.spot_pairs() if p["coin"] == name)
        mid = pair["ctx"].get("midPx") or pair["ctx"].get("markPx")
        mark = pair["ctx"].get("markPx") or mid
        # token names are their deployers' choice: the card always names the pair the venue trades too
        shown = signer.one_line(f"{pair['base']}/{pair['quote']}", 32) or "?"
        return {"coin": name, "label": shown if shown == name else f"{shown} ({name})", "spot": True, "dex": "",
                "asset": hl.SPOT_OFFSET + pair["index"], "sz_decimals": pair["sz_decimals"], "max_leverage": None,
                "mid": Decimal(mid) if mid else None, "mark": Decimal(mark) if mark else None,
                "base": pair["base"], "isolated_only": False}
    dex = coin.split(":", 1)[0] if ":" in coin else ""
    found = ctx.api.info({"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})})
    if not (isinstance(found, list) and len(found) == 2):
        raise ChainError(f"{ctx.api.label} returned an unexpected market listing")
    dex_index = ctx.dex_index(dex)
    for index, (meta, state) in enumerate(zip(found[0].get("universe", []), found[1])):
        if str(meta.get("name")).upper() != coin.upper():
            continue
        if meta.get("isDelisted"):
            raise ChainError(f"{coin} is delisted on {ctx.api.label}")
        mid = state.get("midPx") or state.get("markPx")
        mark = state.get("markPx") or mid
        return {"coin": meta["name"], "label": meta["name"], "spot": False, "dex": dex,
                "asset": hl.perp_asset(dex_index, index), "sz_decimals": meta.get("szDecimals", 0),
                "max_leverage": meta.get("maxLeverage"), "mid": Decimal(mid) if mid else None,
                "mark": Decimal(mark) if mark else None,
                "isolated_only": bool(meta.get("onlyIsolated") or meta.get("marginMode"))}
    raise ChainError(f"no perp {coin!r} on {ctx.api.label}; markets lists them")


def round_price(price: Decimal, mkt: dict, rounding=ROUND_HALF_EVEN) -> Decimal:
    """The venue's tick: at most 5 significant figures (integers always pass) and at most 6 (perp) or 8
    (spot) decimals less the size decimals."""
    decimals = (8 if mkt["spot"] else 6) - int(mkt["sz_decimals"])
    figures = Decimal(1).scaleb(price.adjusted() - 4)
    step = max(min(figures, Decimal(1)), Decimal(1).scaleb(-decimals))
    rounded = (price / step).to_integral_value(rounding) * step
    if rounded <= 0:
        raise ChainError("the price rounds to zero at this market's tick")
    return rounded.normalize()


def round_size(size: Decimal, mkt: dict) -> Decimal:
    step = Decimal(1).scaleb(-int(mkt["sz_decimals"]))
    rounded = size.quantize(step, ROUND_DOWN)
    if rounded <= 0:
        raise ChainError(f"the size rounds to zero: {mkt['label']} trades in steps of {plain(step)}")
    return rounded.normalize()


def worst_price(reference: Decimal, is_buy: bool, slippage: Decimal, mkt: dict) -> Decimal:
    """A limit at most ``slippage`` beyond the reference, rounded inside that bound."""
    bound = reference * (1 + slippage) if is_buy else reference * (1 - slippage)
    return round_price(bound, mkt, ROUND_DOWN if is_buy else ROUND_UP)


def _slippage(payload: dict) -> Decimal:
    value = _decimal(payload, "slippage")
    if value is None:
        return SLIPPAGE_DEFAULT
    if value > SLIPPAGE_MAX:
        raise ChainError(f"slippage is at most {SLIPPAGE_MAX} (5%)")
    return value


def position(ctx: hl.Ctx, user: str, mkt: dict) -> Decimal:
    """The signed perp position (positive long, negative short, zero flat)."""
    if mkt["spot"]:
        return Decimal(0)
    found = ctx.api.info({"type": "clearinghouseState", "user": user, **({"dex": mkt["dex"]} if mkt["dex"] else {})})
    for item in (found or {}).get("assetPositions", []):
        p = item.get("position") or {}
        if p.get("coin") == mkt["coin"]:
            return Decimal(str(p.get("szi") or "0"))
    return Decimal(0)


def leverage_now(ctx: hl.Ctx, user: str, mkt: dict) -> dict | None:
    """The account's current leverage on a perp: {"type": cross | isolated, "value": n}."""
    found = ctx.api.info({"type": "activeAssetData", "user": user, "coin": mkt["coin"]})
    lev = (found or {}).get("leverage") if isinstance(found, dict) else None
    if not isinstance(lev, dict) or lev.get("type") not in MARGIN_MODES or not isinstance(lev.get("value"), int):
        return None
    return {"type": lev["type"], "value": lev["value"]}


def order_status(ctx: hl.Ctx, user: str, oid) -> dict | None:
    found = ctx.api.info({"type": "orderStatus", "user": user, "oid": oid})
    if not isinstance(found, dict) or found.get("status") != "order":
        return None
    return found.get("order") or None


def _cloid(quote_id: str, leg: int) -> str:
    return "0x" + hashlib.sha256(f"hermes-hl-cloid\x00{quote_id}\x00{leg}".encode()).digest()[:16].hex()


# --- building actions ---------------------------------------------------------------------------

def _trigger_legs(payload: dict, mkt: dict, is_buy: bool, size: Decimal, reference: Decimal, quote_id: str,
                  first_leg: int) -> list[tuple[dict, dict]]:
    """TP / SL legs closing a position opened by a buy (is_buy) or held long: each a reduce-only market
    trigger on the other side, its worst fill TRIGGER_SLIPPAGE beyond the trigger."""
    legs = []
    for kind in ("tp", "sl"):
        trigger = _decimal(payload, kind)
        if trigger is None:
            continue
        trigger = round_price(trigger, mkt)
        above = kind == "tp" if is_buy else kind == "sl"
        if above and trigger <= reference or not above and trigger >= reference:
            where = "above" if above else "below"
            raise ChainError(f"the {'take-profit' if kind == 'tp' else 'stop-loss'} of a "
                             f"{'long' if is_buy else 'short'} sits {where} the price ({plain(reference)}); "
                             f"{plain(trigger)} would fire at once")
        limit = worst_price(trigger, not is_buy, TRIGGER_SLIPPAGE, mkt)
        cloid = _cloid(quote_id, first_leg + len(legs))
        wire = hl_sign.order_wire(mkt["asset"], not is_buy, limit, size, True, hl_sign.trigger(trigger, True, kind),
                                  cloid)
        legs.append((wire, {"leg": kind, "trigger": plain(trigger), "worst": plain(limit), "size": plain(size),
                            "cloid": cloid}))
    return legs


def build_order(ctx, payload, user, mkt, quote_id) -> dict:
    side = payload.get("side")
    if side not in SIDES:
        raise ChainError("side is buy or sell (long / short)")
    is_buy = SIDES[side]
    reduce_only = bool(payload.get("reduce_only"))
    if mkt["spot"] and reduce_only:
        raise ChainError("spot orders have no reduce-only")
    price = _decimal(payload, "price")
    kind = payload.get("type") or ("limit" if price is not None else "market")
    if kind not in ("limit", "market"):
        raise ChainError("type is limit or market")
    if kind == "market":
        if price is not None:
            raise ChainError("a market order takes no price; it fills up to slippage beyond the mid price")
        if mkt["mid"] is None:
            raise ChainError(f"{mkt['label']} has no mid price now; place a limit order")
        slippage = _slippage(payload)
        limit = worst_price(mkt["mid"], is_buy, slippage, mkt)
        tif = "Ioc"
    else:
        if price is None:
            raise ChainError("a limit order needs price")
        limit = round_price(price, mkt)
        tif = payload.get("tif") or "Gtc"
        slippage = None
    size, usd = _decimal(payload, "size"), _decimal(payload, "usd")
    if (size is None) == (usd is None):
        raise ChainError("give size (in the coin) or usd (the order's value), one of them")
    size = round_size(size if size is not None else usd / limit, mkt)
    notional = size * limit
    if not reduce_only and notional < MIN_NOTIONAL:
        raise ChainError(f"the order's value is {plain(notional.quantize(Decimal('0.01')))} USDC; the venue's "
                         f"minimum is {MIN_NOTIONAL}")
    try:
        main = hl_sign.order_wire(mkt["asset"], is_buy, limit, size, reduce_only, hl_sign.limit(tif),
                                  _cloid(quote_id, 0))
    except hl_sign.SignError as exc:
        raise ChainError(str(exc)) from None
    legs = []
    if payload.get("tp") is not None or payload.get("sl") is not None:
        if mkt["spot"] or reduce_only:
            raise ChainError("tp and sl go with an opening perp order; for a position held, use kind tpsl")
        # triggers fire on the mark price: a market order's legs are checked against it; a limit order's
        # legs start only once it fills, so against its own price
        reference = limit if kind == "limit" else (mkt["mark"] or mkt["mid"])
        legs = _trigger_legs(payload, mkt, is_buy, size, reference, quote_id, 1)
    action = hl_sign.order_action([main, *[w for w, _ in legs]], "normalTpsl" if legs else "na")
    built = {"action": action, "is_buy": is_buy, "size": plain(size), "price": plain(limit), "order_type": kind,
             "tif": tif, "reduce_only": reduce_only, "slippage": plain(slippage) if slippage is not None else None,
             "notional": plain(notional.quantize(Decimal("0.01"))), "legs": [meta for _, meta in legs],
             "cloids": [main["c"], *[meta["cloid"] for _, meta in legs]]}
    if not mkt["spot"]:  # what the card shows the user beside the order: where the account stands now
        built["held"] = plain(position(ctx, user, mkt))
        built["leverage"] = leverage_now(ctx, user, mkt)
    return built


def build_close(ctx, payload, user, mkt, quote_id) -> dict:
    if mkt["spot"]:
        raise ChainError("close is for perp positions; sell spot with kind order")
    held = position(ctx, user, mkt)
    if held == 0:
        raise ChainError(f"the account holds no {mkt['label']} position on {ctx.api.label}")
    size = _decimal(payload, "size") or abs(held)
    if size > abs(held):
        raise ChainError(f"the position is {plain(abs(held))}; close at most that")
    if mkt["mid"] is None:
        raise ChainError(f"{mkt['label']} has no mid price now")
    is_buy = held < 0
    size = round_size(size, mkt)
    limit = worst_price(mkt["mid"], is_buy, _slippage(payload), mkt)
    main = hl_sign.order_wire(mkt["asset"], is_buy, limit, size, True, hl_sign.limit("Ioc"), _cloid(quote_id, 0))
    return {"action": hl_sign.order_action([main]), "is_buy": is_buy, "size": plain(size), "price": plain(limit),
            "order_type": "market", "tif": "Ioc", "reduce_only": True, "slippage": plain(_slippage(payload)),
            "held": plain(held), "notional": plain((size * limit).quantize(Decimal("0.01"))), "legs": [],
            "cloids": [main["c"]]}


def build_tpsl(ctx, payload, user, mkt, quote_id) -> dict:
    if mkt["spot"]:
        raise ChainError("tp and sl are for perp positions")
    held = position(ctx, user, mkt)
    if held == 0:
        raise ChainError(f"the account holds no {mkt['label']} position on {ctx.api.label}")
    if payload.get("tp") is None and payload.get("sl") is None:
        raise ChainError("give tp, sl or both: their trigger prices")
    if mkt["mark"] is None:
        raise ChainError(f"{mkt['label']} has no mark price now")
    legs = _trigger_legs(payload, mkt, held > 0, round_size(abs(held), mkt), mkt["mark"], quote_id, 0)
    return {"action": hl_sign.order_action([w for w, _ in legs], "positionTpsl"), "is_buy": held < 0,
            "size": plain(abs(held)), "held": plain(held), "reduce_only": True, "legs": [m for _, m in legs],
            "cloids": [m["cloid"] for _, m in legs]}


def _oid(payload: dict):
    oid = payload.get("oid")
    if isinstance(oid, str) and oid.isascii() and oid.isdigit():
        return int(oid)
    if isinstance(oid, int) and not isinstance(oid, bool) and oid > 0:
        return oid
    if isinstance(oid, str) and re.match(r"^0x[0-9a-fA-F]{32}$", oid):
        return oid.lower()
    raise ChainError("oid is the order's id from orders (a number) or its 0x cloid")


def _open_order(ctx, user, payload) -> tuple[dict, object]:
    oid = _oid(payload)
    entry = order_status(ctx, user, oid)
    if entry is None:
        raise ChainError(f"no order {oid} for this account on {ctx.api.label}")
    if entry.get("status") != "open":
        raise ChainError(f"order {oid} is {entry.get('status')}, not open")
    return entry.get("order") or {}, oid


def build_cancel(ctx, payload, user, mkt_unused, quote_id) -> dict:
    order, oid = _open_order(ctx, user, payload)
    mkt = market(ctx, order.get("coin"))
    action = hl_sign.cancel_by_cloid_action(mkt["asset"], oid) if isinstance(oid, str) \
        else hl_sign.cancel_action(mkt["asset"], oid)
    return {"action": action, "market": mkt, "order": _brief(order), "reduce_only": True, "cloids": []}


def build_modify(ctx, payload, user, mkt_unused, quote_id) -> dict:
    order, oid = _open_order(ctx, user, payload)
    if order.get("isTrigger") or order.get("orderType") not in (None, "Limit"):
        raise ChainError("only resting limit orders are modified here; cancel a trigger and place it again")
    mkt = market(ctx, order.get("coin"))
    price = _decimal(payload, "price")
    size = _decimal(payload, "size")
    if price is None and size is None:
        raise ChainError("give the new price, the new size or both")
    price = round_price(price, mkt) if price is not None else Decimal(order["limitPx"])
    size = round_size(size, mkt) if size is not None else Decimal(order["sz"])
    reduce_only = bool(order.get("reduceOnly"))
    if not reduce_only and size * price < MIN_NOTIONAL:
        raise ChainError(f"the order's value would be below the venue's minimum of {MIN_NOTIONAL} USDC")
    tif = order.get("tif") or "Gtc"
    is_buy = order.get("side") == "B"
    new = hl_sign.order_wire(mkt["asset"], is_buy, price, size, reduce_only, hl_sign.limit(tif), order.get("cloid"))
    return {"action": hl_sign.modify_action(oid, new), "market": mkt, "order": _brief(order), "is_buy": is_buy,
            "price": plain(price), "size": plain(size), "tif": tif, "reduce_only": reduce_only,
            "cloids": [order["cloid"]] if order.get("cloid") else []}


def build_leverage(ctx, payload, user, mkt, quote_id) -> dict:
    if mkt["spot"]:
        raise ChainError("leverage is for perps")
    leverage = payload.get("leverage")
    if isinstance(leverage, str) and leverage.isascii() and leverage.isdigit():
        leverage = int(leverage)
    if not isinstance(leverage, int) or isinstance(leverage, bool) or not 1 <= leverage <= (mkt["max_leverage"] or 1):
        raise ChainError(f"leverage is a whole number from 1 to {mkt['max_leverage']} on {mkt['label']}")
    now = leverage_now(ctx, user, mkt)
    mode = payload.get("margin_mode") or (now or {}).get("type") or ("isolated" if mkt["isolated_only"] else "cross")
    if mode not in MARGIN_MODES:
        raise ChainError("margin_mode is cross or isolated")
    if mode == "cross" and mkt["isolated_only"]:
        raise ChainError(f"{mkt['label']} trades isolated only")
    return {"action": hl_sign.leverage_action(mkt["asset"], mode == "cross", leverage), "leverage": leverage,
            "mode": mode, "was": now, "reduce_only": False, "cloids": []}


def build_margin(ctx, payload, user, mkt, quote_id) -> dict:
    if mkt["spot"]:
        raise ChainError("isolated margin is for perps")
    amount = _decimal(payload, "amount", required=True)
    if position(ctx, user, mkt) == 0:
        raise ChainError(f"the account holds no {mkt['label']} position to add margin to or take it from")
    lev = leverage_now(ctx, user, mkt)
    if not lev or lev["type"] != "isolated":
        raise ChainError(f"the {mkt['label']} position is not isolated; margin moves only on isolated positions")
    remove = bool(payload.get("remove"))
    try:
        ntli = hl_sign.usd_int(amount)
    except hl_sign.SignError as exc:
        raise ChainError(str(exc)) from None
    return {"action": hl_sign.margin_action(mkt["asset"], -ntli if remove else ntli), "amount": plain(amount),
            "remove": remove, "reduce_only": False, "cloids": []}


def build_mandate(ctx, payload, user, mkt_unused, quote_id) -> dict:
    terms = hl_mandate.build(payload, lambda coin: market(ctx, coin))
    return {"action": None, "market": {"coin": "mandate", "label": "mandate", "spot": False}, **terms, "cloids": []}


BUILDERS = {"order": build_order, "close": build_close, "tpsl": build_tpsl, "modify": build_modify,
            "cancel": build_cancel, "leverage": build_leverage, "margin": build_margin, "mandate": build_mandate}


def _brief(order: dict) -> dict:
    return {"coin": order.get("coin"), "side": "buy" if order.get("side") == "B" else "sell",
            "price": order.get("limitPx"), "size": order.get("sz"), "reduce_only": bool(order.get("reduceOnly")),
            "oid": order.get("oid"), "trigger": order.get("triggerPx") if order.get("isTrigger") else None}


# --- the effect ---------------------------------------------------------------------------------

def effect(quote: dict) -> str:
    """reduce or increase, from the signed action alone, so the venue's own rules hold it to what it
    says: reduce-only orders cannot grow a position, a cancel and added isolated margin cannot add
    exposure. Leverage is always increase: updateLeverage sets a value unconditionally, and another
    client (the venue's own app) may change the leverage between any read here and the venue's
    processing, so "lower than now" cannot be guaranteed. Anything unclear is increase."""
    action = quote["action"]
    if quote["kind"] == "mandate" or not isinstance(action, dict):
        return "increase"  # a mandate signs nothing at the venue, and is only ever made on its own card
    kind = action.get("type")
    spot = quote["market"]["spot"]
    if kind in ("cancel", "cancelByCloid"):
        return "reduce"
    if kind == "order":
        return "reduce" if not spot and all(o.get("r") is True for o in action["orders"]) else "increase"
    if kind == "batchModify":
        return "reduce" if not spot and all(m["order"].get("r") is True for m in action["modifies"]) else "increase"
    if kind == "updateIsolatedMargin":
        return "reduce" if action["ntli"] > 0 else "increase"
    return "increase"


# --- cards --------------------------------------------------------------------------------------

def _net(quote: dict) -> str:
    return "testnet" if quote["network"] == "testnet" else "MAINNET"


def _what(quote: dict) -> list[str]:
    b, m, kind = quote["built"], quote["market"], quote["kind"]
    venue = "spot" if m["spot"] else "perp"
    if kind in ("order", "close"):
        side = ("Buy" if b["is_buy"] else "Sell") + (" (reduce-only)" if b["reduce_only"] else "")
        how = f"market, worst price {b['price']}" if b["order_type"] == "market" else f"limit {b['price']} {b['tif']}"
        lines = [f"{'Close' if kind == 'close' else side}: {b['size']} {m['label']} {venue} · {how}",
                 f"Value: ≈ {b['notional']} USDC"]
        if b.get("held") is not None:
            lev = b.get("leverage")
            lines.append(f"Position now: {b['held']}" + (f" · leverage {lev['value']}x {lev['type']}" if lev else ""))
        for leg in b.get("legs", []):
            lines.append(f"{leg['leg'].upper()}: trigger {leg['trigger']}, worst {leg['worst']}")
        return lines
    if kind == "tpsl":
        return [f"Protect: {m['label']} perp position {b['held']}",
                *[f"{leg['leg'].upper()}: trigger {leg['trigger']}, worst {leg['worst']} (whole position)"
                  for leg in b["legs"]]]
    if kind == "cancel":
        o = b["order"]
        return [f"Cancel: order {o['oid']} · {o['side']} {o['size']} {m['label']} at {o['price']}"]
    if kind == "modify":
        o = b["order"]
        return [f"Modify: order {o['oid']} · {o['side']} {m['label']}",
                f"Price {o['price']} → {b['price']} · size {o['size']} → {b['size']}"]
    if kind == "leverage":
        was = b.get("was") or {}
        before = f"{was.get('value')}x {was.get('type')}" if was else "unknown"
        return [f"Leverage: {m['label']} perp {before} → {b['leverage']}x {b['mode']}"]
    if kind == "margin":
        return [f"{'Remove' if b['remove'] else 'Add'} isolated margin: {b['amount']} USDC on {m['label']}"]
    return [kind]


def card(quote: dict, drop: tuple = ()) -> str:
    expires = datetime.fromtimestamp(quote["expires"]).astimezone().strftime("%H:%M UTC%z")
    effect_line = "Effect: can only lower exposure" if quote["effect"] == "reduce" else "Effect: can add exposure"
    lines = [f"Hyperliquid {_net(quote)}", *_what(quote), effect_line,
             f"Quote: {quote['id']} · expires {expires}", "", "--- Account ---",
             *signer._party_lines(quote["from_party"], quote["from"], drop)]
    return "\n".join(lines)


CONTEXT = ("Value:", "Position now:")  # what the account looks like, not what is signed


def card_short(quote: dict) -> str:
    """The compact card (Discord): everything that is signed — every leg included — and only the
    context dropped; legs share one line to stay inside the budget."""
    what = [line for line in _what(quote) if not line.startswith(CONTEXT)]
    legs = [line for line in what if line.startswith(("TP:", "SL:"))]
    rest = [line for line in what if line not in legs]
    compact = " · ".join(line.replace(": trigger ", " ").replace(", worst ", "→") for line in legs)
    lines = [f"Hyperliquid {_net(quote)}", *rest, *([compact] if compact else []),
             f"Account {signer.one_line(quote['account'], 40)}: {quote['from']}", f"Quote {quote['id']}"]
    return "\n".join(lines)


def cards(quote: dict) -> tuple[str, str]:
    short = card_short(quote)
    for drop in ((), ("memo",)):
        text = card(quote, drop)
        if signer.card_units(text) <= signer.CARD_BUDGET:
            return text, short
    return short, short


# --- quotes -------------------------------------------------------------------------------------

def _mac(secrets_, quote: dict) -> str:
    return secrets_.mac({**quote, "venue": "hyperliquid"})


def prune(state: Path, now: float) -> None:
    for path in (state / QUOTES).iterdir():
        try:
            if path.suffix in (".json", ".tmp") and now - (path.stat().st_mtime + QUOTE_TTL) > PRUNE_AFTER:
                path.unlink()
        except OSError:
            pass


def op_quote(payload: dict) -> dict:
    state = _state(payload)
    network = _network(payload.get("network"))
    kind = payload.get("kind") or "order"
    if kind not in KINDS:
        raise ChainError("kind is one of " + ", ".join(KINDS))
    secrets_ = signer.Secrets(payload)
    secrets_.require_any()
    account = payload.get("account")
    source, index = secrets_.account(account)
    address, _ = secrets_.signer(account, "evm")
    user = address.lower()
    ctx = _ctx(payload, network)
    quote_id = "h" + random.token_hex(4)
    mkt = None if kind in ("cancel", "modify", "mandate") else market(ctx, payload.get("coin"))
    built = BUILDERS[kind](ctx, payload, user, mkt, quote_id)
    mkt = built.pop("market", mkt)
    action = built.pop("action")
    now = time.time()
    if kind == "mandate":
        before = hl_mandate.current(state, secrets_, account, network, now)
        built["replaces"] = before["id"] if before else None
    quote = {"id": quote_id, "created": now, "expires": now + QUOTE_TTL, "account": account, "source": source,
             "index": index, "network": network, "kind": kind, "from": address,
             "market": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in mkt.items()},
             "action": action, "built": built, "from_party": secrets_.party(account)}
    quote["effect"] = effect(quote)
    quote["card"], quote["card_short"] = hl_mandate.cards(quote) if kind == "mandate" else cards(quote)
    quote["mac"] = _mac(secrets_, quote)
    with ledger.locked(state):
        prune(state, now)
        fd = os.open(state / QUOTES / f"{quote_id}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(quote, handle, ensure_ascii=False)
    return {"quote": quote_id, "effect": quote["effect"], "note": NOTES[quote["effect"]], "card": quote["card"],
            "expires_in_seconds": QUOTE_TTL, "network": network, "account": account, "address": address,
            "summary": {"kind": kind, "coin": quote["market"]["coin"], **built}}


def _load(state: Path, quote_id) -> dict:
    if not isinstance(quote_id, str) or not QUOTE_ID.match(quote_id):
        raise ChainError("quote must be an id like h1a2b3c4d from the quote action")
    path = state / QUOTES / f"{quote_id}.json"
    if not path.exists():
        raise ChainError(f"no quote {quote_id}; make one with the quote action")
    return json.loads(path.read_text(encoding="utf-8"))


def _verified(state: Path, quote_id, secrets_, now: float) -> dict:
    quote = _load(state, quote_id)
    if quote.get("id") != quote_id:
        raise ChainError("this quote file holds another quote; it is refused")
    if quote.get("source") not in secrets_.seeds and quote.get("source") not in secrets_.keys:
        raise ChainError("this quote's seed phrase or key is no longer in the Keychain")
    if not hmac.compare_digest(str(quote.get("mac")), _mac(secrets_, {k: v for k, v in quote.items()
                                                                       if k not in ("mac", "consumed")})):
        raise ChainError("this quote was changed after it was made; it is refused")
    if quote.get("consumed") or ledger.attempted(state, quote_id, LEDGER):
        raise ChainError("this quote was already used; make a new one")
    if now > quote["expires"]:
        raise ChainError("this quote expired; make a new one")
    return quote


def op_verify(payload: dict) -> dict:
    """What the hook decides on: the authentic quote, its effect as it reads now, its cards and MAC."""
    state = _state(payload)
    secrets_ = signer.Secrets(payload)
    now = time.time()
    quote = _verified(state, payload.get("quote"), secrets_, now)
    # recomputed from the authenticated action, never taken from the stored verdict alone
    now_effect = "reduce" if quote["effect"] == "reduce" and effect(quote) == "reduce" else "increase"
    result = {"quote": quote["id"], "network": quote["network"], "kind": quote["kind"], "effect": now_effect,
              "card": quote["card"], "card_short": quote["card_short"], "mac": quote["mac"]}
    if now_effect == "increase" and quote["kind"] != "mandate":
        mandate = hl_mandate.current(state, secrets_, quote["account"], quote["network"], now)
        if mandate:
            ctx = _ctx(payload, quote["network"])
            fits, reason = hl_mandate.fits(ctx, state, quote, mandate, now, _reference(ctx, quote))
            result["mandate"] = {"id": mandate["id"], "fits": fits, "reason": reason}
    return result


# --- submitting ---------------------------------------------------------------------------------

class Unknown(Exception):
    """The action may have reached the venue: no answer came back."""


def _nonce(state: Path, address: str) -> int:
    """A fresh nonce for one signer: now in ms, above every nonce it used before (held under the lock)."""
    path = state / NONCES
    try:
        used = json.loads(path.read_text(encoding="utf-8"))
        used = used if isinstance(used, dict) else {}
    except (OSError, ValueError):
        used = {}
    nonce = max(int(time.time() * 1000), int(used.get(address, 0)) + 1)
    used[address] = nonce
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(used), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return nonce


def post(api: hl.Api, body: dict) -> dict:
    """POST to /exchange. A refusal before anything was sent raises ChainError; anything after the
    request left raises Unknown."""
    request = urllib.request.Request(api.base + "/exchange", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": rpc.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            raise Unknown(f"{api.label} answered HTTP {exc.code}") from None
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace").strip()[:200]
        except Exception:
            pass
        raise ChainError(f"{api.label} refused the action (HTTP {exc.code}){': ' + rpc.mask(detail) if detail else ''}") \
            from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (ConnectionRefusedError, socket.gaierror)):
            raise ChainError(f"{api.label} could not be reached; nothing was sent") from None
        raise Unknown(f"{api.label} did not answer ({type(reason).__name__})") from None
    except (TimeoutError, OSError) as exc:
        raise Unknown(f"{api.label} did not answer ({type(exc).__name__})") from None
    try:
        reply = json.loads(raw)
    except ValueError:
        raise Unknown(f"{api.label} answered with something that is not JSON") from None
    if not isinstance(reply, dict):
        raise Unknown(f"{api.label} answered unexpectedly")
    return reply


def _leg(item) -> dict:
    if item == "success":
        return {"status": "done"}
    if isinstance(item, dict) and isinstance(item.get("resting"), dict):
        return {"status": "resting", "oid": item["resting"].get("oid")}
    if isinstance(item, dict) and isinstance(item.get("filled"), dict):
        f = item["filled"]
        return {"status": "filled", "size": f.get("totalSz"), "average_price": f.get("avgPx"), "oid": f.get("oid")}
    if isinstance(item, dict) and "error" in item:
        return {"status": "error", "error": rpc.mask(str(item["error"]))[:200]}
    return {"status": "unclear", "raw": rpc.mask(json.dumps(item, default=str))[:200]}


def statuses(reply: dict) -> tuple[str, list[dict]]:
    """(outcome, per-leg statuses) of an /exchange reply. Only the venue's explicit refusal
    (``status: err``) is a ChainError; a reply that says neither ok nor err is Unknown, and an ok whose
    every leg is an error moved nothing (rejected)."""
    status = reply.get("status")
    if status == "err":
        raise ChainError(f"the venue refused it: {rpc.mask(str(reply.get('response')))[:300]}")
    if status != "ok":
        raise Unknown("the venue's answer said neither ok nor err")
    response = reply.get("response")
    if isinstance(response, dict) and response.get("type") == "default":
        return "sent", [{"status": "done"}]  # leverage and margin: the venue's whole answer is ok
    data = response.get("data") if isinstance(response, dict) else None
    raw = data.get("statuses") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise Unknown("the venue said ok but its per-order statuses could not be read")
    out = [_leg(item) for item in raw]
    outcome = "rejected" if out and all(s["status"] == "error" for s in out) else "sent"
    return outcome, out


def _caps(state: Path, now: float, current: str) -> None:
    try:
        ledger.check_rate(state, now, LEDGER, ALL_PER_HOUR, "Hyperliquid actions")
        if current != "reduce":
            ledger.check_rate(state, now, LEDGER, INCREASE_PER_HOUR, "Hyperliquid actions that can add exposure",
                              where=lambda row: row.get("effect") != "reduce")
    except ledger.CapReached as exc:
        raise ChainError(str(exc)) from None


def op_submit(payload: dict) -> dict:
    state = _state(payload)
    approval = payload.get("approval")
    if approval not in ("reduce", "card", "mandate"):
        raise ChainError("a submit needs the plugin's approval decision")
    with ledger.locked(state):
        secrets_ = signer.Secrets(payload)
        now = time.time()
        quote = _verified(state, payload.get("quote"), secrets_, now)
        if not hmac.compare_digest(str(payload.get("mac") or ""), quote["mac"]):
            raise ChainError("this is not the quote that was approved; nothing was sent")
        if quote["kind"] == "mandate":
            return _make_mandate(state, secrets_, quote, approval, now)
        ctx = _ctx(payload, quote["network"])
        current = "reduce" if quote["effect"] == "reduce" and effect(quote) == "reduce" else "increase"
        if approval == "reduce" and current != "reduce":
            raise ChainError("this action no longer reads as one that only lowers exposure, so it needs the "
                             "approval card; nothing was sent")
        mandate_id = None
        if approval == "mandate":
            mandate = hl_mandate.current(state, secrets_, quote["account"], quote["network"], now)
            if mandate is None:
                raise ChainError("no mandate is in force for this account and network any more, so this needs "
                                 "the approval card; nothing was sent")
            fits, reason = hl_mandate.fits(ctx, state, quote, mandate, now, _reference(ctx, quote))
            if not fits:
                raise ChainError(f"this no longer fits the mandate ({reason}), so it needs the approval card; "
                                 "nothing was sent")
            mandate_id = mandate["id"]
        _caps(state, now, current)
        address, key = secrets_.signer(quote["account"], "evm")
        if address != quote["from"]:
            raise ChainError("this quote's account does not match its secret")
        mainnet = quote["network"] == "mainnet"
        nonce = _nonce(state, address.lower())
        expires = nonce + EXPIRES_AFTER_MS
        signature = hl_sign.sign_l1(key, quote["action"], nonce, mainnet, None, expires)
        if hl_sign.recover_l1(quote["action"], signature, nonce, mainnet, None, expires) != address:
            raise ChainError("the signature does not recover to this account; nothing was sent")
        _consume(state, quote, now)
        row = {"time": now, "attempt": random.token_hex(8), "quote": quote["id"], "account": quote["account"],
               "network": quote["network"], "kind": quote["kind"], "coin": quote["market"]["coin"],
               "effect": current, "approval": approval, "nonce": nonce, "cloids": quote["built"].get("cloids", []),
               **({"mandate": mandate_id} if mandate_id else {}), "outcome": "unknown"}
        ledger.append(state, row, LEDGER)
        # from here the action may have reached the venue: only its explicit refusal is an error, and
        # nothing else may turn the reply into one (the ledger keeps "unknown", which counts)
        try:
            reply = post(ctx.api, hl_sign.envelope(quote["action"], nonce, signature, None, expires))
            outcome, legs = statuses(reply)
        except ChainError as exc:
            try:
                ledger.append(state, {**row, "outcome": "rejected", "error": str(exc)[:300]}, LEDGER)
            except Exception:
                pass
            raise ChainError(f"not submitted: {exc}; make a new quote to try again") from None
        except Exception as exc:  # Unknown, or anything unexpected after the request left
            reason = str(exc) if isinstance(exc, Unknown) else f"the reply could not be read ({type(exc).__name__})"
            return _unknown(ctx, address.lower(), quote, row, reason)
        try:
            ledger.append(state, {**row, "outcome": outcome, "statuses": legs}, LEDGER)
        except Exception:
            pass  # the venue's answer is known; it is reported even if the ledger cannot take it
    result = {"submitted": outcome == "sent", "network": quote["network"], "kind": quote["kind"],
              "coin": quote["market"]["coin"], "statuses": legs, "cloids": row["cloids"],
              **({"under_mandate": mandate_id} if mandate_id else {})}
    if outcome == "rejected":
        result["note"] = "the venue refused every leg: nothing changed; read the errors before a new quote"
    elif any(leg["status"] == "error" for leg in legs):
        result["note"] = "some legs were refused (see statuses); the others stand"
    return result


def _consume(state: Path, quote: dict, now: float) -> None:
    quote["consumed"] = now
    path = state / QUOTES / f"{quote['id']}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _reference(ctx: hl.Ctx, quote: dict) -> Decimal | None:
    """The market's price now, the higher of mid and mark, or None when it cannot be read."""
    try:
        mkt = market(ctx, quote["market"]["coin"])
    except (ChainError, KeyError):
        return None
    prices = [p for p in (mkt.get("mid"), mkt.get("mark")) if p]
    return max(prices) if prices else None


def _make_mandate(state: Path, secrets_, quote: dict, approval: str, now: float) -> dict:
    """An approved mandate quote: stored and made the account's mandate on its network. Only the card
    makes one — never a mandate (a mandate cannot widen itself), never a reduce. Under the lock."""
    if approval != "card":
        raise ChainError("a mandate is made only on its own approval card; nothing was made")
    mandate = hl_mandate.create(state, secrets_, quote, now)  # checks first, writes only when all hold
    _consume(state, quote, now)
    ledger.append(state, {"time": now, "attempt": random.token_hex(8), "quote": quote["id"],
                          "account": quote["account"], "network": quote["network"], "kind": "mandate",
                          "effect": "increase", "approval": approval, "mandate": mandate["id"], "outcome": "made"},
                  LEDGER)
    return {"mandate": mandate["id"], "made": True, "network": quote["network"], "account": quote["account"],
            "replaced": quote["built"].get("replaces"), "markets": mandate["markets"],
            "until": datetime.fromtimestamp(mandate["expires"]).astimezone().isoformat(timespec="minutes"),
            "note": "orders inside these bounds now run without a card, in cron too; revoke_mandate ends it at once"}


def op_mandates(payload: dict) -> dict:
    state = _state(payload)
    network = payload.get("network")
    if network is not None:
        _network(network)
    rows = hl_mandate.listing(state, signer.Secrets(payload), time.time(), payload.get("account"), network)
    return {"mandates": rows, "note": "active ones approve orders inside their bounds without a card; "
                                      "revoke_mandate ends one at once"}


def op_revoke(payload: dict) -> dict:
    state = _state(payload)
    with ledger.locked(state):
        standing = hl_mandate.revoke(state, signer.Secrets(payload), payload.get("mandate"), time.time())
    note = "from now on every order that can add exposure asks on its card again" if standing == "revoked" else \
        "this mandate was not in force; nothing changed"
    return {"mandate": payload.get("mandate"), "standing": standing, "note": note}


def _unknown(ctx: hl.Ctx, user: str, quote: dict, row: dict, reason: str) -> dict:
    note = ("the venue's answer did not come back or could not be read, so the outcome is unknown; never "
            "submit it again — check orders and state first")
    return {"submitted": "unknown", "reason": reason, "found": _look_up(ctx, user, row["cloids"]), "note": note,
            "network": quote["network"], "cloids": row["cloids"]}


def _look_up(ctx: hl.Ctx, user: str, cloids: list[str]) -> list[dict]:
    """One look at each order's client id after an unanswered submit; never a retry."""
    found = []
    for cloid in cloids:
        try:
            entry = order_status(ctx, user, cloid)
        except Exception:
            entry = None
        found.append({"cloid": cloid, "status": entry.get("status") if isinstance(entry, dict) else "not found (yet)"})
    return found


OPS = {"quote": op_quote, "verify": op_verify, "submit": op_submit, "mandates": op_mandates, "revoke": op_revoke}


def run(payload: dict) -> dict:
    op = payload.get("op")
    if op not in OPS:
        raise ChainError(f"unknown op {op!r}")
    return OPS[op](payload)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ChainError("the request must be a JSON object")
        reply = {"ok": True, "data": run(payload)}
    except ChainError as exc:
        reply = {"ok": False, "error": rpc.mask(exc)}
    except Exception as exc:  # an engine bug: say what, never a secret
        reply = {"ok": False, "error": rpc.mask(f"{type(exc).__name__}: {exc}")[:500]}
    sys.stdout.write(rpc.mask(json.dumps(reply, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
