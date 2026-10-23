"""Rule strategies on Hyperliquid perps: one decision shared by the backtest and the cron gate.

Pure Python, stdlib only: no network, no file, no key. ``hl.py``'s ``backtest`` read runs ``backtest``
and ``walk_forward`` over candles it fetched; ``hl_gate.py`` runs ``evaluate`` on the newest
completed candle for a strategy in force. Because both call ``signal`` on the same completed bars,
what was tested is what runs. Contract: docs/hyperliquid.md "Strategies".

- **Rules** are a ``kind`` and its numbers (``breakout``: a Donchian channel; ``ema_cross``: two
  EMAs; ``mean_revert``: the close's distance from an EMA in ATRs, entered against and left once it
  has come back), each with an ATR stop placed with the entry and a risk per trade, and optionally a
  trailing stop (``trail_atr``) that follows each completed close and never loosens, and a regime
  filter (``regime_ema``) that takes longs only above that EMA and shorts only below. ``fingerprint``
  names a rule set exactly (with its interval), so a strategy may only run rules a backtest reported.
- **Markets together** (``simulate_many``, ``walk_forward_many``): the same rules on several markets on
  one account, the cash and the exposure bound shared, so a strategy's breaker is set from the
  drawdown of the account it will hold rather than of one market alone.
- **A Monte Carlo** redraws a backtest's trades in random order, each with the path its equity took
  while it was held, so the spread of drawdowns the same trades could have produced sits beside the
  one their actual order did. Seeded from the request, so the same backtest gives the same spread.
- **A strategy spec** names the account, network, markets, interval, its validated variants, the
  default stance, the bounds an advisor may choose within, and its limits.
- **A stance** is an advisor's choice inside those bounds: per market a direction, a variant and a
  size multiplier, with an expiry and a dated basis. It never widens a limit: the mandate and the
  spec's limits still bound every order.
- **A breaker** holds a strategy's entries once its own result has fallen a set share below its
  high, measured as an index of what its markets earned against the account's value, so deposits,
  withdrawals and other markets move nothing. Only the user's reset, written after it tripped,
  resumes them.
"""

from __future__ import annotations

import bisect
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import re

SPEC_SCHEMA = "hermes-hyperliquid-strategy/1"
STANCE_SCHEMA = "hermes-hyperliquid-stance/1"
BACKTEST_SCHEMA = "hermes-hyperliquid-backtest/1"
KINDS = ("breakout", "ema_cross", "mean_revert")
DIRECTIONS = ("long", "short", "both", "flat")
SIDES = ("long", "short")
MIN_ORDER_USD = 10.0      # the venue refuses smaller orders
HEADROOM = 0.98           # a market order is valued at its worst price, a little above its size in USDC
HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS
INTERVAL_MS = {"15m": 900_000, "30m": 1_800_000, "1h": HOUR_MS, "2h": 2 * HOUR_MS, "4h": 4 * HOUR_MS,
               "8h": 8 * HOUR_MS, "12h": 12 * HOUR_MS, "1d": DAY_MS}
MAX_MARKETS = 8
MAX_VARIANTS = 6
MAX_GRID = 48
MAX_GRID_VALUES = 6
MAX_FOLDS = 6
TRADES_SHOWN = 20
CURVE_POINTS = 60
MC_RUNS = 1000
MC_MIN_TRADES = 20        # fewer trades say too little about their order to redraw them
LIMIT_TOTALS = ("limit_orders", "limit_filled", "limit_crossed", "market_after_limit")  # how limit entries went
BREAKER_PCT = (1.0, 90.0)  # the drawdown a breaker may be set to hold entries at
BASELINE_FUNDING = 0.0000125  # the venue's interest component, 0.01% per 8 hours, paid by longs
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_COIN = re.compile(r"^[A-Za-z0-9]{1,12}$")
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_ACCOUNT = re.compile(r"^[\w.-]+(/[\w.-]+)*/[\w.-]+(#\d{1,3})?$")

# kind -> parameter -> (low, high, whole number)
PARAMS = {
    "breakout": {"entry": (5, 200, True), "exit": (2, 200, True), "atr": (5, 100, True),
                 "stop_atr": (0.5, 10.0, False), "risk_pct": (0.1, 5.0, False)},
    "ema_cross": {"fast": (2, 100, True), "slow": (3, 400, True), "atr": (5, 100, True),
                  "stop_atr": (0.5, 10.0, False), "risk_pct": (0.1, 5.0, False)},
    # a close entry_atr ATRs below the mean EMA enters long (above it, short); exit_atr ATRs past the
    # mean on the other side exits (0: at the mean)
    "mean_revert": {"mean": (5, 400, True), "entry_atr": (0.5, 10.0, False), "exit_atr": (0.0, 10.0, False),
                    "atr": (5, 100, True), "stop_atr": (0.5, 10.0, False), "risk_pct": (0.1, 5.0, False)},
}
# optional for every kind; 0 (or absent) leaves it out of the rule set, so earlier fingerprints hold:
# trail_atr trails the stop; regime_ema allows entries only on the side of that EMA (longs above it);
# limit_atr places a limit entry that many ATRs better than the signal's close
OPTIONAL = {"trail_atr": (0.5, 10.0, False), "regime_ema": (10, 1500, True), "limit_atr": (0.05, 2.0, False)}
# how an entry is sent; market (or absent) leaves it out of the rule set, so earlier fingerprints hold
ENTRY_ORDERS = ("market", "limit", "limit_then_market")
COSTS = {"taker_bps": (0.0, 100.0, 4.5), "slippage_bps": (0.0, 100.0, 5.0), "maker_bps": (-1.0, 100.0, 1.5),
         "limit_through_bps": (0.0, 100.0, 2.0)}
LIMIT_COSTS = ("maker_bps", "limit_through_bps")  # what only a limit entry pays or needs


class StrategyError(ValueError):
    """A spec, stance, rule set or request that cannot be used, with the reason in plain words."""


# --- small helpers ------------------------------------------------------------------------------

def iso(ms) -> str | None:
    if not isinstance(ms, (int, float)):
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value, what: str) -> int:
    """An ISO 8601 time with a zone, or Unix milliseconds, as Unix milliseconds."""
    if isinstance(value, bool):
        raise StrategyError(f"{what} is an ISO time with a zone or Unix milliseconds")
    if isinstance(value, int) and value > 1_000_000_000_000:
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None and parsed.tzinfo is not None:
            return int(parsed.timestamp() * 1000)
    raise StrategyError(f"{what} is an ISO time with a zone (like 2026-01-31T00:00:00Z) or Unix milliseconds")


def sig5(value: float) -> str:
    """A price at the venue's 5 significant figures, written plainly (the trader rounds to the tick)."""
    if value <= 0 or not math.isfinite(value):
        raise StrategyError("a price must be positive")
    digits = max(0, 4 - int(math.floor(math.log10(value))))
    text = f"{round(value, digits):.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def usd(value: float) -> str:
    return f"{math.floor(value * 100) / 100:.2f}"


def value_in(value, low: float, high: float, whole: bool, what: str):
    """A number inside its bounds, or a StrategyError naming ``what``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise StrategyError(f"{what} must be a number")
    if whole and value != int(value):
        raise StrategyError(f"{what} must be a whole number")
    if not low <= value <= high:
        raise StrategyError(f"{what} must be between {low:g} and {high:g}")
    return int(value) if whole else float(value)


def _number(raw: dict, key: str, low: float, high: float, whole: bool, what: str):
    return value_in(raw.get(key), low, high, whole, f"{what}.{key}")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


# --- rules --------------------------------------------------------------------------------------

def rules(raw, what: str = "rules") -> dict:
    """A rule set, validated and normalized: {"kind": …, its parameters}."""
    if not isinstance(raw, dict):
        raise StrategyError(f"{what} is an object with a kind ({', '.join(KINDS)}) and its numbers")
    kind = raw.get("kind")
    if kind not in PARAMS:
        raise StrategyError(f"{what}: kind is one of {', '.join(KINDS)}")
    extra = set(raw) - set(PARAMS[kind]) - set(OPTIONAL) - {"kind", "entry_order"}
    if extra:
        raise StrategyError(f"{what}: {kind} takes {', '.join(PARAMS[kind])} and optionally "
                            f"{', '.join(OPTIONAL)} and entry_order, not {', '.join(sorted(extra))}")
    out = {"kind": kind}
    for key, (low, high, whole) in PARAMS[kind].items():
        out[key] = _number(raw, key, low, high, whole, what)
    for key, (low, high, whole) in OPTIONAL.items():
        if raw.get(key) not in (None, 0, 0.0):
            out[key] = _number(raw, key, low, high, whole, what)
    order = raw.get("entry_order") or "market"
    if order not in ENTRY_ORDERS:
        raise StrategyError(f"{what}: entry_order is one of {', '.join(ENTRY_ORDERS)}")
    if order != "market":
        out["entry_order"] = order
    if "limit_atr" in out and "entry_order" not in out:
        raise StrategyError(f"{what}: limit_atr is how far a limit entry rests from the signal's close; it takes "
                            "entry_order limit or limit_then_market")
    if out.get("limit_atr", 0) >= out["stop_atr"]:
        raise StrategyError(f"{what}: limit_atr must be less than stop_atr, or the limit rests past the stop")
    if kind == "breakout" and out["exit"] > out["entry"]:
        raise StrategyError(f"{what}: exit must not be longer than entry")
    if kind == "ema_cross" and out["slow"] <= out["fast"]:
        raise StrategyError(f"{what}: slow must be longer than fast")
    if kind == "mean_revert" and out["exit_atr"] >= out["entry_atr"]:
        raise StrategyError(f"{what}: exit_atr must be less than entry_atr, or an entry exits at once")
    return out


def fingerprint(rule_set: dict, interval: str) -> str:
    """The exact name of a rule set on an interval: a strategy runs only rules a backtest reported."""
    return hashlib.sha256(canonical({"interval": interval, "rules": rule_set}).encode()).hexdigest()[:16]


def warmup(rule_set: dict) -> int:
    """Completed bars needed before the first signal (an EMA seeded from the first close has settled
    after about three lengths)."""
    regime = rule_set.get("regime_ema", 0) * 3
    if rule_set["kind"] == "breakout":
        return max(rule_set["entry"], rule_set["exit"], rule_set["atr"], regime) + 1
    if rule_set["kind"] == "mean_revert":
        return max(rule_set["mean"] * 3, rule_set["atr"], regime) + 1
    return max(rule_set["slow"] * 3, rule_set["atr"], regime) + 1


def costs(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    extra = set(raw) - set(COSTS) - {"funding"}
    if extra:
        raise StrategyError(f"costs take {', '.join(COSTS)} and funding, not {', '.join(sorted(extra))}")
    out = {}
    for key, (low, high, default) in COSTS.items():
        out[key] = _number(raw, key, low, high, False, "costs") if key in raw else default
    funding = raw.get("funding", "venue")
    if funding not in ("venue", "none"):
        raise StrategyError("costs: funding is venue (the venue's rates, the observed mean where none were read) "
                            "or none")
    out["funding"] = funding
    return out


# --- bars and indicators ------------------------------------------------------------------------

def bars(rows, interval: str, now_ms: int | None = None) -> list[dict]:
    """Completed bars from candle rows (``{"t","o","h","l","c"}`` as the venue sends them, or
    ``[t, o, h, l, c, …]``), oldest first, deduplicated by open time. A bar still forming at
    ``now_ms`` is dropped: a signal is only ever read from a closed bar."""
    step = INTERVAL_MS[interval]
    seen: dict[int, dict] = {}
    for row in rows or []:
        try:
            if isinstance(row, dict):
                t, o, h, l, c = int(row["t"]), float(row["o"]), float(row["h"]), float(row["l"]), float(row["c"])
            else:
                t, o, h, l, c = int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if min(o, h, l, c) <= 0 or h < max(o, c, l) or l > min(o, c):
            continue
        if now_ms is not None and t + step > now_ms:
            continue
        seen[t] = {"t": t, "o": o, "h": h, "l": l, "c": c}
    return [seen[t] for t in sorted(seen)]


def _atr(series: list[dict], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    trs: list[float] = []
    value = None
    for i, b in enumerate(series):
        tr = b["h"] - b["l"] if i == 0 else max(b["h"] - b["l"], abs(b["h"] - series[i - 1]["c"]),
                                                  abs(b["l"] - series[i - 1]["c"]))
        if value is None:
            trs.append(tr)
            if len(trs) == n:
                value = sum(trs) / n
        else:
            value = (value * (n - 1) + tr) / n
        out[i] = value
    return out


def _channel(series: list[dict], n: int, key: str, pick) -> list[float | None]:
    """The highest high (or lowest low) of the ``n`` bars before each bar, excluding it."""
    out: list[float | None] = [None] * len(series)
    window: deque[int] = deque()  # indices of the last n bars whose value may still be the extreme
    for i in range(len(series)):
        while window and window[0] < i - n:
            window.popleft()
        if i >= n:
            out[i] = series[window[0]][key]
        while window and not pick(series[window[-1]][key], series[i][key]):
            window.pop()
        window.append(i)
    return out


def _ema(series: list[dict], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    k = 2 / (n + 1)
    value = None
    for i, b in enumerate(series):
        value = b["c"] if value is None else b["c"] * k + value * (1 - k)
        out[i] = value if i + 1 >= n else None
    return out


def indicators(series: list[dict], rule_set: dict) -> dict:
    ind = {"atr": _atr(series, rule_set["atr"])}
    if rule_set["kind"] == "breakout":
        ind["up_entry"] = _channel(series, rule_set["entry"], "h", lambda kept, new: kept > new)
        ind["down_entry"] = _channel(series, rule_set["entry"], "l", lambda kept, new: kept < new)
        ind["up_exit"] = _channel(series, rule_set["exit"], "h", lambda kept, new: kept > new)
        ind["down_exit"] = _channel(series, rule_set["exit"], "l", lambda kept, new: kept < new)
    elif rule_set["kind"] == "mean_revert":
        ind["mean"] = _ema(series, rule_set["mean"])
    else:
        ind["fast"] = _ema(series, rule_set["fast"])
        ind["slow"] = _ema(series, rule_set["slow"])
    if rule_set.get("regime_ema"):
        ind["regime"] = _ema(series, rule_set["regime_ema"])
    return ind


def signal(series: list[dict], ind: dict, i: int, rule_set: dict) -> dict | None:
    """What the rules say at the close of completed bar ``i``: {"long": enter?, "short": enter?,
    "exit_long", "exit_short", "atr", "close", "why"}; None before the indicators are ready. A
    regime EMA only withholds entries against it (a long below, a short above); exits are the
    rules' own."""
    sig = _signal(series, ind, i, rule_set)
    if sig is None or "regime" not in ind:
        return sig
    regime = ind["regime"][i]
    if regime is None:
        return None
    if sig["close"] < regime:
        sig["long"] = False
    elif sig["close"] > regime:
        sig["short"] = False
    sig["why"] += f"; EMA {rule_set['regime_ema']} regime {sig5(regime)}"
    return sig


def _signal(series: list[dict], ind: dict, i: int, rule_set: dict) -> dict | None:
    if i < warmup(rule_set) - 1 or ind["atr"][i] is None:
        return None
    close = series[i]["c"]
    if rule_set["kind"] == "breakout":
        up, down = ind["up_entry"][i], ind["down_entry"][i]
        up_x, down_x = ind["up_exit"][i], ind["down_exit"][i]
        if None in (up, down, up_x, down_x):
            return None
        return {"long": close > up, "short": close < down, "exit_long": close < down_x, "exit_short": close > up_x,
                "atr": ind["atr"][i], "close": close,
                "why": (f"close {sig5(close)}; {rule_set['entry']}-bar channel {sig5(down)}–{sig5(up)}, "
                        f"{rule_set['exit']}-bar exit channel {sig5(down_x)}–{sig5(up_x)}")}
    if rule_set["kind"] == "mean_revert":
        mean, atr = ind["mean"][i], ind["atr"][i]
        if mean is None:
            return None
        # ATRs above the mean, negative below it; a dead market (no ATR) still exits, on the side of the
        # mean the close sits, and enters nothing, having no stop distance
        if atr > 0:
            away = (close - mean) / atr
        else:
            away = math.copysign(math.inf, close - mean) if close != mean else 0.0
        enter, leave = rule_set["entry_atr"], rule_set["exit_atr"]
        where = f"{away:+.2f} ATR away" if math.isfinite(away) else "no ATR to measure by"
        return {"long": atr > 0 and away <= -enter, "short": atr > 0 and away >= enter,
                "exit_long": away >= leave, "exit_short": away <= -leave, "atr": atr, "close": close,
                "why": (f"close {sig5(close)}; EMA {rule_set['mean']} {sig5(mean)}, {where} "
                        f"(enter at {enter:g}, exit at {leave:g} past the mean)")}
    fast, slow = ind["fast"][i], ind["slow"][i]
    fast_0, slow_0 = ind["fast"][i - 1], ind["slow"][i - 1]
    if None in (fast, slow, fast_0, slow_0):
        return None
    up, was_up = fast > slow, fast_0 > slow_0
    return {"long": up and not was_up, "short": not up and was_up, "exit_long": not up, "exit_short": up,
            "atr": ind["atr"][i], "close": close,
            "why": f"close {sig5(close)}; EMA {rule_set['fast']} {sig5(fast)} vs EMA {rule_set['slow']} {sig5(slow)}"}


def stop_price(side: str, close: float, atr: float, rule_set: dict) -> float:
    distance = rule_set["stop_atr"] * atr
    return close - distance if side == "long" else close + distance


def trailed(side: str, stop: float, close: float, atr: float | None, rule_set: dict) -> float:
    """The stop after a completed bar: ``trail_atr`` ATRs behind its close when that is tighter than
    the stop held, else the stop held. Without ``trail_atr`` (or an ATR) the stop stays."""
    trail = rule_set.get("trail_atr")
    if not trail or not atr:
        return stop
    level = close - trail * atr if side == "long" else close + trail * atr
    return max(stop, level) if side == "long" else min(stop, level)


def decide(sig: dict | None, holding: str | None, direction: str) -> tuple[bool, str | None]:
    """(close what is held?, side to open or None) from a signal, the side held and the direction
    allowed. A direction that excludes the side held closes it; an opposite entry closes first."""
    if sig is None:
        return False, None
    allowed = SIDES if direction == "both" else () if direction == "flat" else (direction,)
    close = holding is not None and (holding not in allowed or sig[f"exit_{holding}"]
                                     or sig["short" if holding == "long" else "long"])
    after = None if close else holding
    if after is not None:
        return close, None
    for side in SIDES:
        if side in allowed and sig[side]:
            return close, side
    return close, None


def size_usd(equity: float, price: float, stop: float, rule_set: dict, multiplier: float, held: float,
             limits: dict) -> tuple[float | None, str]:
    """The entry's value in USDC from the risk per trade, capped by every limit, or None and why not.
    ``limits``: exposure_pct and max_leverage of equity; optional max_order_usd / max_exposure_usd
    (a mandate's, absolute)."""
    distance = abs(price - stop)
    if equity <= 0 or distance <= 0:
        return None, "no equity or no stop distance"
    wanted = equity * rule_set["risk_pct"] / 100 * multiplier / distance * price
    caps = {"risk": wanted, "exposure_pct": equity * limits["exposure_pct"] / 100 - held,
            "max_leverage": equity * limits["max_leverage"] - held}
    if limits.get("max_order_usd") is not None:
        caps["mandate order"] = float(limits["max_order_usd"]) * HEADROOM
    if limits.get("max_exposure_usd") is not None:
        caps["mandate exposure"] = (float(limits["max_exposure_usd"]) - held) * HEADROOM
    bound = min(caps, key=caps.get)
    value = caps[bound]
    if value < MIN_ORDER_USD:
        return None, f"{usd(max(value, 0))} USDC after the {bound} limit, below the venue's {MIN_ORDER_USD:g}"
    return value, bound


# --- the backtest -------------------------------------------------------------------------------

def funding_by_bar(series: list[dict], interval: str, funding: dict | None, mean: float,
                   mode: str) -> list[tuple[float, int]]:
    """Per bar, (summed hourly rate, hours assumed): the venue's rate where read (``funding`` maps the
    hour's start in ms to its rate), else ``mean``. Positive rates are paid by longs."""
    step = INTERVAL_MS[interval]
    out = []
    for b in series:
        if mode == "none":
            out.append((0.0, 0))
            continue
        total, assumed = 0.0, 0
        hour = b["t"] + (-b["t"]) % HOUR_MS
        while hour < b["t"] + step:
            rate = funding.get(hour) if funding else None
            if rate is None:
                total, assumed = total + mean, assumed + 1
            else:
                total += rate
            hour += HOUR_MS
        out.append((total, assumed))
    return out


def _stance_at(timeline: list[dict], t: int, default: dict) -> dict:
    for item in timeline:
        if item["from"] <= t < item["to"]:
            return item
    return default


def timeline(raw) -> list[dict]:
    """A backtest's stance over time: [{"from", "to", "direction", "size"}], each a window."""
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > 500:
        raise StrategyError("stance is a list of at most 500 windows {from, to, direction, size}")
    out = []
    for n, item in enumerate(raw):
        if not isinstance(item, dict):
            raise StrategyError(f"stance[{n}] is an object")
        start, end = parse_time(item.get("from"), f"stance[{n}].from"), parse_time(item.get("to"), f"stance[{n}].to")
        if end <= start:
            raise StrategyError(f"stance[{n}] ends before it starts")
        direction = item.get("direction", "both")
        if direction not in DIRECTIONS:
            raise StrategyError(f"stance[{n}].direction is one of {', '.join(DIRECTIONS)}")
        size = _number({"size": item.get("size", 1.0)}, "size", 0.0, 2.0, False, f"stance[{n}]")
        out.append({"from": start, "to": end, "direction": direction, "size": size})
    return sorted(out, key=lambda w: w["from"])


def limit_price(side: str, sig: dict, rule_set: dict) -> float:
    """A limit entry's price: ``limit_atr`` ATRs better than the signal's close, at the close without it."""
    offset = rule_set.get("limit_atr", 0) * sig["atr"]
    return sig["close"] - offset if side == "long" else sig["close"] + offset


def limit_fill(side: str, sig: dict, bar: dict, rule_set: dict, through: float,
               slip: float) -> tuple[float, bool] | None:
    """How a limit entry listed at a signal's close fills in the next bar: (price, crossed), or None
    when it does not. Placed as a good-till-cancel order when the bar opens, one the market already
    reached takes the book at once, as a taker: at the open with ``slip``, never past its own price
    (crossed). Otherwise it rests, and fills at its price as a maker only when the bar trades
    ``through`` (a share of its price) past it: a bar that only touches it leaves it in the queue."""
    price = limit_price(side, sig, rule_set)
    if side == "long":
        if bar["o"] <= price:
            return min(bar["o"] * (1 + slip), price), True
        return (price, False) if bar["l"] <= price * (1 - through) else None
    if bar["o"] >= price:
        return max(bar["o"] * (1 - slip), price), True
    return (price, False) if bar["h"] >= price * (1 + through) else None


def simulate(series: list[dict], rule_set: dict, interval: str, cost: dict, limits: dict, *,
             rates: list[tuple[float, int]] | None = None, stance: list[dict] | None = None,
             direction: str = "both", start_equity: float = 1000.0, trade_from: int = 0,
             ind: dict | None = None) -> dict:
    """Trade the rules bar by bar: a signal at bar ``i``'s close fills at bar ``i+1``'s open, with
    slippage and the taker fee both ways; the stop placed with the entry fills inside a bar its range
    reaches (at the open when the bar gaps through it); funding (``rates``, from ``funding_by_bar``;
    the venue's baseline when left out) accrues each hour held. Trading starts at bar ``trade_from``
    (earlier bars only warm the indicators). A position still open at the end closes at the last close.
    A limit entry (``entry_order``) is placed at bar ``i+1``'s open instead (``limit_fill``): one the
    open already reached fills there at once as a taker, never past its price; else it rests through
    the bar and fills at its price with the maker fee only when the bar trades through it. The stop
    and the size are the market entry's, and the bar's stop and funding count whole, as if it filled at
    the open.
    Unfilled, ``limit`` enters nothing, while ``limit_then_market`` enters at market at the next open,
    as an entry from bar ``i+1``'s close, unless that close no longer holds the side. ``paths`` holds
    each trade's equity path for ``monte_carlo``: (end, low, high, drawdown), the equity at its close,
    lowest and highest marks as multiples of the equity before it, and the deepest fall from its own
    highest mark. One market of ``simulate_many``: the same run, without the market named."""
    return simulate_many({"": series}, {"": rule_set}, interval, cost, limits,
                         rates_by={"": rates} if rates else None, stance_by={"": stance} if stance else None,
                         direction_by={"": direction}, start_equity=start_equity, trade_from=trade_from,
                         ind_by={"": ind} if ind else None)


def simulate_many(series_by: dict, rules_by: dict, interval: str, cost: dict, limits: dict, *,
                  rates_by: dict | None = None, stance_by: dict | None = None, direction_by: dict | None = None,
                  start_equity: float = 1000.0, trade_from: int = 0, ind_by: dict | None = None) -> dict:
    """Trade several markets' rules on one account, as ``simulate`` trades one: bar by bar along the
    markets' shared timeline (the union of their bars' open times, oldest first; a market with no bar at
    a time sits that time out), each market's rules on its own bars, the cash shared. Each time has two
    steps, so nothing decided at an open sees the bar it opens: first every market's open (the close
    it was decided at, the entry, in the markets' order), then every market's bar (its stop, funding,
    trailing, close and the next decision). An entry is sized as the gate sizes it: from the account's
    value (the cash and the other markets' unrealized results) less what the other markets hold (their
    positions, and a limit of theirs resting through the bar), at prices known at that open. Trading
    starts at the ``trade_from``-th time. Each trade names its market when there is more than one.
    ``paths`` holds each trade's own path (the equity before it, moved by that trade alone), so
    ``monte_carlo`` composes trades one after another whether or not they overlapped; the curve is the
    account's. ``bars_held`` counts times with any position, and ``buy_hold_pct`` is the markets'
    mean."""
    markets = list(series_by)
    many = len(markets) > 1
    ind_by = {m: (ind_by or {}).get(m) or indicators(series_by[m], rules_by[m]) for m in markets}
    rates_by = {m: (rates_by or {}).get(m) or funding_by_bar(series_by[m], interval, None, BASELINE_FUNDING,
                                                               cost["funding"]) for m in markets}
    stance_by = {m: (stance_by or {}).get(m) or [] for m in markets}
    defaults = {m: {"direction": (direction_by or {}).get(m, "both"), "size": 1.0} for m in markets}
    fee, slip = cost["taker_bps"] / 10_000, cost["slippage_bps"] / 10_000
    maker, through = cost["maker_bps"] / 10_000, cost["limit_through_bps"] / 10_000
    cash = start_equity
    times = sorted({b["t"] for s in series_by.values() for b in s})
    at = {m: {b["t"]: i for i, b in enumerate(series_by[m])} for m in markets}
    # per market: the position, (close what is held?, side to open, its signal, how the entry is sent:
    # market | limit), the side of a limit_then_market entry that did not fill, the value a limit resting
    # through the bar reserves, and the newest price known (the open while the bar runs, then its close)
    state = {m: {"pos": None, "pending": None, "owed": None, "reserved": 0.0, "resting": None, "mark": None}
             for m in markets}
    trades: list[dict] = []
    paths: list[tuple[float, float, float, float]] = []
    curve: list[tuple[int, float]] = []
    totals = {"fees": 0.0, "funding": 0.0, "assumed_hours": 0, "bars_held": 0, **dict.fromkeys(LIMIT_TOTALS, 0)}

    def mark_path(pos: dict, value: float):
        m = value / pos["base"]
        pos["high"], pos["low"] = max(pos["high"], m), min(pos["low"], m)
        pos["dd"] = max(pos["dd"], 1 - m / pos["high"])

    def own(pos: dict, unrealized: float) -> float:
        """The trade's own path: the equity before it, moved by this trade alone (its fees, its funding,
        its result), kept bar by bar in the order the cash moves so one market reads as the cash."""
        return pos["own"] + unrealized

    def unrealized(pos: dict, price: float) -> float:
        return (price - pos["entry"]) * pos["qty"] * (1 if pos["side"] == "long" else -1)

    def close(m: str, t: int, price: float, reason: str):
        nonlocal cash
        pos = state[m]["pos"]
        exit_px = price * (1 - slip) if pos["side"] == "long" else price * (1 + slip)
        gross = unrealized(pos, exit_px)
        cost_out = exit_px * pos["qty"] * fee
        cash += gross - cost_out
        totals["fees"] += cost_out
        pnl = gross - cost_out - pos["fee_in"] - pos["funding"]
        trades.append({**({"market": m} if many else {}), "side": pos["side"], "open": iso(pos["t"]), "close": iso(t),
                       "entry": sig5(pos["entry"]), "exit": sig5(exit_px), "pnl": round(pnl, 2),
                       "r": round(pnl / pos["risk"], 2) if pos["risk"] else None, "reason": reason})
        end = own(pos, gross - cost_out)
        mark_path(pos, end)
        paths.append((end / pos["base"], pos["low"], pos["high"], pos["dd"]))
        state[m]["pos"] = None

    def open_position(m: str, side: str, signal_close: float, stop: float, value: float, entry: float, rate: float,
                      t: int):
        nonlocal cash
        qty = value / signal_close
        fee_in = entry * qty * rate
        # a maker rebate is not risk taken off: R stays the loss at the stop, never below it
        state[m]["pos"] = {"side": side, "qty": qty, "entry": entry, "stop": stop, "t": t, "fee_in": fee_in,
                           "funding": 0.0, "risk": abs(entry - stop) * qty + max(fee_in, 0.0),
                           "base": cash, "own": cash - fee_in, "low": 1.0, "high": 1.0, "dd": 0.0}
        cash -= fee_in
        totals["fees"] += fee_in

    def others(m: str) -> tuple[float, float]:
        """What the other markets hold when ``m`` sizes an entry at an open, at prices known then (their
        open of the same time, else their newest close): (the value held, as the gate's ``held``, with
        a limit resting there reserved, as the gate counts a resting order; their unrealized result,
        which the account's value carries)."""
        held = unrealized_now = 0.0
        for n, o in state.items():
            if n == m:
                continue
            if o["pos"] is not None:
                held += o["pos"]["qty"] * o["mark"]
                unrealized_now += unrealized(o["pos"], o["mark"])
            held += o["reserved"]
        return held, unrealized_now

    start = max(trade_from, 0)
    for k in range(start, len(times)):
        t = times[k]
        here = {m: at[m].get(t) for m in markets}
        for m in markets:  # the open: what the last close decided, at prices known at the open
            i = here[m]
            if i is None:
                continue
            state[m]["mark"] = series_by[m][i]["o"]
        held_here = any(state[m]["pos"] is not None for m in markets if here[m] is None)  # held on, no bar here
        for m in markets:
            i = here[m]
            if i is None:
                continue
            s, series, rule_set = state[m], series_by[m], rules_by[m]
            b = series[i]
            entry_order = rule_set.get("entry_order", "market")
            if s["pending"] is not None:
                do_close, side, sig, how = s["pending"]
                s["pending"] = None
                if do_close and s["pos"] is not None:
                    close(m, t, b["o"], "signal")
                if side and s["pos"] is None:
                    stance_now = _stance_at(stance_by[m], t, defaults[m])
                    stop = stop_price(side, sig["close"], sig["atr"], rule_set)
                    gapped = b["o"] <= stop if side == "long" else b["o"] >= stop
                    held, unrealized_now = others(m)
                    value, _ = size_usd(cash + unrealized_now, sig["close"], stop, rule_set, stance_now["size"], held,
                                        limits)
                    entry, rate = None, fee
                    if value is not None and not gapped:
                        if how == "limit":
                            totals["limit_orders"] += 1
                            filled = limit_fill(side, sig, b, rule_set, through, slip)
                            if filled is not None and filled[1]:  # the open had reached it: taken at once
                                entry, rate = filled[0], fee
                                totals["limit_crossed"] += 1
                            else:  # rests through the bar, counted like a resting order; a fill inside the
                                s["reserved"] = value  # bar is the bar's, not the open's
                                if filled is not None:
                                    s["resting"] = (side, sig["close"], stop, value, filled[0])
                                elif entry_order == "limit_then_market":
                                    s["owed"] = side
                        else:
                            entry = b["o"] * (1 + slip) if side == "long" else b["o"] * (1 - slip)
                            if how == "after_limit":
                                totals["market_after_limit"] += 1
                    if entry is not None:
                        totals["limit_filled"] += 1 if how == "limit" else 0
                        open_position(m, side, sig["close"], stop, value, entry, rate, t)
        for m in markets:  # the bar: its stop, funding, trailing and close, then the next bar's decision
            i = here[m]
            if i is None:
                continue
            s, series, rule_set, ind, rates = state[m], series_by[m], rules_by[m], ind_by[m], rates_by[m]
            b = series[i]
            entry_order = rule_set.get("entry_order", "market")
            s["reserved"] = 0.0  # a limit still resting at the close is canceled
            if s["resting"] is not None:  # the resting limit the bar trades through: filled as a maker
                side, signal_close, stop, value, price = s["resting"]
                s["resting"] = None
                totals["limit_filled"] += 1
                open_position(m, side, signal_close, stop, value, price, maker, t)
            pos = s["pos"]
            if pos is not None and (b["o"] <= pos["stop"] if pos["side"] == "long" else b["o"] >= pos["stop"]):
                close(m, t, b["o"], "stop")  # gapped through at the open: no funding for this bar
                pos = None
            if pos is not None:
                held_here = True
                rate, assumed = rates[i]
                paid = pos["qty"] * b["o"] * rate * (1 if pos["side"] == "long" else -1)
                cash -= paid
                pos["own"] -= paid
                pos["funding"] += paid
                totals["funding"] += paid
                totals["assumed_hours"] += assumed
                # a stop inside the bar: its hour is unknown from OHLC, so the bar's funding is charged whole
                if b["l"] <= pos["stop"] if pos["side"] == "long" else b["h"] >= pos["stop"]:
                    close(m, t, pos["stop"], "stop")
                    pos = None
            if pos is not None:  # the trailing stop follows this close from the next bar on
                pos["stop"] = trailed(pos["side"], pos["stop"], b["c"], ind["atr"][i], rule_set)
                mark_path(pos, own(pos, unrealized(pos, b["c"])))
            s["mark"] = b["c"]
            if i + 1 < len(series):
                stance_now = _stance_at(stance_by[m], series[i + 1]["t"], defaults[m])
                sig = signal(series, ind, i, rule_set)
                do_close, side = decide(sig, pos["side"] if pos else None, stance_now["direction"])
                how = "market" if entry_order == "market" else "limit"
                if s["owed"] is not None and pos is None and sig is not None:
                    # the limit that did not fill enters at market from this close, if the rules would still hold it
                    leave, _ = decide(sig, s["owed"], stance_now["direction"])
                    if not leave:
                        do_close, side, how = False, s["owed"], "after_limit"
                s["owed"] = None
                if do_close or side:
                    s["pending"] = (do_close, side, sig, how)
        if held_here:
            totals["bars_held"] += 1
        curve.append((t, cash + sum(unrealized(s["pos"], s["mark"]) for s in state.values() if s["pos"] is not None)))
    for m in markets:
        if state[m]["pos"] is not None and series_by[m]:
            close(m, series_by[m][-1]["t"], series_by[m][-1]["c"], "end")
    if curve and any(tr["reason"] == "end" for tr in trades):
        curve[-1] = (curve[-1][0], cash)
    traded = [m for m in markets if any(b["t"] >= times[start] for b in series_by[m])] if len(times) > start else []
    buy_hold = [(series_by[m][-1]["c"] / next(b for b in series_by[m] if b["t"] >= times[start])["o"] - 1) * 100
                for m in traded]
    return {"trades": trades, "paths": paths, "curve": curve, "totals": totals, "start_equity": start_equity,
            "end_equity": cash, "bars": len(times) - start, "interval": interval,
            "first": times[start] if len(times) > start else None, "last": times[-1] if times else None,
            "buy_hold_pct": sum(buy_hold) / len(buy_hold) if buy_hold else None}


def metrics(run: dict) -> dict:
    """The figures a decision reads: return, CAGR, maximum drawdown, MAR, Sharpe, trades, win rate,
    mean R, profit factor, time in the market, fees and funding paid, and buy-and-hold for scale; for
    rules with a limit entry, also how its orders went (placed, filled, at market after, missed)."""
    curve = [v for _, v in run["curve"]]
    start, end = run["start_equity"], run["end_equity"]
    trades = run["trades"]
    peak, max_dd = start, 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)
    years = (run["bars"] * INTERVAL_MS[run["interval"]]) / (365 * DAY_MS) if run["bars"] else 0
    cagr = ((end / start) ** (1 / years) - 1) * 100 if years > 0 and end > 0 else None
    returns = [(curve[i] / curve[i - 1] - 1) for i in range(1, len(curve)) if curve[i - 1] > 0]
    sharpe = None
    if len(returns) > 2:
        mean = sum(returns) / len(returns)
        sd = math.sqrt(sum((r - mean) ** 2 for r in returns) / (len(returns) - 1))
        if sd > 0:
            sharpe = mean / sd * math.sqrt(365 * DAY_MS / INTERVAL_MS[run["interval"]])
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [-t["pnl"] for t in trades if t["pnl"] <= 0]
    rs = [t["r"] for t in trades if t["r"] is not None]
    out = {"return_pct": round((end / start - 1) * 100, 2), "cagr_pct": None if cagr is None else round(cagr, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "mar": None if cagr is None or max_dd == 0 else round(cagr / (max_dd * 100), 3),
            "sharpe": None if sharpe is None else round(sharpe, 3), "trades": len(trades),
            "win_rate": round(len(wins) / len(trades), 3) if trades else None,
            "mean_r": round(sum(rs) / len(rs), 3) if rs else None,
            "profit_factor": round(sum(wins) / sum(losses), 3) if losses and sum(losses) > 0 else None,
            "time_in_market_pct": round(run["totals"]["bars_held"] / run["bars"] * 100, 1) if run["bars"] else None,
            "fees_pct": round(run["totals"]["fees"] / start * 100, 2),
            "funding_pct": round(run["totals"]["funding"] / start * 100, 2),
            "buy_hold_pct": None if run["buy_hold_pct"] is None else round(run["buy_hold_pct"], 2)}
    placed = run["totals"].get("limit_orders", 0)
    if placed:  # only rules with a limit entry say how it went, so a market entry's figures stay as they were
        filled, after = run["totals"]["limit_filled"], run["totals"]["market_after_limit"]
        out["limit_entries"] = {"placed": placed, "filled": filled, "fill_rate": round(filled / placed, 3),
                                "crossed": run["totals"]["limit_crossed"], "market_after": after,
                                "missed": placed - filled - after}
    return out


def _compose(paths) -> tuple[float, float, int]:
    """(deepest drawdown, final equity as a multiple of the start, longest run of losing trades) of
    trades taken one after another. Inside a trade the drawdown is the deeper of its lowest mark under
    the peak it started from and its fall from its own highest mark, which is exactly the deepest
    fall its bar-by-bar marks would show. A trade that leaves no equity (a gap through the stop) ends
    the sequence there, as the backtest opens nothing after it."""
    equity = peak = 1.0
    worst, streak, longest = 0.0, 0, 0
    for end, low, high, dd in paths:
        worst = max(worst, 1 - low * equity / peak, dd)
        peak = max(peak, equity * high)
        equity *= end
        streak = streak + 1 if end <= 1 else 0
        longest = max(longest, streak)
        if equity <= 0:
            break
    return worst, equity, longest


def _rank(values: list[float], share: float) -> float:
    """The value at ``share`` of a sorted list, by nearest rank."""
    return values[max(0, math.ceil(share * len(values)) - 1)]


def monte_carlo(run: dict, seed: str, runs: int = MC_RUNS) -> dict | None:
    """The spread of what the same trades could have done in another order: ``runs`` draws, with
    replacement, of as many trades as the run made, each with its own equity path, so a drawdown
    inside a trade counts as it did. Draws are independent: losses that cluster in one market regime
    are spread out, so the actual order (``observed``) is shown beside the spread. A draw that loses
    the whole account stops there, like the backtest. None below MC_MIN_TRADES trades."""
    paths = run["paths"]
    if len(paths) < MC_MIN_TRADES:
        return None
    rng = random.Random(f"hermes-hl-monte-carlo\x00{seed}")
    drawdowns, returns, streaks = [], [], []
    for _ in range(runs):
        dd, end, streak = _compose(rng.choices(paths, k=len(paths)))
        drawdowns.append(dd * 100)
        returns.append((end - 1) * 100)
        streaks.append(streak)
    drawdowns.sort()
    returns.sort()
    streaks.sort()
    dd, end, streak = _compose(paths)
    return {"runs": runs, "trades": len(paths),
            "max_drawdown_pct": {"observed": round(dd * 100, 2), "p50": round(_rank(drawdowns, 0.5), 2),
                                 "p95": round(_rank(drawdowns, 0.95), 2), "p99": round(_rank(drawdowns, 0.99), 2)},
            "return_pct": {"observed": round((end - 1) * 100, 2), "p5": round(_rank(returns, 0.05), 2),
                           "p50": round(_rank(returns, 0.5), 2)},
            "losing_streak": {"observed": streak, "p50": _rank(streaks, 0.5), "p95": _rank(streaks, 0.95)}}


def curve_points(curve: list[tuple[int, float]], points: int = CURVE_POINTS) -> dict:
    if not curve:
        return {"columns": ["t", "equity"], "rows": []}
    step = max(1, math.ceil(len(curve) / points))
    picked = curve[::step]
    if picked[-1] != curve[-1]:
        picked.append(curve[-1])
    return {"columns": ["t", "equity"], "rows": [[t, round(v, 2)] for t, v in picked]}


def backtest_limits(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    extra = set(raw) - {"exposure_pct", "max_leverage"}
    if extra:
        raise StrategyError(f"limits take exposure_pct and max_leverage, not {', '.join(sorted(extra))}")
    return {"exposure_pct": _number(raw, "exposure_pct", 1, 100, False, "limits") if "exposure_pct" in raw else 70.0,
            "max_leverage": _number(raw, "max_leverage", 1, 10, True, "limits") if "max_leverage" in raw else 2}


def grid(raw, base: dict) -> list[dict]:
    """Every rule set a walk-forward may choose from: the base rules with each listed parameter varied
    (``entry_order`` too, by its names)."""
    if not isinstance(raw, dict) or not raw:
        raise StrategyError("walk_forward.grid lists values per parameter, like {\"entry\": [20, 55]}")
    keys = sorted(raw)
    for key in keys:
        if key not in PARAMS[base["kind"]] and key not in OPTIONAL and key != "entry_order":
            raise StrategyError(f"walk_forward.grid: {base['kind']} has no {key}")
        if not isinstance(raw[key], list) or not 1 <= len(raw[key]) <= MAX_GRID_VALUES:
            raise StrategyError(f"walk_forward.grid.{key} lists 1 to {MAX_GRID_VALUES} values")
    combos = [{}]
    for key in keys:
        combos = [{**c, key: v} for c in combos for v in raw[key]]
    if len(combos) > MAX_GRID:
        raise StrategyError(f"walk_forward.grid makes {len(combos)} rule sets; at most {MAX_GRID}")
    out = []
    for combo in combos:
        try:
            out.append(rules({**base, **combo}, "walk_forward.grid"))
        except StrategyError:
            continue  # an impossible combination (exit longer than entry, slow under fast, exit_atr not under
            # entry_atr) is skipped
    if not out:
        raise StrategyError("walk_forward.grid makes no valid rule set")
    return out


OBJECTIVES = ("mar", "sharpe", "return_pct")


def _score(m: dict, objective: str, min_trades: int) -> float:
    if m["trades"] < min_trades or m[objective] is None:
        return -math.inf
    return m[objective]


def _walk_forward_args(raw, base: dict) -> tuple[list[dict], int, str, int, bool]:
    """(candidates, folds, objective, min_trades, anchored) from a walk_forward request."""
    if not isinstance(raw, dict):
        raise StrategyError("walk_forward is an object with grid and folds")
    candidates = grid(raw.get("grid"), base)
    folds = _number({"folds": raw.get("folds", 4)}, "folds", 2, MAX_FOLDS, True, "walk_forward")
    objective = raw.get("objective", "mar")
    if objective not in OBJECTIVES:
        raise StrategyError(f"walk_forward.objective is one of {', '.join(OBJECTIVES)}")
    min_trades = _number({"min_trades": raw.get("min_trades", 5)}, "min_trades", 0, 1000, True, "walk_forward")
    return candidates, folds, objective, min_trades, raw.get("anchored", True) is not False


def _chunk(bars: int, lead: int, folds: int) -> int:
    chunk = (bars - lead) // (folds + 1)
    if chunk < 50:
        raise StrategyError(f"{bars} bars are too few for {folds} folds; fewer folds or a longer window")
    return chunk


def walk_forward(series: list[dict], base: dict, interval: str, cost: dict, limits: dict, raw: dict, *,
                 rates: list[tuple[float, int]], stance: list[dict], direction: str, seed: str = "") -> dict:
    """Choose rules on past data, trade them on the next unseen window, and stitch the unseen windows:
    the out-of-sample result is what choosing this way would have earned, with the Monte Carlo of its
    trades (``seed``). ``raw``: grid, folds (2-6), objective (mar | sharpe | return_pct), min_trades,
    anchored (train on everything before, default true, else only the window before)."""
    candidates, folds, objective, min_trades, anchored = _walk_forward_args(raw, base)
    lead = max(warmup(c) for c in candidates)
    chunk = _chunk(len(series), lead, folds)
    cache = {}

    def run(rule_set, lo, hi, equity):
        key = canonical(rule_set)
        if key not in cache:
            cache[key] = indicators(series, rule_set)
        part = series[:hi]
        ind = {k: v[:hi] for k, v in cache[key].items()}
        return simulate(part, rule_set, interval, cost, limits, rates=rates[:hi], stance=stance,
                        direction=direction, start_equity=equity, trade_from=lo, ind=ind)

    equity = 1000.0
    stitched_curve: list[tuple[int, float]] = []
    stitched_trades: list[dict] = []
    stitched_paths: list[tuple[float, float, float, float]] = []
    totals = {"fees": 0.0, "funding": 0.0, "assumed_hours": 0, "bars_held": 0, **dict.fromkeys(LIMIT_TOTALS, 0)}
    rows = []
    for k in range(1, folds + 1):
        train_lo = lead if anchored else lead + (k - 1) * chunk
        train_hi, test_hi = lead + k * chunk, (lead + (k + 1) * chunk if k < folds else len(series))
        scored = []
        for c in candidates:
            m = metrics(run(c, train_lo, train_hi, 1000.0))
            scored.append((_score(m, objective, min_trades), m, c))
        scored.sort(key=lambda s: s[0], reverse=True)
        best_score, best_train, chosen = scored[0]
        test = run(chosen, train_hi, test_hi, equity)
        test_m = metrics(test)
        equity = test["end_equity"]
        stitched_curve += test["curve"]
        stitched_trades += test["trades"]
        stitched_paths += test["paths"]
        for key in totals:
            totals[key] += test["totals"][key]
        rows.append({"train": {"start": iso(series[train_lo]["t"]), "end": iso(series[train_hi - 1]["t"]),
                               objective: best_train[objective], "trades": best_train["trades"]},
                     "test": {"start": iso(series[train_hi]["t"]), "end": iso(series[test_hi - 1]["t"]), **test_m},
                     "chosen": {k2: v for k2, v in chosen.items() if k2 != "kind"},
                     "chosen_fingerprint": fingerprint(chosen, interval),
                     "nothing_qualified": best_score == -math.inf})
    first = lead + chunk
    stitched = {"trades": stitched_trades, "paths": stitched_paths, "curve": stitched_curve, "totals": totals,
                "start_equity": 1000.0, "end_equity": equity, "bars": len(series) - first, "interval": interval,
                "buy_hold_pct": (series[-1]["c"] / series[first]["o"] - 1) * 100}
    return {"objective": objective, "anchored": anchored, "folds": rows, "candidates": len(candidates),
            "out_of_sample": {**metrics(stitched), "monte_carlo": monte_carlo(stitched, f"{seed}\x00out_of_sample")},
            "equity": curve_points(stitched_curve),
            "window": {"start": iso(series[first]["t"]), "end": iso(series[-1]["t"])}}


def walk_forward_many(series_by: dict, base: dict, interval: str, cost: dict, limits: dict, raw: dict, *,
                      rates_by: dict, stance: list[dict], direction: str, seed: str = "") -> dict:
    """``walk_forward`` over several markets on one account: the folds are cut on the markets' shared
    timeline; in each, every market's rules are chosen on its own past bars (as ``walk_forward``
    chooses them, by the market's own result), and the chosen rules trade the next unseen window
    together (``simulate_many``). The stitched unseen windows are the account's out-of-sample result,
    with the Monte Carlo of its trades."""
    candidates, folds, objective, min_trades, anchored = _walk_forward_args(raw, base)
    markets = list(series_by)
    times = sorted({b["t"] for s in series_by.values() for b in s})
    lead = max(warmup(c) for c in candidates)
    chunk = _chunk(len(times), lead, folds)
    stamps = {m: [b["t"] for b in series_by[m]] for m in markets}
    cache: dict = {}

    def index(m: str, k: int) -> int:
        """The first bar of ``m`` at or after the ``k``-th shared time (its count when there is none)."""
        return bisect.bisect_left(stamps[m], times[k]) if k < len(times) else len(stamps[m])

    def ind_for(m: str, rule_set: dict, hi: int) -> dict:
        key = (m, canonical(rule_set))
        if key not in cache:
            cache[key] = indicators(series_by[m], rule_set)
        return {k: v[:hi] for k, v in cache[key].items()}

    def run_one(m: str, rule_set: dict, lo: int, hi: int) -> dict:
        at_lo, at_hi = index(m, lo), index(m, hi)
        return simulate(series_by[m][:at_hi], rule_set, interval, cost, limits, rates=rates_by[m][:at_hi],
                        stance=stance, direction=direction, start_equity=1000.0, trade_from=at_lo,
                        ind=ind_for(m, rule_set, at_hi))

    equity = 1000.0
    stitched_curve: list[tuple[int, float]] = []
    stitched_trades: list[dict] = []
    stitched_paths: list[tuple[float, float, float, float]] = []
    totals = {"fees": 0.0, "funding": 0.0, "assumed_hours": 0, "bars_held": 0, **dict.fromkeys(LIMIT_TOTALS, 0)}
    rows = []
    for k in range(1, folds + 1):
        train_lo = lead if anchored else lead + (k - 1) * chunk
        train_hi, test_hi = lead + k * chunk, (lead + (k + 1) * chunk if k < folds else len(times))
        chosen_by, train_by, fingerprints, unqualified = {}, {}, {}, []
        for m in markets:
            scored = []
            for c in candidates:
                met = metrics(run_one(m, c, train_lo, train_hi))
                scored.append((_score(met, objective, min_trades), met, c))
            scored.sort(key=lambda s: s[0], reverse=True)
            best_score, best_train, chosen = scored[0]
            chosen_by[m] = chosen
            train_by[m] = {objective: best_train[objective], "trades": best_train["trades"],
                           "chosen": {k2: v for k2, v in chosen.items() if k2 != "kind"}}
            fingerprints[m] = fingerprint(chosen, interval)
            if best_score == -math.inf:
                unqualified.append(m)
        ends = {m: index(m, test_hi) for m in markets}
        test = simulate_many({m: series_by[m][:ends[m]] for m in markets}, chosen_by, interval, cost, limits,
                             rates_by={m: rates_by[m][:ends[m]] for m in markets},
                             stance_by={m: stance for m in markets}, direction_by={m: direction for m in markets},
                             start_equity=equity, trade_from=train_hi,
                             ind_by={m: ind_for(m, chosen_by[m], ends[m]) for m in markets})
        test_m = metrics(test)
        equity = test["end_equity"]
        stitched_curve += test["curve"]
        stitched_trades += test["trades"]
        stitched_paths += test["paths"]
        for key in totals:
            totals[key] += test["totals"][key]
        rows.append({"train": {"start": iso(times[train_lo]), "end": iso(times[train_hi - 1]), "markets": train_by},
                     "test": {"start": iso(times[train_hi]), "end": iso(times[test_hi - 1]), **test_m},
                     "chosen": {m: train_by[m]["chosen"] for m in markets}, "chosen_fingerprint": fingerprints,
                     "nothing_qualified": unqualified})
    first = lead + chunk
    held_from = {m: index(m, first) for m in markets}
    buy_hold = [(series_by[m][-1]["c"] / series_by[m][held_from[m]]["o"] - 1) * 100
                for m in markets if held_from[m] < len(series_by[m])]
    stitched = {"trades": stitched_trades, "paths": stitched_paths, "curve": stitched_curve, "totals": totals,
                "start_equity": 1000.0, "end_equity": equity, "bars": len(times) - first, "interval": interval,
                "buy_hold_pct": sum(buy_hold) / len(buy_hold) if buy_hold else None}
    return {"objective": objective, "anchored": anchored, "folds": rows, "candidates": len(candidates),
            "markets": markets,
            "out_of_sample": {**metrics(stitched), "monte_carlo": monte_carlo(stitched, f"{seed}\x00out_of_sample")},
            "equity": curve_points(stitched_curve),
            "window": {"start": iso(times[first]), "end": iso(times[-1])}}


# --- specs and stances --------------------------------------------------------------------------

def _choice(raw, base: dict, variants: dict, what: str) -> dict:
    """A default choice {variant, direction, size} over ``base``, each named key validated."""
    if not isinstance(raw, dict):
        raise StrategyError(f"{what} is an object with variant, direction and size")
    out = {"variant": raw.get("variant", base["variant"]), "direction": raw.get("direction", base["direction"]),
           "size": value_in(raw.get("size", base["size"]), 0, 1, False, f"{what}.size")}
    if out["variant"] not in variants:
        raise StrategyError(f"{what}.variant names one of the variants")
    if out["direction"] not in DIRECTIONS:
        raise StrategyError(f"{what}.direction is one of {', '.join(DIRECTIONS)}")
    return out


def out_of_sample(raw) -> dict | None:
    """A variant's recorded walk-forward ``out_of_sample`` (its maximum drawdown, MAR and trades, and
    the Monte Carlo's 95th percentile drawdown when it ran), or None when none is recorded or it is
    not one: such a variant opens nothing."""
    if not isinstance(raw, dict):
        return None
    dd, trades, mar = raw.get("max_drawdown_pct"), raw.get("trades"), raw.get("mar")
    if isinstance(dd, bool) or not isinstance(dd, (int, float)) or not 0 <= dd <= 100:
        return None
    if isinstance(trades, bool) or not isinstance(trades, int) or trades < 1:
        return None
    if mar is not None and (isinstance(mar, bool) or not isinstance(mar, (int, float)) or not math.isfinite(mar)):
        return None
    mc = raw.get("monte_carlo")
    spread = mc.get("max_drawdown_pct") if isinstance(mc, dict) else None
    p95 = spread.get("p95") if isinstance(spread, dict) else None
    p95 = p95 if isinstance(p95, (int, float)) and not isinstance(p95, bool) and 0 <= p95 <= 100 else None
    return {"max_drawdown_pct": float(dd), "mar": mar, "trades": trades, "monte_carlo_p95_drawdown_pct": p95}


def spec(raw) -> dict:
    """A strategy spec, validated: what runs, on which account and markets, within which bounds. The
    default choice holds for every market, and ``default.markets`` overrides it per market. A variant
    keeps its walk-forward ``out_of_sample`` as ``out_of_sample`` (None when not recorded)."""
    if not isinstance(raw, dict) or raw.get("schema") != SPEC_SCHEMA:
        raise StrategyError(f"a strategy spec is a JSON object with schema {SPEC_SCHEMA}")
    name = raw.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        raise StrategyError("name is lower case letters, digits and dashes, at most 40")
    if raw.get("network") not in ("mainnet", "testnet"):
        raise StrategyError("network is mainnet or testnet")
    account, address = raw.get("account"), raw.get("address")
    if not isinstance(account, str) or not _ACCOUNT.match(account):
        raise StrategyError("account is the Hermes wallet account, like hermes/HERMES_MAIN#0")
    if not isinstance(address, str) or not _ADDRESS.match(address):
        raise StrategyError("address is the account's 0x address")
    markets = raw.get("markets")
    if (not isinstance(markets, list) or not 1 <= len(markets) <= MAX_MARKETS
            or not all(isinstance(m, str) and _COIN.match(m) for m in markets) or len(set(markets)) != len(markets)):
        raise StrategyError(f"markets lists 1 to {MAX_MARKETS} main-dex perps by ticker, like [\"BTC\", \"ETH\"]")
    interval = raw.get("interval")
    if interval not in INTERVAL_MS:
        raise StrategyError(f"interval is one of {', '.join(INTERVAL_MS)}")
    variants_raw = raw.get("variants")
    if not isinstance(variants_raw, dict) or not 1 <= len(variants_raw) <= MAX_VARIANTS:
        raise StrategyError(f"variants names 1 to {MAX_VARIANTS} rule sets, each with the backtest that validated it")
    variants = {}
    for vid, v in variants_raw.items():
        if not isinstance(vid, str) or not _NAME.match(vid) or not isinstance(v, dict):
            raise StrategyError("a variant id is lower case letters, digits and dashes, and its value an object")
        rule_set = rules(v.get("rules"), f"variants.{vid}.rules")
        validated = v.get("validated") if isinstance(v.get("validated"), dict) else {}
        if validated.get("fingerprint") != fingerprint(rule_set, interval):
            raise StrategyError(f"variant {vid} was not backtested as written: its validated.fingerprint must be the "
                                f"one the backtest of exactly these rules on {interval} reported")
        variants[vid] = {"rules": rule_set, "validated": validated,
                         "out_of_sample": out_of_sample(validated.get("out_of_sample"))}
    advisor_raw = raw.get("advisor") if isinstance(raw.get("advisor"), dict) else {}
    directions = advisor_raw.get("directions", list(DIRECTIONS))
    if not isinstance(directions, list) or not directions or not set(directions) <= set(DIRECTIONS):
        raise StrategyError(f"advisor.directions lists some of {', '.join(DIRECTIONS)}")
    advisor = {"directions": directions,
               "max_size": value_in(advisor_raw.get("max_size", 1.0), 0, 2, False, "advisor.max_size"),
               "max_age_days": value_in(advisor_raw.get("max_age_days", 7), 1, 14, True, "advisor.max_age_days"),
               "min_days_between_flips": value_in(advisor_raw.get("min_days_between_flips", 7), 0, 60, True,
                                                  "advisor.min_days_between_flips")}
    default_raw = raw.get("default") if isinstance(raw.get("default"), dict) else {}
    default = _choice(default_raw, {"variant": next(iter(variants)), "direction": "both", "size": 1.0},
                      variants, "default")
    per_market = default_raw.get("markets", {})
    if not isinstance(per_market, dict) or not set(per_market) <= set(markets):
        raise StrategyError("default.markets maps some of the strategy's markets to their own variant, direction "
                            "or size")
    default["markets"] = {m: _choice(per_market.get(m, {}), default, variants, f"default.markets.{m}")
                          for m in markets}
    limits_raw = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}
    limits = backtest_limits({k: limits_raw[k] for k in ("exposure_pct", "max_leverage") if k in limits_raw})
    mandate = raw.get("mandate")
    if mandate is not None:
        if not isinstance(mandate, dict):
            raise StrategyError("mandate is the mandate's id, bounds and end as mandates lists them")
        for key in ("max_order_usd", "max_exposure_usd"):
            try:
                if float(mandate.get(key)) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise StrategyError(f"mandate.{key} is the mandate's bound in USDC") from None
        if not isinstance(mandate.get("max_leverage"), int) or mandate["max_leverage"] < 1:
            raise StrategyError("mandate.max_leverage is the mandate's whole leverage")
        mandate = {"id": str(mandate.get("id", "")), "max_order_usd": float(mandate["max_order_usd"]),
                   "max_exposure_usd": float(mandate["max_exposure_usd"]), "max_leverage": mandate["max_leverage"],
                   "expires": parse_time(mandate.get("expires"), "mandate.expires")}
        limits["max_leverage"] = min(limits["max_leverage"], mandate["max_leverage"])
    # a breaker that cannot be read holds entries like a missing one, but never stops the closes and stops
    try:
        brake, problem = breaker(raw.get("breaker")), None
    except StrategyError as exc:
        brake, problem = None, str(exc)
    return {"schema": SPEC_SCHEMA, "name": name, "network": raw["network"], "account": account,
            "address": address.lower(), "markets": markets, "interval": interval, "variants": variants,
            "advisor": advisor, "default": default, "limits": limits, "mandate": mandate,
            "breaker": brake, "breaker_problem": problem,
            "active": raw.get("active", True) is not False, "purpose": str(raw.get("purpose", ""))[:200]}


def breaker(raw) -> dict | None:
    """The spec's drawdown breaker, {"max_drawdown_pct", "reset" (Unix ms or None)}, or None when the spec
    has none. ``reset`` is the user's resume: it counts only once it is later than the trip."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise StrategyError("breaker is {max_drawdown_pct, reset}")
    extra = set(raw) - {"max_drawdown_pct", "reset"}
    if extra:
        raise StrategyError(f"breaker takes max_drawdown_pct and reset, not {', '.join(sorted(extra))}")
    low, high = BREAKER_PCT
    limit = value_in(raw.get("max_drawdown_pct"), low, high, False, "breaker.max_drawdown_pct")
    reset = raw.get("reset")
    return {"max_drawdown_pct": limit, "reset": None if reset in (None, "") else parse_time(reset, "breaker.reset")}


def breaker_step(memory: dict | None, change_usd: float, equity_before: float, limit_pct: float | None,
                 reset_ms: int | None, now_ms: int) -> tuple[dict, float]:
    """The breaker after one gate run: (its memory, the drawdown in percent). The index moves by what the
    strategy's markets earned since the last run (``change_usd``: realized result less fees, funding,
    and the change in unrealized result) as a share of the account's value then (``equity_before``),
    so a deposit or a withdrawal moves it not at all and later results count against the new size. The
    drawdown is its fall below its highest value. It trips at ``limit_pct`` and stays tripped until a
    reset later than the trip and not in the future, which starts the index and its high again at 1,
    so even an account the strategy emptied can resume once refunded. No limit (``None``) keeps the
    index without ever tripping."""
    m = {"index": 1.0, "peak": 1.0, "tripped": None, "since": now_ms, **(memory or {})}
    if equity_before > 0 and change_usd:
        m["index"] = max(0.0, m["index"] * (1 + change_usd / equity_before))
    tripped = m["tripped"]
    if tripped and reset_ms is not None and tripped["at"] < reset_ms <= now_ms:
        m.update(tripped=None, index=1.0, peak=1.0, since=reset_ms)
    m["peak"] = max(m["peak"], m["index"])
    drawdown = round((m["peak"] - m["index"]) / m["peak"] * 100, 9) if m["peak"] > 0 else 100.0
    if m["tripped"] is None and limit_pct is not None and drawdown >= limit_pct:
        m["tripped"] = {"at": now_ms, "drawdown_pct": round(drawdown, 2)}
    return m, drawdown


def stance(strategy: dict, raw, now_ms: int, history: dict | None = None) -> tuple[dict, list[str], dict]:
    """The stance in force per market: (market -> {direction, variant, size, source}, notes, history).

    An advisor's stance counts only when it is this strategy's, current, dated and inside the spec's
    advisor bounds; anything else falls back to the spec's default, with a note saying why. Turning a
    market from long to short (or back) within ``min_days_between_flips`` of the last turn, directly or
    through flat or both, makes it flat until then: a premature flip only ever takes risk off.
    ``history`` (market -> {"bias": long | short, "since"}) is the gate's memory of the last side
    allowed; the updated copy is returned."""
    history = {k: dict(v) for k, v in (history or {}).items()}
    out = {m: {**strategy["default"]["markets"][m], "source": "default"} for m in strategy["markets"]}
    notes: list[str] = []
    if raw is not None:
        try:
            accepted = _stance(strategy, raw, now_ms)
        except StrategyError as exc:
            notes.append(f"advisor stance not used: {exc}")
            accepted = {}
        for market, choice in accepted.items():
            out[market] = {**choice, "source": "advisor"}
    flip_ms = strategy["advisor"]["min_days_between_flips"] * DAY_MS
    for market, choice in out.items():
        side = choice["direction"]
        if side not in SIDES:
            continue
        before = history.get(market)
        if before and before.get("bias") != side and now_ms - int(before.get("since", 0)) < flip_ms:
            notes.append(f"{market}: the turn to {side} waits until {iso(int(before['since']) + flip_ms)}; "
                         "flat until then")
            out[market] = {**choice, "direction": "flat", "source": "held"}
            continue
        if not before or before.get("bias") != side:
            history[market] = {"bias": side, "since": now_ms}
    return out, notes, history


def _stance(strategy: dict, raw, now_ms: int) -> dict:
    if not isinstance(raw, dict) or raw.get("schema") != STANCE_SCHEMA:
        raise StrategyError(f"a stance is a JSON object with schema {STANCE_SCHEMA}")
    if raw.get("strategy") != strategy["name"]:
        raise StrategyError(f"it names strategy {raw.get('strategy')!r}, not {strategy['name']!r}")
    issued, expires = parse_time(raw.get("issued"), "issued"), parse_time(raw.get("expires"), "expires")
    max_age = strategy["advisor"]["max_age_days"] * DAY_MS
    if issued > now_ms + 5 * 60_000:
        raise StrategyError("it is issued in the future")
    if expires <= now_ms:
        raise StrategyError(f"it expired at {iso(expires)}")
    if expires - issued > max_age:
        raise StrategyError(f"it runs longer than the spec's {strategy['advisor']['max_age_days']} days")
    basis = raw.get("basis")
    if not isinstance(basis, list) or not basis:
        raise StrategyError("basis lists the facts it rests on, each with a source and an as_of time")
    for n, item in enumerate(basis):
        if not isinstance(item, dict) or not str(item.get("claim", "")).strip() or not str(item.get("source", "")).strip():
            raise StrategyError(f"basis[{n}] needs a claim and a source")
        if parse_time(item.get("as_of"), f"basis[{n}].as_of") > issued:
            raise StrategyError(f"basis[{n}] is dated after the stance was issued")
    markets = raw.get("markets")
    if not isinstance(markets, dict) or not markets:
        raise StrategyError("markets maps each market to {direction, variant, size}")
    out = {}
    for market, choice in markets.items():
        if market not in strategy["markets"]:
            raise StrategyError(f"{market} is not one of the strategy's markets")
        if not isinstance(choice, dict):
            raise StrategyError(f"markets.{market} is an object")
        direction = choice.get("direction")
        if direction not in strategy["advisor"]["directions"]:
            raise StrategyError(f"markets.{market}.direction is one of {', '.join(strategy['advisor']['directions'])}")
        variant = choice.get("variant", strategy["default"]["markets"][market]["variant"])
        if variant not in strategy["variants"]:
            raise StrategyError(f"markets.{market}.variant is one of {', '.join(strategy['variants'])}")
        size = value_in(choice.get("size", 1.0), 0, strategy["advisor"]["max_size"], False, f"markets.{market}.size")
        out[market] = {"direction": direction, "variant": variant, "size": size}
    return out


# --- the live decision --------------------------------------------------------------------------

def evaluate(series: list[dict], rule_set: dict, choice: dict, holding: str | None) -> dict:
    """What the rules and the stance in force say at the newest completed bar: {"bar", "close"
    (bool), "open" (side or None), "stop", "atr", "price", "why"}, and for a position held under a
    trailing rule "trail": where its stop should be at least after this bar."""
    if not series:
        return {"bar": None, "close": False, "open": None, "why": "no completed bars"}
    ind = indicators(series, rule_set)
    i = len(series) - 1
    sig = signal(series, ind, i, rule_set)
    if sig is None:
        return {"bar": series[i]["t"], "close": False, "open": None,
                "why": f"{len(series)} bars; the rules need {warmup(rule_set)}"}
    do_close, side = decide(sig, holding, choice["direction"])
    out = {"bar": series[i]["t"], "close": do_close, "open": side, "atr": sig["atr"], "price": sig["close"],
           "why": sig["why"]}
    if side:
        out["stop"] = stop_price(side, sig["close"], sig["atr"], rule_set)
        if rule_set.get("entry_order"):
            out["limit"] = limit_price(side, sig, rule_set)
    if holding and not do_close and rule_set.get("trail_atr"):
        worst = -math.inf if holding == "long" else math.inf
        out["trail"] = trailed(holding, worst, sig["close"], sig["atr"], rule_set)
    return out


def market_after_limit(series: list[dict], rule_set: dict, choice: dict, side: str) -> dict | None:
    """The market entry a ``limit_then_market`` limit that did not fill turns into, as ``simulate`` takes
    it: an entry on ``side`` from the newest completed bar's close (its stop, and its size from there),
    when the rules at that close would still hold the side; None when they would close it or cannot say."""
    if not series:
        return None
    ind = indicators(series, rule_set)
    sig = signal(series, ind, len(series) - 1, rule_set)
    if sig is None or decide(sig, side, choice["direction"])[0]:
        return None
    return {"bar": series[-1]["t"], "open": side, "atr": sig["atr"], "price": sig["close"], "why": sig["why"],
            "stop": stop_price(side, sig["close"], sig["atr"], rule_set)}
