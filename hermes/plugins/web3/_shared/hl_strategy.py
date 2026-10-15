"""Rule strategies on Hyperliquid perps: one decision shared by the backtest and the cron gate.

Pure Python, stdlib only: no network, no file, no key. ``hl.py``'s ``backtest`` read runs ``backtest``
and ``walk_forward`` over candles it fetched; ``hl_gate.py`` runs ``evaluate`` on the newest
completed candle for a strategy in force. Because both call ``signal`` on the same completed bars,
what was tested is what runs. Contract: docs/hyperliquid.md "Strategies".

- **Rules** are a ``kind`` and its numbers (``breakout``: a Donchian channel; ``ema_cross``: two
  EMAs), each with an ATR stop placed with the entry and a risk per trade. ``fingerprint`` names a
  rule set exactly (with its interval), so a strategy may only run rules a backtest reported.
- **A strategy spec** names the account, network, markets, interval, its validated variants, the
  default stance, the bounds an advisor may choose within, and its limits.
- **A stance** is an advisor's choice inside those bounds: per market a direction, a variant and a
  size multiplier, with an expiry and a dated basis. It never widens a limit: the mandate and the
  spec's limits still bound every order.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
import re

SPEC_SCHEMA = "hermes-hyperliquid-strategy/1"
STANCE_SCHEMA = "hermes-hyperliquid-stance/1"
BACKTEST_SCHEMA = "hermes-hyperliquid-backtest/1"
KINDS = ("breakout", "ema_cross")
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
}
COSTS = {"taker_bps": (0.0, 100.0, 4.5), "slippage_bps": (0.0, 100.0, 5.0)}


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
    extra = set(raw) - set(PARAMS[kind]) - {"kind"}
    if extra:
        raise StrategyError(f"{what}: {kind} takes {', '.join(PARAMS[kind])}, not {', '.join(sorted(extra))}")
    out = {"kind": kind}
    for key, (low, high, whole) in PARAMS[kind].items():
        out[key] = _number(raw, key, low, high, whole, what)
    if kind == "breakout" and out["exit"] > out["entry"]:
        raise StrategyError(f"{what}: exit must not be longer than entry")
    if kind == "ema_cross" and out["slow"] <= out["fast"]:
        raise StrategyError(f"{what}: slow must be longer than fast")
    return out


def fingerprint(rule_set: dict, interval: str) -> str:
    """The exact name of a rule set on an interval: a strategy runs only rules a backtest reported."""
    return hashlib.sha256(canonical({"interval": interval, "rules": rule_set}).encode()).hexdigest()[:16]


def warmup(rule_set: dict) -> int:
    """Completed bars needed before the first signal."""
    if rule_set["kind"] == "breakout":
        return max(rule_set["entry"], rule_set["exit"], rule_set["atr"]) + 1
    return max(rule_set["slow"] * 3, rule_set["atr"]) + 1


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
    else:
        ind["fast"] = _ema(series, rule_set["fast"])
        ind["slow"] = _ema(series, rule_set["slow"])
    return ind


def signal(series: list[dict], ind: dict, i: int, rule_set: dict) -> dict | None:
    """What the rules say at the close of completed bar ``i``: {"long": enter?, "short": enter?,
    "exit_long", "exit_short", "atr", "close", "why"}; None before the indicators are ready."""
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


def simulate(series: list[dict], rule_set: dict, interval: str, cost: dict, limits: dict, *,
             rates: list[tuple[float, int]] | None = None, stance: list[dict] | None = None,
             direction: str = "both", start_equity: float = 1000.0, trade_from: int = 0,
             ind: dict | None = None) -> dict:
    """Trade the rules bar by bar: a signal at bar ``i``'s close fills at bar ``i+1``'s open, with
    slippage and the taker fee both ways; the stop placed with the entry fills inside a bar its range
    reaches (at the open when the bar gaps through it); funding (``rates``, from ``funding_by_bar``;
    the venue's baseline when left out) accrues each hour held. Trading starts at bar ``trade_from``
    (earlier bars only warm the indicators). A position still open at the end closes at the last close."""
    ind = ind or indicators(series, rule_set)
    rates = rates or funding_by_bar(series, interval, None, BASELINE_FUNDING, cost["funding"])
    fee, slip = cost["taker_bps"] / 10_000, cost["slippage_bps"] / 10_000
    default = {"direction": direction, "size": 1.0}
    stance = stance or []
    cash = start_equity
    pos = None
    trades: list[dict] = []
    curve: list[tuple[int, float]] = []
    totals = {"fees": 0.0, "funding": 0.0, "assumed_hours": 0, "bars_held": 0}
    pending: tuple[bool, str | None, dict | None] | None = None

    def close(i: int, price: float, reason: str):
        nonlocal cash, pos
        exit_px = price * (1 - slip) if pos["side"] == "long" else price * (1 + slip)
        gross = (exit_px - pos["entry"]) * pos["qty"] * (1 if pos["side"] == "long" else -1)
        cost_out = exit_px * pos["qty"] * fee
        cash += gross - cost_out
        totals["fees"] += cost_out
        pnl = gross - cost_out - pos["fee_in"] - pos["funding"]
        trades.append({"side": pos["side"], "open": iso(pos["t"]), "close": iso(series[i]["t"]), "entry": sig5(pos["entry"]),
                       "exit": sig5(exit_px), "pnl": round(pnl, 2), "r": round(pnl / pos["risk"], 2) if pos["risk"] else None,
                       "reason": reason})
        pos = None

    start = max(trade_from, 0)
    for i in range(start, len(series)):
        b = series[i]
        if pending is not None:
            do_close, side, sig = pending
            pending = None
            if do_close and pos is not None:
                close(i, b["o"], "signal")
            if side and pos is None:
                stance_now = _stance_at(stance, b["t"], default)
                stop = stop_price(side, sig["close"], sig["atr"], rule_set)
                gapped = b["o"] <= stop if side == "long" else b["o"] >= stop
                equity = cash
                value, _ = size_usd(equity, sig["close"], stop, rule_set, stance_now["size"], 0.0, limits)
                if value is not None and not gapped:
                    entry = b["o"] * (1 + slip) if side == "long" else b["o"] * (1 - slip)
                    qty = value / sig["close"]
                    fee_in = entry * qty * fee
                    cash -= fee_in
                    totals["fees"] += fee_in
                    pos = {"side": side, "qty": qty, "entry": entry, "stop": stop, "t": b["t"], "fee_in": fee_in,
                           "funding": 0.0, "risk": abs(entry - stop) * qty + fee_in}
        if pos is not None and (b["o"] <= pos["stop"] if pos["side"] == "long" else b["o"] >= pos["stop"]):
            close(i, b["o"], "stop")  # gapped through at the open: no funding for this bar
        if pos is not None:
            totals["bars_held"] += 1
            rate, assumed = rates[i]
            paid = pos["qty"] * b["o"] * rate * (1 if pos["side"] == "long" else -1)
            cash -= paid
            pos["funding"] += paid
            totals["funding"] += paid
            totals["assumed_hours"] += assumed
            # a stop inside the bar: its hour is unknown from OHLC, so the bar's funding is charged whole
            if b["l"] <= pos["stop"] if pos["side"] == "long" else b["h"] >= pos["stop"]:
                close(i, pos["stop"], "stop")
        mark = cash
        if pos is not None:
            mark += (b["c"] - pos["entry"]) * pos["qty"] * (1 if pos["side"] == "long" else -1)
        curve.append((b["t"], mark))
        if i + 1 < len(series):
            stance_now = _stance_at(stance, series[i + 1]["t"], default)
            sig = signal(series, ind, i, rule_set)
            do_close, side = decide(sig, pos["side"] if pos else None, stance_now["direction"])
            if do_close or side:
                pending = (do_close, side, sig)
    if pos is not None and series:
        close(len(series) - 1, series[-1]["c"], "end")
        curve[-1] = (curve[-1][0], cash)
    return {"trades": trades, "curve": curve, "totals": totals, "start_equity": start_equity, "end_equity": cash,
            "bars": len(series) - start, "interval": interval,
            "first": series[start]["t"] if len(series) > start else None,
            "last": series[-1]["t"] if series else None,
            "buy_hold_pct": (series[-1]["c"] / series[start]["o"] - 1) * 100 if len(series) > start else None}


def metrics(run: dict) -> dict:
    """The figures a decision reads: return, CAGR, maximum drawdown, MAR, Sharpe, trades, win rate,
    mean R, profit factor, time in the market, fees and funding paid, and buy-and-hold for scale."""
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
    return {"return_pct": round((end / start - 1) * 100, 2), "cagr_pct": None if cagr is None else round(cagr, 2),
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
    """Every rule set a walk-forward may choose from: the base rules with each listed parameter varied."""
    if not isinstance(raw, dict) or not raw:
        raise StrategyError("walk_forward.grid lists values per parameter, like {\"entry\": [20, 55]}")
    keys = sorted(raw)
    for key in keys:
        if key not in PARAMS[base["kind"]]:
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
            continue  # an impossible combination (exit longer than entry, slow under fast) is skipped
    if not out:
        raise StrategyError("walk_forward.grid makes no valid rule set")
    return out


OBJECTIVES = ("mar", "sharpe", "return_pct")


def _score(m: dict, objective: str, min_trades: int) -> float:
    if m["trades"] < min_trades or m[objective] is None:
        return -math.inf
    return m[objective]


def walk_forward(series: list[dict], base: dict, interval: str, cost: dict, limits: dict, raw: dict, *,
                 rates: list[tuple[float, int]], stance: list[dict], direction: str) -> dict:
    """Choose rules on past data, trade them on the next unseen window, and stitch the unseen windows:
    the out-of-sample result is what choosing this way would have earned. ``raw``: grid, folds (2-8),
    objective (mar | sharpe | return_pct), min_trades, anchored (train on everything before, default
    true, else only the window before)."""
    if not isinstance(raw, dict):
        raise StrategyError("walk_forward is an object with grid and folds")
    candidates = grid(raw.get("grid"), base)
    folds = _number({"folds": raw.get("folds", 4)}, "folds", 2, MAX_FOLDS, True, "walk_forward")
    objective = raw.get("objective", "mar")
    if objective not in OBJECTIVES:
        raise StrategyError(f"walk_forward.objective is one of {', '.join(OBJECTIVES)}")
    min_trades = _number({"min_trades": raw.get("min_trades", 5)}, "min_trades", 0, 1000, True, "walk_forward")
    anchored = raw.get("anchored", True) is not False
    lead = max(warmup(c) for c in candidates)
    usable = len(series) - lead
    chunk = usable // (folds + 1)
    if chunk < 50:
        raise StrategyError(f"{len(series)} bars are too few for {folds} folds; fewer folds or a longer window")
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
    totals = {"fees": 0.0, "funding": 0.0, "assumed_hours": 0, "bars_held": 0}
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
        for key in totals:
            totals[key] += test["totals"][key]
        rows.append({"train": {"start": iso(series[train_lo]["t"]), "end": iso(series[train_hi - 1]["t"]),
                               objective: best_train[objective], "trades": best_train["trades"]},
                     "test": {"start": iso(series[train_hi]["t"]), "end": iso(series[test_hi - 1]["t"]), **test_m},
                     "chosen": {k2: v for k2, v in chosen.items() if k2 != "kind"},
                     "chosen_fingerprint": fingerprint(chosen, interval),
                     "nothing_qualified": best_score == -math.inf})
    first = lead + chunk
    stitched = {"trades": stitched_trades, "curve": stitched_curve, "totals": totals, "start_equity": 1000.0,
                "end_equity": equity, "bars": len(series) - first, "interval": interval,
                "buy_hold_pct": (series[-1]["c"] / series[first]["o"] - 1) * 100}
    return {"objective": objective, "anchored": anchored, "folds": rows, "candidates": len(candidates),
            "out_of_sample": metrics(stitched), "equity": curve_points(stitched_curve),
            "window": {"start": iso(series[first]["t"]), "end": iso(series[-1]["t"])}}


# --- specs and stances --------------------------------------------------------------------------

def spec(raw) -> dict:
    """A strategy spec, validated: what runs, on which account and markets, within which bounds."""
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
        variants[vid] = {"rules": rule_set, "validated": validated}
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
    default = {"variant": default_raw.get("variant", next(iter(variants))),
               "direction": default_raw.get("direction", "both"),
               "size": value_in(default_raw.get("size", 1.0), 0, 1, False, "default.size")}
    if default["variant"] not in variants:
        raise StrategyError("default.variant names one of the variants")
    if default["direction"] not in DIRECTIONS:
        raise StrategyError(f"default.direction is one of {', '.join(DIRECTIONS)}")
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
    return {"schema": SPEC_SCHEMA, "name": name, "network": raw["network"], "account": account,
            "address": address.lower(), "markets": markets, "interval": interval, "variants": variants,
            "advisor": advisor, "default": default, "limits": limits, "mandate": mandate,
            "active": raw.get("active", True) is not False, "purpose": str(raw.get("purpose", ""))[:200]}


def stance(strategy: dict, raw, now_ms: int, history: dict | None = None) -> tuple[dict, list[str], dict]:
    """The stance in force per market: (market -> {direction, variant, size, source}, notes, history).

    An advisor's stance counts only when it is this strategy's, current, dated and inside the spec's
    advisor bounds; anything else falls back to the spec's default, with a note saying why. Turning a
    market from long to short (or back) within ``min_days_between_flips`` of the last turn, directly or
    through flat or both, makes it flat until then: a premature flip only ever takes risk off.
    ``history`` (market -> {"bias": long | short, "since"}) is the gate's memory of the last side
    allowed; the updated copy is returned."""
    history = {k: dict(v) for k, v in (history or {}).items()}
    default = strategy["default"]
    out = {m: {**default, "source": "default"} for m in strategy["markets"]}
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
        variant = choice.get("variant", strategy["default"]["variant"])
        if variant not in strategy["variants"]:
            raise StrategyError(f"markets.{market}.variant is one of {', '.join(strategy['variants'])}")
        size = value_in(choice.get("size", 1.0), 0, strategy["advisor"]["max_size"], False, f"markets.{market}.size")
        out[market] = {"direction": direction, "variant": variant, "size": size}
    return out


# --- the live decision --------------------------------------------------------------------------

def evaluate(series: list[dict], rule_set: dict, choice: dict, holding: str | None) -> dict:
    """What the rules and the stance in force say at the newest completed bar: {"bar", "close"
    (bool), "open" (side or None), "stop", "atr", "price", "why"}."""
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
    return out
