"""The cron gate of the Assistant's Hyperliquid strategies (docs/hyperliquid.md "Strategies").

Run by ``profiles/assistant/scripts/hl-strategy-gate.sh`` with the web3 venv's interpreter, as the
``script`` of a cron job that wakes the Assistant only when there is something to do:

    hl_gate.py <HERMES_HOME>/hl-strategies

For each directory there holding a ``spec.json`` whose strategy is active, it reads the account and
the newest completed candles through the public ``/info`` endpoint, applies the stance in force
(``stance.json``, an advisor's, when valid; else the spec's default) and the rules, and lists the
exact ``hyperliquid`` quotes the rules call for: a close, a missing stop or a trailed stop and the
cancel of the one it replaces (reduce), and on a newly completed bar an entry with its stop
(increase, inside the mandate the spec records, for a variant whose walk-forward out-of-sample the
spec records, while the spec's breaker is set and not tripped); for ``limit_then_market`` rules the
entry is a limit under a client id of the gate's, followed by that id until the venue shows it over:
what filled protected, canceled once its bar closes, and entered at market on a later run when the
venue shows nothing filled; while it may still fill, its market opens nothing new. An intent with
``after`` is sent only once the intent it names was. The breaker follows the strategy's own result from its markets' fills,
funding and unrealized result, read each run from where the last one stopped. It prints one
JSON line; when nothing is to be done or said, that line is ``{"wakeAgent": false}`` and no model
runs. It never signs, never reads a key and never sends anything: the Assistant quotes and submits
through the tool, where the trader and the mandate decide. Its own memory is ``state.json`` beside
the spec: the bar each market was last read on, the side last allowed, the notices already given,
the account's value at the first read (the strategy's starting point), the positions seen on the
last run, so one the venue closed on its own (a stop that fired) is said once and its result
reported, the breaker's index, high, trip and read position, what the strategy's orders cost
against what it expected (the price an entry or a signal's close was listed at, a stop's trigger),
and the limit entries it follows. A failure it cannot place in a strategy exits nonzero, so Hermes
reports it.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

import hl
import hl_strategy as hs
import rpc
from rpc import ChainError

SCHEMA = "hermes-hyperliquid-gate/1"
SPEC, STANCE, STATE = "spec.json", "stance.json", "state.json"
SLIPPAGE = "0.01"
EXPIRY_WARNING_MS = 3 * hs.DAY_MS
REPORTED_KEPT = 100
LEDGER_PAGES = 5          # pages of fills or funding one run reads for the breaker before it calls the window unread
FUNDING_PAGE = 500        # rows userFunding returns per request
SILENT = {"wakeAgent": False}


def _now_ms() -> int:
    if rpc.testing() and os.environ.get("HL_GATE_NOW"):
        return int(os.environ["HL_GATE_NOW"])
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _api_override() -> str | None:
    return os.environ.get("HL_GATE_API") if rpc.testing() else None


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise hs.StrategyError(f"{path.name} is not readable JSON ({type(exc).__name__})") from None


def _write_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _quote(strategy: dict, **fields) -> dict:
    return {"action": "quote", "account": strategy["account"], "network": strategy["network"], **fields}


class Account:
    """What the strategy's account holds now, from public reads: equity, positions, stops, leverage."""

    def __init__(self, ctx: hl.Ctx, address: str, markets: list[str]):
        self.ctx, self.address = ctx, address
        found = ctx.api.info({"type": "clearinghouseState", "user": address})
        if not isinstance(found, dict) or not isinstance(found.get("assetPositions"), list):
            raise ChainError(f"{ctx.api.label} returned an unexpected account state")
        snapshot = found.get("time")  # the venue's own time of this read: the breaker's ledger reads end there
        self.time = snapshot if isinstance(snapshot, int) and not isinstance(snapshot, bool) else None
        self.positions: dict[str, dict] = {}
        for item in found["assetPositions"]:
            p = item.get("position") or {}
            size = hl.num(p.get("szi")) or 0.0
            if p.get("coin") and size:
                self.positions[p["coin"]] = {"side": "long" if size > 0 else "short", "size": abs(size),
                                             "entry": hl.num(p.get("entryPx")),
                                             "value": abs(hl.num(p.get("positionValue")) or 0.0),
                                             "unrealized": hl.num(p.get("unrealizedPnl")) or 0.0}
        self.mode = hl.abstraction(ctx, address)
        equity = hl.num((found.get("marginSummary") or {}).get("accountValue")) or 0.0
        if self.mode in hl.UNIFIED:
            # read just after the account's time: a loss landing between the two reads can only make the
            # breaker's next measure deeper (held entries), never shallower
            spot = ctx.api.info({"type": "spotClearinghouseState", "user": address})
            usdc = [b for b in (spot or {}).get("balances", []) if b.get("coin") == "USDC"]
            equity = (hl.num(usdc[0].get("total")) or 0.0) if usdc else 0.0
            equity += sum(hl.num((i.get("position") or {}).get("unrealizedPnl")) or 0.0
                          for i in found["assetPositions"])
        self.equity = equity
        orders = ctx.api.info({"type": "frontendOpenOrders", "user": address})
        if not isinstance(orders, list):
            raise ChainError(f"{ctx.api.label} returned unexpected open orders")
        self.orders = orders
        self.held = sum(p["value"] for c, p in self.positions.items() if c in markets)
        self.held += sum(hl.num(o.get("sz")) * max(hl.num(o.get("limitPx")) or 0, hl.num(o.get("triggerPx")) or 0)
                         for o in orders if o.get("coin") in markets and not o.get("reduceOnly")
                         and hl.num(o.get("sz")) is not None)

    def stop_orders(self, coin: str) -> list[dict]:
        """The stop losses protecting the position on ``coin`` for all of it: reduce-only stop
        triggers on the closing side, for the whole position or at least its size, tightest first.
        A take profit is not protection. Empty without a position or a stop."""
        position = self.positions.get(coin)
        if not position:
            return []
        closing = "A" if position["side"] == "long" else "B"
        found = []
        for o in self.orders:
            if (o.get("coin") != coin or not o.get("reduceOnly") or not o.get("isTrigger")
                    or "stop" not in str(o.get("orderType", "")).lower() or o.get("side") != closing):
                continue
            if o.get("isPositionTpsl") or (hl.num(o.get("sz")) or 0) >= position["size"] * 0.999:
                found.append(o)
        return sorted(found, key=lambda o: hl.num(o.get("triggerPx")) or 0, reverse=position["side"] == "long")

    def stopped(self, coin: str) -> bool:
        return not self.positions.get(coin) or bool(self.stop_orders(coin))

    def leverage(self, coin: str) -> int | None:
        found = self.ctx.api.info({"type": "activeAssetData", "user": self.address, "coin": coin})
        lev = (found or {}).get("leverage") if isinstance(found, dict) else None
        return lev.get("value") if isinstance(lev, dict) and isinstance(lev.get("value"), int) else None

    def entry_order(self, cloid: str) -> dict | None:
        """A limit entry the gate listed, found by its client id: {"status" (open, filled, canceled, a
        rejection), "size", "left" (what still rests), "side", "price"} as the venue keeps it, or None
        when the venue never had it (its submit was refused or never made)."""
        found = self.ctx.api.info({"type": "orderStatus", "user": self.address, "oid": cloid})
        if isinstance(found, dict) and found.get("status") == "unknownOid":
            return None
        entry = found.get("order") if isinstance(found, dict) and found.get("status") == "order" else None
        order = entry.get("order") if isinstance(entry, dict) else None
        try:  # any other shape is an unread order, never a fault that stops the gate
            size, left, price = (hl.num(order.get(k)) for k in ("origSz", "sz", "limitPx"))
            side = order.get("side")
        except (AttributeError, TypeError, ValueError):
            size = left = price = side = None
        if (not _number(size) or not _number(left) or size < 0 or left < 0
                or not isinstance(entry.get("status") if isinstance(entry, dict) else None, str)):
            raise ChainError(f"{self.ctx.api.label} returned an unexpected order status")
        return {"status": entry["status"], "size": size, "left": left,
                "side": {"B": "long", "A": "short"}.get(side) if isinstance(side, str) else None,
                "price": price if _number(price) and price > 0 else None}


def _entry_cloid(name: str, market: str, bar: int) -> str:
    """The client id of a strategy's limit entry on a bar: any later run finds that order by it."""
    return "0x" + hashlib.sha256(f"hermes-hl-gate-entry\x00{name}\x00{market}\x00{bar}".encode()).digest()[:16].hex()


def _since(ctx: hl.Ctx, kind: str, user: str, start: int, end: int, page_size: int, key) -> list[dict]:
    """Every row of a time-ranged account read (``userFillsByTime``, ``userFunding``) from ``start`` to
    ``end``, paged. A page starts at the last one's millisecond, so rows sharing it are kept once by
    ``key``. A reply of another shape, or more rows than LEDGER_PAGES pages hold, raises: the breaker
    never counts a window it did not read whole."""
    rows: list[dict] = []
    seen: set = set()
    cursor = start
    for _ in range(LEDGER_PAGES):
        page = ctx.api.info({"type": kind, "user": user, "startTime": cursor, "endTime": end})
        if not isinstance(page, list):
            raise ChainError(f"{ctx.api.label} returned an unexpected {kind}")
        for row in page:
            if isinstance(row, dict) and key(row) not in seen:
                seen.add(key(row))
                rows.append(row)
        if len(page) < page_size:
            return rows
        cursor = max(int(r.get("time") or 0) for r in page if isinstance(r, dict))
    raise ChainError(f"more {kind} rows than {LEDGER_PAGES} reads cover")


def _number(value) -> bool:
    """A finite JSON number; never raises, even for an integer too large for a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _memory(raw) -> dict | None:
    """The breaker's memory from state.json when it has every field the gate wrote and reads, else None."""
    if not isinstance(raw, dict) or "tripped" not in raw:
        return None
    if not all(_number(raw.get(k)) for k in ("index", "peak", "unrealized", "equity", "cursor", "since")):
        return None
    tripped = raw["tripped"]
    if tripped is not None and not (isinstance(tripped, dict) and isinstance(tripped.get("at"), int)
                                    and not isinstance(tripped.get("at"), bool) and "drawdown_pct" in tripped
                                    and (tripped["drawdown_pct"] is None or _number(tripped["drawdown_pct"]))):
        return None
    return raw if raw["peak"] > 0 and 0 <= raw["index"] <= raw["peak"] else None


def _breaker(ctx: hl.Ctx, strategy: dict, account: Account, memory: dict | None,
             lost: bool) -> tuple[dict, float, list[dict] | None]:
    """The breaker after this run: what the strategy's markets earned since the last run (their fills'
    realized result less fees, their funding, and the change in their positions' unrealized result),
    applied to its index (hl_strategy.breaker_step), with the fills read (None when the run only set
    the baseline). Fills and funding are read up to the account read's own time, the moment its
    unrealized results and value hold for, so nothing falls between. Without memory the run sets the
    baseline; when the memory was lost (``lost``: state.json or its breaker could not be read) the
    baseline starts tripped, so only the user's reset resumes entries. A read that fails raises, and
    nothing moves."""
    if account.time is None:
        raise ChainError(f"{ctx.api.label} gave no time for the account read")
    markets = set(strategy["markets"])
    unrealized = sum(p["unrealized"] for c, p in account.positions.items() if c in markets)
    brake = strategy["breaker"] or {}
    limit, reset = brake.get("max_drawdown_pct"), brake.get("reset")
    change, equity_before, end, fills = 0.0, 0.0, account.time, None
    if memory is not None:
        user = strategy["address"]
        fills = _since(ctx, "userFillsByTime", user, int(memory["cursor"]), end, hl.FILLS_PAGE,
                       lambda f: (f.get("tid"), f.get("oid"), f.get("time"), f.get("sz"), f.get("px")))
        funding = _since(ctx, "userFunding", user, int(memory["cursor"]), end, FUNDING_PAGE,
                         lambda r: (r.get("time"), r.get("hash"), (r.get("delta") or {}).get("coin")))
        for f in fills:
            if f.get("coin") in markets:
                change += hl.num(f.get("closedPnl")) or 0.0
                if f.get("feeToken") in (None, "USDC"):
                    change -= hl.num(f.get("fee")) or 0.0
        for r in funding:
            delta = r.get("delta") or {}
            if delta.get("coin") in markets:
                change += hl.num(delta.get("usdc")) or 0.0
        change += unrealized - memory["unrealized"]
        equity_before = memory["equity"]
    kept = {k: memory[k] for k in ("index", "peak", "tripped", "since")} if memory is not None else None
    if kept is None and lost:
        kept = {"tripped": {"at": end, "drawdown_pct": None}}
    stepped, drawdown = hs.breaker_step(kept, change, equity_before, limit, reset, end)
    return {**stepped, "cursor": end + 1, "unrealized": unrealized, "equity": account.equity}, drawdown, fills


def _orders(fills: list[dict], markets: set) -> list[dict]:
    """The strategy markets' fills of one read, one row per order: its id, market, side (buy / sell),
    direction as the venue names it, size, average price, USDC fees, the notional that rested on the
    book (maker fills), whether it was a liquidation, and the time of its last fill."""
    rows: dict = {}
    for f in fills:
        sz, px = hl.num(f.get("sz")), hl.num(f.get("px"))
        if f.get("coin") not in markets or not sz or not px or sz <= 0 or px <= 0:
            continue
        row = rows.setdefault(f.get("oid"), {"oid": f.get("oid"), "market": f["coin"],
                                            "side": "buy" if f.get("side") == "B" else "sell",
                                            "dir": str(f.get("dir") or ""), "size": 0.0, "notional": 0.0,
                                            "fees": 0.0, "maker": 0.0, "liquidation": False, "at": 0})
        direction = str(f.get("dir") or "")
        if direction != row["dir"] and ">" not in row["dir"]:  # one order that closed one side and opened the other
            row["dir"] = "Close > Open"
        row["size"] += sz
        row["notional"] += sz * px
        if f.get("feeToken") in (None, "USDC"):
            row["fees"] += hl.num(f.get("fee")) or 0.0
        if not f.get("crossed"):
            row["maker"] += sz * px
        row["liquidation"] = row["liquidation"] or bool(f.get("liquidation"))
        row["at"] = max(row["at"], int(f.get("time") or 0))
    return list(rows.values())


TALLY = ("orders", "notional_usd", "fees_usd", "maker_notional_usd", "reference_notional_usd", "slippage_usd")
KINDS = ("entry", "close", "stop", "other", "liquidation")
SIDE = ("buy", "sell")
STOPS_KEPT = 6            # stop levels remembered per market: the tightest one at or through a fill priced it
EXPECT_KEPT = 6           # listed entries or closes remembered per market and kind while fills go unread
STOP_BAND = 0.001         # a stop's fill sits at or past its trigger, give or take this share
MATCH_KEPT_MS = hs.DAY_MS  # an order priced once keeps its kind and reference for fills that come later
LATEST_MS = 10**14        # times past this (year 5138) are not times the gate wrote


def _ref(value) -> bool:
    return _number(value) and value > 0


def _when(value) -> bool:
    return _number(value) and 0 <= value < LATEST_MS


def _execution_memory(raw) -> dict:
    """The execution memory from state.json, or a fresh one when any part has a shape the gate never
    writes: it only measures, so starting again costs a history, never a decision."""
    if not isinstance(raw, dict) or not _when(raw.get("since", 0)):
        return {}
    expect, stops, matched, totals = (raw.get(k, {}) for k in ("expect", "stops", "matched", "totals"))
    if not all(isinstance(p, dict) for p in (expect, stops, matched, totals)) or (totals and "since" not in raw):
        return {}
    for kinds in expect.values():
        if not (isinstance(kinds, dict) and set(kinds) <= {"entry", "close"} and all(
                isinstance(listed, list) and all(isinstance(e, dict) and e.get("side") in SIDE and _ref(e.get("ref"))
                                                 for e in listed) for listed in kinds.values())):
            return {}
    for levels in stops.values():
        if not (isinstance(levels, list) and all(
                isinstance(s, dict) and s.get("side") in SIDE and _ref(s.get("ref"))
                and (s.get("oid") is None or isinstance(s["oid"], int)) for s in levels)):
            return {}
    for m in matched.values():
        if not (isinstance(m, dict) and m.get("kind") in KINDS and (m.get("ref") is None or _ref(m["ref"]))
                and _when(m.get("at"))):
            return {}
    for kind, tally in totals.items():
        if not (kind in KINDS and isinstance(tally, dict) and all(_number(tally.get(f)) for f in TALLY)):
            return {}
    return raw


def _stop_for(order: dict, px: float, levels: list[dict]) -> float | None:
    """The stop an order closing a position executed, or None. A stop seen on the venue has an order id,
    and only a fill of that id is its execution. A level listed but not yet seen has none: an order
    whose fill sits at or past it on its side (a stop sells at or under its trigger, buys at or over
    it), at most 10% past as the venue fills a triggered stop, is taken for it, the tightest first."""
    same = [s for s in levels if s["side"] == order["side"]]
    for s in same:
        if s.get("oid") is not None and s["oid"] == order["oid"]:
            return s["ref"]
    unseen = [s["ref"] for s in same if s.get("oid") is None]
    if order["side"] == "sell":
        hit = [ref for ref in unseen if ref * 0.9 <= px <= ref * (1 + STOP_BAND)]
        return max(hit) if hit else None
    hit = [ref for ref in unseen if ref * (1 - STOP_BAND) <= px <= ref * 1.1]
    return min(hit) if hit else None


def _expect_copy(memory: dict) -> dict:
    return {m: {k: list(listed) for k, listed in kinds.items()} for m, kinds in (memory.get("expect") or {}).items()}


def _expected(expect: dict, market: str, kind: str, side: str, ref: float) -> None:
    """Add what an order listed now should fill at, the oldest kept first while fills go unread."""
    listed = expect.setdefault(market, {}).setdefault(kind, [])
    listed.append({"side": side, "ref": ref})
    del listed[:-EXPECT_KEPT]


def _take(wanted: dict, kind: str, side: str) -> float | None:
    """The reference of the oldest listed ``kind`` on ``side``, used up, or None."""
    for n, e in enumerate(wanted.get(kind, [])):
        if e["side"] == side:
            return wanted[kind].pop(n)["ref"]
    return None


def _classify(order: dict, px: float, expect: dict, levels: list[dict]) -> tuple[str, float | None]:
    """An order's kind and reference: a stop by its id first, then what the strategy listed for the
    market (an entry for an opening order or a flip, a close for a closing one, the oldest first), then
    a stop listed but not yet seen, by price; anything else is another trade. A match is used up."""
    wanted, side, direction = expect.setdefault(order["market"], {}), order["side"], order["dir"]
    flip, closing = ">" in direction, direction.startswith("Close")
    if order["liquidation"]:
        return "liquidation", None
    if closing and any(s.get("oid") is not None and s["oid"] == order["oid"] for s in levels):
        return "stop", _stop_for(order, px, levels)
    if direction.startswith("Open") or flip:
        ref = _take(wanted, "entry", side)
        if ref is not None:
            if flip:
                _take(wanted, "close", side)  # the one order closed the old side and opened the new one
            return "entry", ref
    if closing or flip:
        ref = _take(wanted, "close", side)
        if ref is not None:
            return "close", ref
    if closing:
        ref = _stop_for(order, px, levels)
        if ref is not None:
            return "stop", ref
    return "other", None


def _execution(memory: dict, fills: list[dict], markets: set, now: int) -> tuple[dict, list[dict]]:
    """What the orders of one read cost against what the strategy expected, and the running totals per
    kind: (memory, this read's orders). References: an entry or a signal's close at the bar's close it
    was listed at (where the backtest fills it, at the next open); a stop at its trigger. Slippage is
    the price paid past the reference, positive when it cost, in basis points of the reference as the
    backtest's ``slippage_bps`` is. An order priced once keeps its kind and reference for its later
    fills and is counted once; one matching nothing listed counts its fees and maker share only."""
    expect = _expect_copy(memory)
    stops, totals = memory.get("stops") or {}, memory.get("totals") or {}
    matched = dict(memory.get("matched") or {})
    measured = []
    for order in _orders(fills, markets):
        px = order["notional"] / order["size"]
        key = str(order["oid"])
        prior = matched.get(key)
        if prior:
            kind, ref = prior["kind"], prior["ref"]
        else:
            kind, ref = _classify(order, px, expect, stops.get(order["market"], []))
        matched[key] = {"kind": kind, "ref": ref, "at": max(order["at"], int(prior["at"]) if prior else 0)}
        cost = None if ref is None else (px - ref) * order["size"] * (1 if order["side"] == "buy" else -1)
        tally = totals.setdefault(kind, dict.fromkeys(TALLY, 0.0))
        tally["orders"] += 0 if prior else 1
        tally["notional_usd"] += order["notional"]
        tally["fees_usd"] += order["fees"]
        tally["maker_notional_usd"] += order["maker"]
        if cost is not None:
            tally["reference_notional_usd"] += ref * order["size"]
            tally["slippage_usd"] += cost
        measured.append({"market": order["market"], "kind": kind, "side": order["side"],
                         "size": hs.sig5(order["size"]), "price": hs.sig5(px),
                         "reference": None if ref is None else hs.sig5(ref),
                         "slippage_bps": None if cost is None else round(cost / (ref * order["size"]) * 10_000, 2),
                         "fee_bps": round(order["fees"] / order["notional"] * 10_000, 2),
                         "maker_pct": round(order["maker"] / order["notional"] * 100, 1)})
    matched = {k: m for k, m in matched.items() if m["at"] >= now - MATCH_KEPT_MS}
    return {**memory, "expect": expect, "totals": totals, "matched": matched,
            "since": memory.get("since", now)}, measured


def _remember_stops(old: dict, seen: dict, listed: dict, held: set, read: bool) -> dict:
    """The stop levels to price the next read's fills by, newest last. After a read: the stops seen in
    force at it and those listed now, and for a market held with no stop seen (one may have fired just
    after the read) the levels it had. After a failed read: everything, since its fills are still to be
    priced."""
    out: dict = {}
    for market in set(old) | set(seen) | set(listed):
        kept = list(old.get(market, [])) if (not read or (market in held and not seen.get(market))) else []
        for level in seen.get(market, []) + listed.get(market, []):
            kept = [s for s in kept if (s["ref"], s.get("oid")) != (level["ref"], level.get("oid"))] + [level]
        if kept:
            out[market] = kept[-STOPS_KEPT:]
    return out


def _costs(totals: dict) -> dict:
    """The running totals as basis points: per kind, orders, slippage on the orders with a reference, fees,
    and the share of notional that rested on the book (maker)."""
    out = {}
    for kind, t in sorted(totals.items()):
        notional, measured = t["notional_usd"], t["reference_notional_usd"]
        out[kind] = {"orders": int(t["orders"]),
                     "slippage_bps": round(t["slippage_usd"] / measured * 10_000, 2) if measured else None,
                     "fee_bps": round(t["fees_usd"] / notional * 10_000, 2) if notional else None,
                     "maker_pct": round(t["maker_notional_usd"] / notional * 100, 1) if notional else None}
    return out


def _entry_limits(raw, name: str) -> dict | None:
    """The limit entries the gate follows, per market, from state.json: {"cloid", "bar" (the signal's),
    "side", "price", "stop", "listed", "cancel"}. Each must carry the client id the gate gives that
    market and bar, so the gate never cancels an order it did not name. One found after the gate lost
    track of it (``cancel``) may lack its side, price and stop. None for a shape the gate never writes."""
    if not isinstance(raw, dict):
        return None
    for market, p in raw.items():
        if not (isinstance(p, dict) and isinstance(p.get("bar"), int) and _when(p["bar"])
                and p.get("cloid") == _entry_cloid(name, market, p["bar"]) and _when(p.get("listed"))
                and all(isinstance(p.get(k, False), bool) for k in ("cancel", "said", "rechecked"))
                and (p.get("side") in hs.SIDES or (p.get("cancel") and p.get("side") is None))
                and all(p.get(k) is None or _ref(p[k]) for k in ("price", "stop"))
                and (p.get("cancel") or (p.get("price") is not None and p.get("stop") is not None))):
            return None
    return raw


def _lookups(raw) -> dict | None:
    """The bars per market whose limit entry the gate still has to look up after losing track, or None."""
    if not isinstance(raw, dict) or not all(isinstance(b, list) and all(isinstance(t, int) and _when(t) for t in b)
                                            for b in raw.values()):
        return None
    return raw


def _guard(strategy: dict, market: str, pending: dict, position: dict | None, stopped: bool, out: dict) -> bool:
    """A stop for the whole position at the limit entry's stop, when a position on its side has none on
    the venue: the venue places the stop sent with a limit only once all of it fills, and cancels it
    with a partly filled one. Whether one was listed."""
    if not (position and pending.get("stop") and position["side"] == pending["side"] and not stopped):
        return False
    verb = "buy" if pending["side"] == "long" else "sell"
    out["intents"].append({"id": f"{strategy['name']}:{market}:{pending['bar']}:protect", "market": market,
                           "effect": "reduce",
                           "why": f"the limit {verb} at {hs.sig5(pending['price'])} filled without the stop the "
                                  "venue places only once all of it fills: protect the position at the entry's stop",
                           "quote": _quote(strategy, kind="tpsl", coin=market, sl=hs.sig5(pending["stop"]))})
    return True


def _limit_entries(strategy: dict, market: str, account: Account, held: str | None, allowed: tuple,
                   waiting: dict, following: dict, unlooked: dict, lookups: dict, now: int, step: int,
                   out: dict) -> dict:
    """One market's limit entries on this run: it looks up the ones the gate lost track of
    (``lookups``), follows the one it knows (``waiting`` → ``following``), and says what that leaves
    the run: {"blocked": no new entry, since a limit may still fill or something about one could not
    be read or settled; "owed": the record of a limit over with nothing filled after its bar closed;
    "guarded": a stop was listed for what filled; "unguarded": a position from a limit with no stop of
    its own, so the rules' stop is due}. ``held`` names why entries are held, ``allowed`` the sides the
    stance in force allows."""
    result = {"blocked": False, "owed": None, "guarded": False, "unguarded": False}
    position, stopped = account.positions.get(market), account.stopped(market)
    for when in lookups.get(market, []):
        cloid = _entry_cloid(strategy["name"], market, when)
        if market in waiting and waiting[market]["cloid"] == cloid:
            continue
        try:
            found = account.entry_order(cloid)
        except ChainError as exc:
            out["problems"].append(f"{market}: a limit entry the gate may have listed could not be looked up ({exc}); "
                                   "the market opens nothing until it can be")
            unlooked.setdefault(market, []).append(when)
            result["blocked"] = True
            continue
        if found is not None and found["status"] == "open":
            if market in waiting:  # one at a time: the other is looked up again next run
                unlooked.setdefault(market, []).append(when)
                result["blocked"] = True
            else:
                waiting[market] = {"cloid": cloid, "bar": when, "side": found["side"], "price": found["price"],
                                   "stop": None, "listed": now, "cancel": True}
    pending = waiting.pop(market, None)
    if pending is None:
        return result
    side = pending["side"]
    result["unguarded"] = pending.get("stop") is None and bool(position) and not stopped
    try:
        order = account.entry_order(pending["cloid"])
    except ChainError as exc:
        out["problems"].append(f"{market}: its limit entry could not be read ({exc}); it is read again next run, "
                               "and the market opens nothing until then")
        following[market] = pending
        result["blocked"] = True
        result["guarded"] = _guard(strategy, market, pending, position, stopped, out)
        return result
    withdrawn = ("it was listed before the gate lost track of it" if pending.get("cancel") else held
                 or (f"the stance in force no longer allows a {side}" if side not in allowed else None))
    keep, outcome, result["guarded"] = _follow_limit(strategy, market, pending, order, position, stopped,
                                                     now >= pending["bar"] + 2 * step, withdrawn, out)
    if keep:
        following[market] = pending
    if outcome == "working" or (outcome == "filled" and keep and not (position and position["side"] == side)):
        result["blocked"] = True  # a fill the account read did not show yet: decide from the next one
    elif outcome == "unfilled":
        result["owed"] = pending
    return result


def _follow_limit(strategy: dict, market: str, pending: dict, order: dict | None, position: dict | None,
                  stopped: bool, ended: bool, withdrawn: str | None, out: dict) -> tuple[bool, str, bool]:
    """One run's look at a limit entry listed earlier (``pending``; ``order``: the venue's state of it,
    None when the venue never had it). What of it filled is protected on every run until the venue
    shows a stop, at the entry's stop: the venue places the stop sent with a limit only once all of it
    fills, and cancels it with a partly filled one. A limit still resting is canceled once its bar has
    closed (``ended``) or it is ``withdrawn`` (the reason entries are held, the stance excludes its
    side, or it was found after the gate lost track of it), on every run until the venue shows it
    over. Returns (keep following it; "working" while it may still fill or its fate is not settled,
    "filled", "unfilled" (its bar closed with nothing filled: a market entry may follow), "dropped";
    whether a stop was listed)."""
    tag = f"{strategy['name']}:{market}:{pending['bar']}"
    side, verb = pending["side"], {"long": "buy", "short": "sell"}.get(pending["side"], "entry")
    price = f" at {hs.sig5(pending['price'])}" if pending.get("price") else ""
    filled = 0.0 if order is None else max(order["size"] - order["left"], 0.0)
    resting = order is not None and order["status"] == "open"
    protected = _guard(strategy, market, pending, position, stopped, out) if resting or filled > 0 else False
    if resting:
        if ended or withdrawn:
            out["intents"].append({"id": f"{tag}:unlimit", "market": market, "effect": "reduce",
                                   "why": f"cancel the limit {verb}{price}: "
                                          + (withdrawn or "its bar has closed"),
                                   "quote": _quote(strategy, kind="cancel", oid=pending["cloid"])})
        return True, "working", protected
    if filled > 0:  # filled whole, or in part and then canceled: the position is the entry
        if not pending.get("said"):
            how = "all of it" if order["status"] == "filled" else f"{filled:g} of {order['size']:g}"
            gone = "" if position and position["side"] == side else \
                "; the position is no longer held (its stop may have fired): read its fills and report the trade"
            out["notes"].append(f"{market}: the limit {verb}{price} listed {hs.iso(pending['listed'])} filled "
                                f"{how}{gone}")
            pending["said"] = True
        # followed on while what filled has no stop on the venue, so the stop is listed again until it shows;
        # a fill this run's account read did not show yet is looked at once more, on the next read
        if position and position["side"] == side:
            return not stopped, "filled", protected
        if not pending.get("rechecked"):
            pending["rechecked"] = True
            return True, "filled", protected
        return False, "filled", protected
    if withdrawn:
        return False, "dropped", protected
    if not ended:  # never placed, or gone unfilled before its bar closed: what the backtest takes at the close
        return True, "working", protected
    return False, "unfilled", protected


def _candles(ctx: hl.Ctx, coin: str, rule_set: dict, interval: str, now: int) -> list[dict]:
    step = hs.INTERVAL_MS[interval]
    count = min(hs.warmup(rule_set) * 2 + 10, hl.CANDLES_MAX)
    rows = hl._candles(ctx, coin, interval, now - count * step, now)
    return hs.bars(rows, interval, now)


def run_strategy(directory: Path, now: int) -> dict:
    """One strategy's part of the report: {"name", "intents", "notes", "problems", …}."""
    state_path = directory / STATE
    try:
        state = _read_json(state_path)
    except hs.StrategyError:
        state = None
    lost_state = not isinstance(state, dict) and state_path.exists()
    if not isinstance(state, dict):
        # none yet is a first run; anything else took the breaker's memory with it, so a marker of a shape
        # the gate never writes is kept until the breaker starts tripped
        state = {"breaker": {"lost": now}} if lost_state else {}
    state.setdefault("bars", {})
    state.setdefault("history", {})
    reported = state.setdefault("reported", [])
    out = {"name": directory.name, "intents": [], "notes": [], "problems": []}
    try:
        strategy = hs.spec(_read_json(directory / SPEC))
    except hs.StrategyError as exc:
        out["problems"].append(f"spec.json not used: {exc}")
        return _finish(out, state, state_path, reported)
    out.update({"name": strategy["name"], "network": strategy["network"], "account": strategy["account"],
                "address": strategy["address"]})  # the reads (state, fills, orders) take the address
    if strategy["name"] != directory.name:
        out["problems"].append(f"spec.json names {strategy['name']!r} but lives in {directory.name!r}; not run")
        return _finish(out, state, state_path, reported)
    if not strategy["active"]:
        out["inactive"] = True
        return out
    mandate = strategy["mandate"]
    entries = mandate is not None and mandate["expires"] > now
    if not entries:
        out["notes"].append("no mandate in force: only closes and stops are proposed; make or renew one to trade")
    elif mandate["expires"] - now < EXPIRY_WARNING_MS:
        out["notes"].append(f"the mandate ends at {hs.iso(mandate['expires'])}")
    try:
        stance_raw = _read_json(directory / STANCE)
    except hs.StrategyError as exc:
        stance_raw = None
        out["notes"].append(f"advisor stance not used: {exc}")
    choices, stance_notes, state["history"] = hs.stance(strategy, stance_raw, now, state["history"])
    out["notes"] += stance_notes
    out["stance"] = {m: {k: v for k, v in c.items()} for m, c in choices.items()}
    untested = sorted({c["variant"] for c in choices.values()
                       if strategy["variants"][c["variant"]]["out_of_sample"] is None})
    if untested:
        out["notes"].append(f"variant {', '.join(untested)} has no walk-forward out_of_sample recorded in the spec: "
                            "its markets open nothing until it is; closes and stops go on")
    # the gate places limit_then_market entries; a plain limit is tested in backtests only
    unplaced = sorted({c["variant"] for c in choices.values()
                       if strategy["variants"][c["variant"]]["rules"].get("entry_order") == "limit"} - set(untested))
    if unplaced:
        out["notes"].append(f"variant {', '.join(unplaced)} enters with a plain limit (entry_order limit), which the "
                            "gate does not place (limit_then_market it does): its markets open nothing; closes and "
                            "stops go on")
    ctx = hl.Ctx(strategy["network"], {"_api": _api_override()})
    limits = dict(strategy["limits"])
    if mandate:
        limits.update(max_order_usd=mandate["max_order_usd"], max_exposure_usd=mandate["max_exposure_usd"])
    try:
        account = Account(ctx, strategy["address"], strategy["markets"])
    except ChainError as exc:
        out["problems"].append(f"the account could not be read: {exc}")
        return _finish(out, state, state_path, reported, transient=True)
    out["equity_usd"] = hs.usd(account.equity)
    if "start_equity_usd" not in state and account.equity > 0:  # the first funded read is the starting point
        state["start_equity_usd"] = out["equity_usd"]
        state["started"] = hs.iso(now)
    if "start_equity_usd" in state:
        out["start_equity_usd"] = state["start_equity_usd"]
    # a position the venue closed on its own (a stop that fired, a liquidation) leaves no intent, so the
    # gate says it once and the Assistant reads the fills and reports the trade's result; one that left
    # through a close the gate listed was reported by the run that sent it
    seen = state.setdefault("positions", {})
    for market in strategy["markets"]:
        was, now_pos = seen.get(market), account.positions.get(market)
        if was and (not now_pos or now_pos["side"] != was["side"]) and not was.get("closing"):
            entry = f" @ {hs.sig5(was['entry'])}" if was.get("entry") else ""
            out["notes"].append(f"{market}: the {was['side']} of {was['size']:g}{entry} seen since "
                                f"{hs.iso(was['since'])} is gone from the account; read its fills from before "
                                "then and report the trade's result")
        if now_pos:
            same = was and was["side"] == now_pos["side"]
            seen[market] = {"side": now_pos["side"], "size": now_pos["size"], "entry": now_pos["entry"],
                            "since": was["since"] if same else now}
        else:
            seen.pop(market, None)
    # the breaker: entries wait while it is missing, unread or tripped; closes and stops never do
    brake, hold_entries, breaker_unread = strategy["breaker"], False, False
    memory = _memory(state.get("breaker"))
    lost = memory is None and "breaker" in state  # unreadable state, or a breaker of a shape the gate never wrote
    was_tripped = memory is not None and memory["tripped"] is not None
    try:  # measuring only: no memory it kept can stop the gate
        execution = _execution_memory(state.get("execution"))
    except Exception:  # noqa: BLE001
        execution = {}
    try:
        state["breaker"], drawdown, fills = _breaker(ctx, strategy, account, memory, lost)
    except ChainError as exc:
        out["problems"].append(f"the strategy's fills or funding could not be read ({exc}); its entries wait for "
                               "the next run")
        breaker_unread = True
    else:
        if fills is not None:  # what the orders since the last run cost; what it expected is used up
            try:
                execution, measured = _execution(execution, fills, set(strategy["markets"]), now)
            except Exception as exc:  # noqa: BLE001
                # it only measures: a fault here starts its history again and never stops the gate
                out["problems"].append(f"execution costs could not be measured ({type(exc).__name__}); "
                                       "they count again from this run")
                execution, measured = {"since": now}, []
            execution["expect"] = {}
            if measured:
                out["fills_measured"] = measured
        latest = state["breaker"]
        tripped = latest["tripped"]
        out["breaker"] = {"drawdown_pct": round(drawdown, 2),
                          "max_drawdown_pct": brake["max_drawdown_pct"] if brake else None,
                          "since": hs.iso(latest["since"]), "tripped": hs.iso(tripped["at"]) if tripped else None}
        if tripped and tripped["drawdown_pct"] is None:
            hold_entries = True
            out["notes"].append(f"breaker holding since {hs.iso(tripped['at'])}: its memory in state.json could "
                                "not be read, so the strategy's drawdown is unknown; entries are held until the "
                                "user resumes it; closes and stops go on")
        elif tripped:
            hold_entries = True
            out["notes"].append(f"breaker tripped at {hs.iso(tripped['at'])} with the strategy "
                                f"{tripped['drawdown_pct']:g}% below its high: entries are held until the user "
                                "resumes it; closes and stops go on")
        elif was_tripped:
            out["notes"].append(f"breaker reset at {hs.iso(latest['since'])}: entries resume, and the drawdown "
                                "counts from there")
    if brake is None:
        hold_entries = True
        out["notes"].append(f"breaker not used: {strategy['breaker_problem']}; entries are held until it is fixed, "
                            "closes and stops go on" if strategy["breaker_problem"] else
                            "no breaker in the spec: entries are held until breaker.max_drawdown_pct is set; "
                            "closes and stops go on")
    held = account.held
    # what the orders this run lists should fill at: kept with what an unread window still owes
    expect = _expect_copy(execution)
    seen_stops: dict = {}  # in force at this read; ``stops`` gathers the levels this run lists
    stops: dict = {}
    for market, position in account.positions.items():
        if market not in strategy["markets"]:
            continue
        closing = "sell" if position["side"] == "long" else "buy"
        for o in reversed(account.stop_orders(market)):  # the tightest last, as the newest
            trigger, oid = hl.num(o.get("triggerPx")), o.get("oid")
            if trigger and trigger > 0:
                seen_stops.setdefault(market, []).append({
                    "side": closing, "ref": trigger, "oid": oid if isinstance(oid, int) and not isinstance(oid, bool)
                    else None})
    # the limit entries the gate follows. Without that memory (state.json unreadable or new, or a record
    # of a shape it never writes) it looks up the ids it would have given the newest two bars' limits,
    # again on each run until every lookup could be read, and cancels any still resting
    step = hs.INTERVAL_MS[strategy["interval"]]
    waiting = _entry_limits(state.get("entry_limits"), strategy["name"])
    lookups = _lookups(state.get("entry_lookups", {}))
    if waiting is None or lookups is None or lost_state:
        newest = now - now % step - step
        lookups = {**(lookups or {}), **{m: [newest, newest - step] for m in strategy["markets"]}}
    waiting = dict(waiting or {})
    following: dict = {}
    unlooked: dict = {}
    for market in strategy["markets"]:
        choice = choices[market]
        rule_set = strategy["variants"][choice["variant"]]["rules"]
        position = account.positions.get(market)
        held_back = not entries or hold_entries or choice["variant"] in untested + unplaced
        allowed = hs.SIDES if choice["direction"] == "both" else () if choice["direction"] == "flat" \
            else (choice["direction"],)
        # a market whose limit may still fill, or whose limit's state is unknown, opens nothing new this run
        known = waiting.get(market)
        try:
            part = _limit_entries(strategy, market, account, "entries are held" if held_back else None, allowed,
                                  waiting, following, unlooked, lookups, now, step, out)
        except Exception as exc:  # noqa: BLE001 - never a fault that stops the gate's closes and stops
            out["problems"].append(f"{market}: its limit entries could not be followed ({type(exc).__name__}); the "
                                   "market opens nothing until they can be")
            if known is not None:
                following[market] = known
            unlooked[market] = list(lookups.get(market, []))
            part = {"blocked": True, "owed": None, "guarded": False, "unguarded": False}
        blocked, owed, guarded, unguarded = part["blocked"], part["owed"], part["guarded"], part["unguarded"]
        if guarded:
            entering_stop = following.get(market) or known
            stops.setdefault(market, []).append({"side": "sell" if entering_stop["side"] == "long" else "buy",
                                                 "ref": entering_stop["stop"], "oid": None})
        if owed and blocked:  # its market entry waits until nothing about the market's limits is unsettled
            following[market], owed = owed, None
        try:
            series = _candles(ctx, market, rule_set, strategy["interval"], now)
            ev = hs.evaluate(series, rule_set, choice, position["side"] if position else None)
        except (ChainError, hs.StrategyError) as exc:
            out["problems"].append(f"{market}: not read this run ({exc})")
            if owed:  # the market entry it owes waits for the rules to be read
                following[market] = owed
            continue
        bar = ev.get("bar")
        fresh = bar is not None and bar > int(state["bars"].get(market, 0))
        retry = blocked  # its bar is read again once the limit is settled
        tag = f"{strategy['name']}:{market}:{bar}"
        closing_id = None
        if position and ev["close"]:
            closing_id = f"{tag}:close"
            out["intents"].append({"id": f"{tag}:close", "market": market, "effect": "reduce",
                                   "why": f"close the {position['side']}: {ev['why']} "
                                          f"(direction {choice['direction']})",
                                   "quote": _quote(strategy, kind="close", coin=market)})
            seen[market]["closing"] = True  # the run that sends it reports the result; the next run stays quiet
            _expected(expect, market, "close", "sell" if position["side"] == "long" else "buy", ev["price"])
        elif position and (fresh or unguarded) and not guarded and not account.stopped(market) and ev.get("atr"):
            sign = -1 if position["side"] == "long" else 1
            price = ev["price"]
            stop = (position["entry"] or price) + sign * rule_set["stop_atr"] * ev["atr"]
            if (position["side"] == "long" and stop >= price) or (position["side"] == "short" and stop <= price):
                stop = price + sign * rule_set["stop_atr"] * ev["atr"]
            stop = hs.trailed(position["side"], stop, price, ev["atr"], rule_set)
            out["intents"].append({"id": f"{tag}:protect", "market": market, "effect": "reduce",
                                   "why": f"the {position['side']} has no stop on the venue",
                                   "quote": _quote(strategy, kind="tpsl", coin=market, sl=hs.sig5(stop))})
            stops.setdefault(market, []).append({"side": "sell" if position["side"] == "long" else "buy",
                                                 "ref": stop, "oid": None})
        elif position and fresh and ev.get("trail") is not None:
            # the trailing stop moved: place the tighter stop first, then cancel every stop looser than
            # it (the one it replaces, and any left from an earlier run whose cancel did not go), so the
            # position is never without one; the cancels are sent only after the new stop is
            in_force = account.stop_orders(market)
            trigger = hl.num(in_force[0].get("triggerPx")) if in_force else None
            tighter = trigger is not None and (ev["trail"] > trigger if position["side"] == "long"
                                               else ev["trail"] < trigger)
            if tighter:
                out["intents"].append({"id": f"{tag}:trail", "market": market, "effect": "reduce",
                                       "why": f"trail the {position['side']}'s stop from {hs.sig5(trigger)} to "
                                              f"{hs.sig5(ev['trail'])} ({rule_set['trail_atr']:g} ATR behind the "
                                              f"close {hs.sig5(ev['price'])})",
                                       "quote": _quote(strategy, kind="tpsl", coin=market, sl=hs.sig5(ev["trail"]))})
                stops.setdefault(market, []).append({"side": "sell" if position["side"] == "long" else "buy",
                                                     "ref": ev["trail"], "oid": None})
                for n, o in enumerate(in_force):
                    out["intents"].append({"id": f"{tag}:untrail{n or ''}", "market": market, "effect": "reduce",
                                           "after": f"{tag}:trail",
                                           "why": f"cancel the stop at {hs.sig5(hl.num(o.get('triggerPx')) or trigger)} "
                                                  "the trailed one replaces",
                                           "quote": _quote(strategy, kind="cancel", oid=o.get("oid"))})
        # the entry: a limit its bar's close found unfilled, once the venue shows it over, enters at market
        # from the newest close if the rules there still hold its side (the backtest's next open); else the
        # rules' own on a new bar, as a limit for limit_then_market. Beside a close, it waits for the close
        opening = None
        if owed:
            opening = hs.market_after_limit(series, rule_set, choice, owed["side"])
            if opening:
                opening.update(how="market", why=f"the limit did not fill by its bar's close, so at market: "
                                                 f"{opening['why']}")
        if opening is None and ev.get("open") and fresh and not blocked:
            opening = {**{k: ev[k] for k in ("open", "price", "stop", "why")},
                       "how": "limit" if rule_set.get("entry_order") == "limit_then_market" else "market"}
            if opening["how"] == "limit":
                opening["limit"] = ev["limit"]
        if opening:
            opening["after"] = closing_id
        if opening:
            if not entries:
                out["notes"].append(f"{market}: the rules open a {opening['open']} ({opening['why']}), but no mandate "
                                    "is in force")
            elif breaker_unread:
                retry = True  # the bar is read again once the breaker can be
            elif choice["variant"] not in untested + unplaced and not hold_entries:  # each said once above
                value, bound = hs.size_usd(account.equity, opening["price"], opening["stop"], rule_set,
                                           choice["size"], held, limits)
                if value is None:
                    out["notes"].append(f"{market}: no {opening['open']} opened: {bound}")
                else:
                    try:
                        leverage = account.leverage(market)
                    except ChainError as exc:
                        out["problems"].append(f"{market}: its leverage could not be read ({exc}); the entry "
                                               "is tried again next run")
                        leverage, retry = -1, True
                    if leverage != -1:
                        if leverage is None or leverage > limits["max_leverage"]:
                            out["intents"].append({
                                "id": f"{tag}:leverage", "market": market, "effect": "increase",
                                "why": f"set {market} to {limits['max_leverage']}x cross before the entry, inside "
                                       "the mandate", "quote": _quote(strategy, kind="leverage", coin=market,
                                                                     leverage=limits["max_leverage"],
                                                                     margin_mode="cross")})
                        entering = "buy" if opening["open"] == "long" else "sell"
                        sized = (f"stop {hs.sig5(opening['stop'])} ({rule_set['stop_atr']:g} ATR), {hs.usd(value)} "
                                 f"USDC, bound by {bound}, size ×{choice['size']:g} ({choice['source']})")
                        if opening["how"] == "limit":
                            # the size the market entry would take, so usd is valued at the limit's price
                            cloid, price = _entry_cloid(strategy["name"], market, bar), opening["limit"]
                            intent = {"why": f"rest a limit {entering} at {hs.sig5(price)} until "
                                             f"{hs.iso(bar + 2 * step)}, then at market if the rules still hold it: "
                                             f"{opening['why']}; {sized}",
                                      "quote": _quote(strategy, kind="order", coin=market, side=entering,
                                                      usd=hs.usd(value * price / opening["price"]), type="limit",
                                                      price=hs.sig5(price), tif="Gtc", sl=hs.sig5(opening["stop"]),
                                                      cloid=cloid)}
                            following[market] = {"cloid": cloid, "bar": bar, "side": opening["open"],
                                                 "price": price, "stop": opening["stop"], "listed": now}
                        else:
                            intent = {"why": f"open a {opening['open']}: {opening['why']}; {sized}",
                                      "quote": _quote(strategy, kind="order", coin=market, side=entering,
                                                      usd=hs.usd(value), type="market", slippage=SLIPPAGE,
                                                      sl=hs.sig5(opening["stop"]))}
                        out["intents"].append({"id": f"{tag}:open", "market": market, "effect": "increase",
                                               **({"after": opening["after"]} if opening["after"] else {}),
                                               **intent})
                        held += value
                        _expected(expect, market, "entry", entering, opening["price"])
                        stops.setdefault(market, []).append({"side": "sell" if entering == "buy" else "buy",
                                                             "ref": opening["stop"], "oid": None})
        if owed and retry:  # the market entry it owes is decided again next run
            following[market] = owed
        if fresh and not retry:  # a bar whose entry could not be decided is read again next run
            state["bars"][market] = bar
    # a market the spec no longer names: its limits, known or still to be looked up, are canceled
    for market in sorted((set(waiting) | set(lookups)) - set(strategy["markets"])):
        known = waiting.get(market)
        try:
            part = _limit_entries(strategy, market, account, "the spec no longer trades this market", hs.SIDES,
                                  waiting, following, unlooked, lookups, now, step, out)
            if part["unguarded"]:  # no rules here to set a stop by: the user is told, once, and decides
                out["problems"].append(f"{market}: a position from a limit entry the gate lost track of has no "
                                       "stop, and the spec no longer trades this market: protect or close it by "
                                       "hand")
        except Exception as exc:  # noqa: BLE001
            out["problems"].append(f"{market}: its limit entries could not be followed ({type(exc).__name__})")
            if known is not None:
                following[market] = known
            unlooked[market] = list(lookups.get(market, []))
    state["entry_limits"] = following
    state["entry_lookups"] = unlooked
    held_markets = {m for m in account.positions if m in strategy["markets"]}
    try:  # measuring only: whatever goes wrong here starts the measure again, never the intents
        state["execution"] = {**execution, "expect": expect,
                              "stops": _remember_stops(execution.get("stops") or {}, seen_stops, stops, held_markets,
                                                       read=not breaker_unread)}
        if execution.get("totals"):
            out["execution"] = {"since": hs.iso(execution["since"]), "costs": _costs(execution["totals"])}
    except Exception as exc:  # noqa: BLE001
        state["execution"] = {"since": now}
        out.pop("execution", None)
        out["problems"].append(f"execution costs could not be kept ({type(exc).__name__}); they count again from "
                               "this run")
    return _finish(out, state, state_path, reported)


def _finish(out: dict, state: dict, path: Path, reported: list, transient: bool = False) -> dict:
    """Mark which notes and problems are new; a notice is said once, a transient read failure each time."""
    fresh = []
    for text in out["notes"] + out["problems"]:
        key = hashlib.sha256(f"{out['name']}|{text}".encode()).hexdigest()[:16]
        if key not in reported:
            fresh.append(text)
            if not (transient and text in out["problems"]):
                reported.append(key)
    state["reported"] = reported[-REPORTED_KEPT:]
    out["new_notices"] = fresh
    try:
        _write_state(path, state)
    except OSError as exc:
        out["problems"].append(f"state.json could not be written ({type(exc).__name__})")
        out["new_notices"].append(out["problems"][-1])
    return out


def run(root: Path, now: int) -> dict:
    strategies = []
    if root.is_dir():
        for directory in sorted(p for p in root.iterdir() if p.is_dir() and (p / SPEC).is_file()):
            strategies.append(run_strategy(directory, now))
    acting = [s for s in strategies if s["intents"] or s.get("new_notices")]
    if not acting:
        return SILENT
    return {"schema": SCHEMA, "time": hs.iso(now), "strategies": acting,
            "instructions": 'skill_view(name="hyperliquid-access:run-strategy")',
            "wakeAgent": True}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: hl_gate.py <HERMES_HOME>/hl-strategies\n")
        return 2
    try:
        report = run(Path(argv[1]), _now_ms())
    except Exception as exc:  # a gate bug: say what, so Hermes reports it, and never act
        sys.stderr.write(rpc.mask(f"hl_gate: {type(exc).__name__}: {exc}")[:500] + "\n")
        return 1
    sys.stdout.write(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
