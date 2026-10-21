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
spec records, while the spec's breaker is set and not tripped). An intent with ``after`` is sent only once
the intent it names was. The breaker follows the strategy's own result from its markets' fills,
funding and unrealized result, read each run from where the last one stopped. It prints one
JSON line; when nothing is to be done or said, that line is ``{"wakeAgent": false}`` and no model
runs. It never signs, never reads a key and never sends anything: the Assistant quotes and submits
through the tool, where the trader and the mandate decide. Its own memory is ``state.json`` beside
the spec: the bar each market was last read on, the side last allowed, the notices already given,
the account's value at the first read (the strategy's starting point), the positions seen on the
last run, so one the venue closed on its own (a stop that fired) is said once and its result
reported, and the breaker's index, high, trip and read position. A failure it cannot place in a strategy exits nonzero, so Hermes reports it.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
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


def _breaker(ctx: hl.Ctx, strategy: dict, account: Account, memory: dict | None, lost: bool) -> tuple[dict, float]:
    """The breaker after this run: what the strategy's markets earned since the last run (their fills'
    realized result less fees, their funding, and the change in their positions' unrealized result),
    applied to its index (hl_strategy.breaker_step). Fills and funding are read up to the account
    read's own time, the moment its unrealized results and value hold for, so nothing falls between.
    Without memory the run sets the baseline; when the memory was lost (``lost``: state.json or its
    breaker could not be read) the baseline starts tripped, so only the user's reset resumes entries.
    A read that fails raises, and nothing moves."""
    if account.time is None:
        raise ChainError(f"{ctx.api.label} gave no time for the account read")
    markets = set(strategy["markets"])
    unrealized = sum(p["unrealized"] for c, p in account.positions.items() if c in markets)
    brake = strategy["breaker"] or {}
    limit, reset = brake.get("max_drawdown_pct"), brake.get("reset")
    change, equity_before, end = 0.0, 0.0, account.time
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
    return {**stepped, "cursor": end + 1, "unrealized": unrealized, "equity": account.equity}, drawdown


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
    if not isinstance(state, dict):
        # none yet is a first run; anything else took the breaker's memory with it, so a marker of a shape
        # the gate never writes is kept until the breaker starts tripped
        state = {"breaker": {"lost": now}} if state_path.exists() else {}
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
    try:
        state["breaker"], drawdown = _breaker(ctx, strategy, account, memory, lost)
    except ChainError as exc:
        out["problems"].append(f"the strategy's fills or funding could not be read ({exc}); its entries wait for "
                               "the next run")
        breaker_unread = True
    else:
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
    for market in strategy["markets"]:
        choice = choices[market]
        rule_set = strategy["variants"][choice["variant"]]["rules"]
        position = account.positions.get(market)
        try:
            series = _candles(ctx, market, rule_set, strategy["interval"], now)
            ev = hs.evaluate(series, rule_set, choice, position["side"] if position else None)
        except (ChainError, hs.StrategyError) as exc:
            out["problems"].append(f"{market}: not read this run ({exc})")
            continue
        bar = ev.get("bar")
        fresh = bar is not None and bar > int(state["bars"].get(market, 0))
        retry = False
        tag = f"{strategy['name']}:{market}:{bar}"
        if position and ev["close"]:
            out["intents"].append({"id": f"{tag}:close", "market": market, "effect": "reduce",
                                   "why": f"close the {position['side']}: {ev['why']} "
                                          f"(direction {choice['direction']})",
                                   "quote": _quote(strategy, kind="close", coin=market)})
            seen[market]["closing"] = True  # the run that sends it reports the result; the next run stays quiet
        elif position and fresh and not account.stopped(market) and ev.get("atr"):
            sign = -1 if position["side"] == "long" else 1
            price = ev["price"]
            stop = (position["entry"] or price) + sign * rule_set["stop_atr"] * ev["atr"]
            if (position["side"] == "long" and stop >= price) or (position["side"] == "short" and stop <= price):
                stop = price + sign * rule_set["stop_atr"] * ev["atr"]
            stop = hs.trailed(position["side"], stop, price, ev["atr"], rule_set)
            out["intents"].append({"id": f"{tag}:protect", "market": market, "effect": "reduce",
                                   "why": f"the {position['side']} has no stop on the venue",
                                   "quote": _quote(strategy, kind="tpsl", coin=market, sl=hs.sig5(stop))})
        elif position and fresh and ev.get("trail") is not None:
            # the trailing stop moved: place the tighter stop first, then cancel every stop looser than
            # it (the one it replaces, and any left from an earlier run whose cancel did not go), so the
            # position is never without one; the cancels are sent only after the new stop is
            held = account.stop_orders(market)
            trigger = hl.num(held[0].get("triggerPx")) if held else None
            tighter = trigger is not None and (ev["trail"] > trigger if position["side"] == "long"
                                               else ev["trail"] < trigger)
            if tighter:
                out["intents"].append({"id": f"{tag}:trail", "market": market, "effect": "reduce",
                                       "why": f"trail the {position['side']}'s stop from {hs.sig5(trigger)} to "
                                              f"{hs.sig5(ev['trail'])} ({rule_set['trail_atr']:g} ATR behind the "
                                              f"close {hs.sig5(ev['price'])})",
                                       "quote": _quote(strategy, kind="tpsl", coin=market, sl=hs.sig5(ev["trail"]))})
                for n, o in enumerate(held):
                    out["intents"].append({"id": f"{tag}:untrail{n or ''}", "market": market, "effect": "reduce",
                                           "after": f"{tag}:trail",
                                           "why": f"cancel the stop at {hs.sig5(hl.num(o.get('triggerPx')) or trigger)} "
                                                  "the trailed one replaces",
                                           "quote": _quote(strategy, kind="cancel", oid=o.get("oid"))})
        if ev.get("open") and fresh:
            if not entries:
                out["notes"].append(f"{market}: the rules open a {ev['open']} ({ev['why']}), but no mandate is in "
                                    "force")
            elif breaker_unread:
                retry = True  # the bar is read again once the breaker can be
            elif choice["variant"] not in untested and not hold_entries:  # each said once above, not per bar
                value, bound = hs.size_usd(account.equity, ev["price"], ev["stop"], rule_set, choice["size"], held,
                                           limits)
                if value is None:
                    out["notes"].append(f"{market}: no {ev['open']} opened: {bound}")
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
                        out["intents"].append({
                            "id": f"{tag}:open", "market": market, "effect": "increase",
                            "why": f"open a {ev['open']}: {ev['why']}; stop {hs.sig5(ev['stop'])} "
                                   f"({rule_set['stop_atr']:g} ATR), {hs.usd(value)} USDC, bound by {bound}, "
                                   f"size ×{choice['size']:g} ({choice['source']})",
                            "quote": _quote(strategy, kind="order", coin=market,
                                            side="buy" if ev["open"] == "long" else "sell", usd=hs.usd(value),
                                            type="market", slippage=SLIPPAGE, sl=hs.sig5(ev["stop"]))})
                        held += value
        if fresh and not retry:  # a bar whose entry could not be decided is read again next run
            state["bars"][market] = bar
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
            "instructions": 'skill_view(name="hyperliquid-access:hyperliquid-strategy"), section "Each run"',
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
