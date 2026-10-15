"""The read engine of the ``hyperliquid`` tool: one read per process, run by the web3 venv's interpreter.

The plugin writes one JSON request to stdin and reads one JSON reply from stdout:

    {"action": "markets" | "state" | …, "network": "mainnet" | "testnet", …the action's arguments}
    → {"ok": true, "data": {…}} or {"ok": false, "error": "…"}

Everything here goes through Hyperliquid's public ``/info`` endpoint: no key, nothing signed, no file
written. Names chosen by deployers (builder perp dexs, spot tokens) are data from strangers: a short
plain ticker stays as it is, anything longer or odder, and every full name, arrives as
``{"untrusted": …}``. ``_api`` (a base URL) is honoured only when the engine's own tests set
``WEB3_ENGINE_TEST=1``; the plugin never passes it. Contract: docs/hyperliquid.md "Reads".
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import chains
import hl_strategy
import rpc
from rpc import ChainError

NETWORKS = {
    "mainnet": {"api": "https://api.hyperliquid.xyz", "label": "Hyperliquid mainnet",
                "explorer": "https://app.hyperliquid.xyz/explorer"},
    "testnet": {"api": "https://api.hyperliquid-testnet.xyz", "label": "Hyperliquid testnet",
                "explorer": "https://app.hyperliquid-testnet.xyz/explorer"},
}
TIMEOUT = 20
HOUR_MS = 3_600_000
INTERVALS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": HOUR_MS,
             "2h": 2 * HOUR_MS, "4h": 4 * HOUR_MS, "8h": 8 * HOUR_MS, "12h": 12 * HOUR_MS, "1d": 24 * HOUR_MS,
             "3d": 72 * HOUR_MS, "1w": 168 * HOUR_MS, "1M": 720 * HOUR_MS}
SORTS = ("volume", "oi", "funding_abs", "change_abs", "name")
FUNDING_PAGE = 500       # rows fundingHistory returns per request
FUNDING_PAGES = 4        # with hourly funding, 2000 hours: the longest funding window
CANDLES_MAX = 5000       # candles the venue keeps per coin and interval
UNREAD_CANDLES = "the venue keeps only the newest 5000 candles: the window's start is cut; use a longer interval"
FILLS_PAGE = 2000        # rows userFills / userFillsByTime return per request
FILLS_PAGES = 3
UNREAD_FILLS = "the window holds more fills than one read returns, so part of it is missing; shorten hours"
REVIEW_COINS = 8         # traded perps a review reads market context for
EXPORT_SCHEMA = "hermes-hyperliquid-export/1"
SPOT_OFFSET = 10_000
BUILDER_OFFSET = 100_000
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TICKER = re.compile(r"^[A-Za-z0-9._:/@+-]{1,24}$")
_DEX = re.compile(r"^[a-z0-9]{1,16}$")
_CLOID = re.compile(r"^0x[0-9a-fA-F]{32}$")


# --- small helpers ------------------------------------------------------------------------------

def ticker(text):
    """A deployer-chosen name: plain when it is a short ticker, else marked as text from strangers."""
    if text is None:
        return None
    text = str(text)
    return text if _TICKER.match(text) else {"untrusted": text[:120]}


def stranger(text):
    return None if text in (None, "") else {"untrusted": str(text)[:200]}


def num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(new, old) -> float | None:
    new, old = num(new), num(old)
    if new is None or not old:
        return None
    return round((new - old) / old * 100, 4)


def iso(ms) -> str | None:
    if not isinstance(ms, (int, float)):
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rounded(value, places=6):
    return None if value is None else round(value, places)


def integer(args: dict, key: str, default: int, low: int, high: int) -> int:
    value = args.get(key, default)
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChainError(f"{key} must be a whole number")
    if not low <= value <= high:
        raise ChainError(f"{key} must be between {low} and {high}")
    return value


def address(args: dict) -> str:
    value = args.get("address")
    if not isinstance(value, str) or not _ADDRESS.match(value):
        raise ChainError("address is required: the account's 0x address (40 hex digits)")
    return value.lower()


def coin_arg(args: dict) -> str:
    value = args.get("coin")
    if not isinstance(value, str) or not value.strip() or len(value) > 40:
        raise ChainError("coin is required: a perp like BTC, a builder perp like dex:COIN, or a spot pair like "
                         "PURR/USDC or @107")
    return value.strip()


def dex_arg(args: dict) -> str:
    value = args.get("dex") or ""
    if not isinstance(value, str) or (value and not _DEX.match(value)):
        raise ChainError("dex is a builder perp dex name from dexs (lower case), or left out for the main one")
    return value


def window(args: dict, default_hours: int, max_hours: int) -> tuple[int, int]:
    hours = integer(args, "hours", default_hours, 1, max_hours)
    end = args.get("end_time")
    if end is None:
        end = int(datetime.now(timezone.utc).timestamp() * 1000)
    elif isinstance(end, bool) or not isinstance(end, int) or end < 1_500_000_000_000:
        raise ChainError("end_time is a Unix time in milliseconds, like 1760000000000")
    return end - hours * HOUR_MS, end


def is_spot(coin: str) -> bool:
    return coin.startswith("@") or "/" in coin


def perp_asset(dex_index: int, index: int) -> int:
    return index if dex_index == 0 else BUILDER_OFFSET + dex_index * 10_000 + index


# --- the API ------------------------------------------------------------------------------------

class Api:
    """Hyperliquid's ``/info`` endpoint on one network. Errors name the network, never a URL."""

    def __init__(self, network: str, override: str | None = None):
        self.network = network
        self.label = NETWORKS[network]["label"]
        self.base = override if override and rpc.testing() else NETWORKS[network]["api"]

    def info(self, body: dict):
        request = urllib.request.Request(self.base + "/info", data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": rpc.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ChainError(f"{self.label} rate-limited the request; wait a minute and narrow the read") from None
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace").strip()[:200]
            except Exception:
                pass
            raise ChainError(f"{self.label} refused {body.get('type')} (HTTP {exc.code})"
                             + (f": {rpc.mask(detail)}" if detail else "")) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ChainError(f"{self.label} could not be reached ({type(reason).__name__})") from None
        except ValueError:
            raise ChainError(f"{self.label} returned something that is not JSON") from None


class Ctx:
    def __init__(self, network: str, payload: dict):
        self.network = network
        self.api = Api(network, payload.get("_api"))
        self._dexs = None
        self._spot = None

    def account(self, user: str) -> dict:
        """The head of every account read: which network, which address, and its explorer page."""
        return {"network": self.network, "address": user,
                "explorer": f"{NETWORKS[self.network]['explorer']}/address/{user}"}

    def dexs(self) -> list:
        """perpDexs as listed: index 0 is the main dex (null), builder dexs follow."""
        if self._dexs is None:
            found = self.api.info({"type": "perpDexs"})
            self._dexs = found if isinstance(found, list) else [None]
        return self._dexs

    def dex_index(self, dex: str) -> int:
        if not dex:
            return 0
        for index, entry in enumerate(self.dexs()):
            if isinstance(entry, dict) and entry.get("name") == dex:
                return index
        raise ChainError(f"no builder perp dex {dex!r} on {self.api.label}; dexs lists them")

    def spot(self) -> tuple[dict, list]:
        if self._spot is None:
            found = self.api.info({"type": "spotMetaAndAssetCtxs"})
            if not (isinstance(found, list) and len(found) == 2):
                raise ChainError(f"{self.api.label} returned an unexpected spot listing")
            self._spot = (found[0], found[1])
        return self._spot

    def spot_pairs(self) -> list[dict]:
        meta, ctxs = self.spot()
        tokens = {t.get("index"): t for t in meta.get("tokens", [])}
        by_coin = {c.get("coin"): c for c in ctxs if isinstance(c, dict)}
        pairs = []
        for entry in meta.get("universe", []):
            base, quote = (tokens.get(i, {}) for i in (entry.get("tokens") or [None, None])[:2])
            pairs.append({"coin": entry.get("name"), "index": entry.get("index"),
                          "base": base.get("name"), "quote": quote.get("name"),
                          "sz_decimals": base.get("szDecimals"), "canonical": entry.get("isCanonical"),
                          "base_full_name": base.get("fullName"), "ctx": by_coin.get(entry.get("name"), {})})
        return pairs

    def spot_coin(self, coin: str) -> str:
        """The API's name for a spot pair: PURR/USDC (canonical) or @index, given either or BASE/QUOTE."""
        pairs = self.spot_pairs()
        for pair in pairs:
            if pair["coin"] == coin:
                return coin
        wanted = coin.upper()
        matches = [p for p in pairs if f"{p['base']}/{p['quote']}".upper() == wanted]
        canonical = [p for p in matches if p["canonical"]]
        if len(canonical) == 1 or len(matches) == 1:
            return (canonical or matches)[0]["coin"]
        if matches:  # token names are chosen by their deployers: a look-alike pair is never picked silently
            names = ", ".join(str(p["coin"]) for p in matches[:10])
            raise ChainError(f"{coin!r} names several spot pairs on {self.api.label} ({names}); use the @N name from "
                             "spots")
        raise ChainError(f"no spot pair {coin!r} on {self.api.label}; spots lists them")

    def coin(self, coin: str) -> str:
        return self.spot_coin(coin) if is_spot(coin) else coin


# --- markets ------------------------------------------------------------------------------------

def dexs(ctx, args) -> dict:
    rows = [{"index": 0, "name": "", "about": "the main perp dex (leave dex out)", "first_asset": 0}]
    for index, entry in enumerate(ctx.dexs()):
        if index == 0 or not isinstance(entry, dict):
            continue
        rows.append({"index": index, "name": ticker(entry.get("name")), "full_name": stranger(entry.get("fullName")),
                     "deployer": entry.get("deployer"), "first_asset": perp_asset(index, 0)})
    return {"network": ctx.network, "dexs": rows,
            "note": "builder dexs are deployed by third parties; their coins read dex:COIN"}


def _perp_row(dex_index: int, index: int, meta: dict, asset: dict) -> dict:
    mark, prev = asset.get("markPx"), asset.get("prevDayPx")
    funding = num(asset.get("funding"))
    oi = num(asset.get("openInterest"))
    sz_decimals = meta.get("szDecimals")
    row = {"coin": ticker(meta.get("name")), "asset": perp_asset(dex_index, index), "mark": mark,
           "mid": asset.get("midPx"), "oracle": asset.get("oraclePx"), "change_24h_pct": pct(mark, prev),
           "volume_24h_usd": rounded(num(asset.get("dayNtlVlm")), 2),
           "open_interest_usd": rounded(oi * num(mark), 2) if oi is not None and num(mark) else None,
           "funding_hourly": asset.get("funding"),
           "funding_apr_pct": rounded(funding * 24 * 365 * 100, 2) if funding is not None else None,
           "max_leverage": meta.get("maxLeverage"), "sz_decimals": sz_decimals,
           "price_decimals": 6 - sz_decimals if isinstance(sz_decimals, int) else None}
    if meta.get("onlyIsolated") or meta.get("marginMode"):
        row["margin"] = meta.get("marginMode") or "isolated only"
    if meta.get("isDelisted"):
        row["delisted"] = True
    return row


def _sort(rows: list[dict], key: str) -> list[dict]:
    if key not in SORTS:
        raise ChainError(f"sort is one of {', '.join(SORTS)}")
    if key == "name":
        return sorted(rows, key=lambda r: str(r["coin"]))
    field = {"volume": "volume_24h_usd", "oi": "open_interest_usd", "funding_abs": "funding_apr_pct",
             "change_abs": "change_24h_pct"}[key]
    return sorted(rows, key=lambda r: abs(r.get(field) or 0), reverse=True)


def markets(ctx, args) -> dict:
    dex = dex_arg(args)
    found = ctx.api.info({"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})})
    if not (isinstance(found, list) and len(found) == 2):
        raise ChainError(f"{ctx.api.label} returned an unexpected market listing")
    dex_index = ctx.dex_index(dex)
    rows = [_perp_row(dex_index, i, meta, asset)
            for i, (meta, asset) in enumerate(zip(found[0].get("universe", []), found[1]))]
    wanted = args.get("coin")
    if wanted:
        match = [r for r in rows if str(r["coin"]).upper() == str(wanted).upper()]
        if not match:
            raise ChainError(f"no perp {wanted!r} on {ctx.api.label}{f' dex {dex}' if dex else ''}")
        return {"network": ctx.network, "dex": dex, "market": match[0]}
    rows = [r for r in rows if not r.get("delisted")]
    limit = integer(args, "limit", 20, 1, 200)
    return {"network": ctx.network, "dex": dex, "count": len(rows),
            "markets": _sort(rows, args.get("sort") or "volume")[:limit]}


def spots(ctx, args) -> dict:
    rows = []
    for pair in ctx.spot_pairs():
        c = pair["ctx"]
        sz_decimals = pair["sz_decimals"]
        rows.append({"coin": ticker(pair["coin"]), "pair": ticker(f"{pair['base']}/{pair['quote']}"),
                     "asset": SPOT_OFFSET + pair["index"] if isinstance(pair["index"], int) else None,
                     "mark": c.get("markPx"), "mid": c.get("midPx"), "change_24h_pct": pct(c.get("markPx"), c.get("prevDayPx")),
                     "volume_24h_usd": rounded(num(c.get("dayNtlVlm")), 2), "sz_decimals": sz_decimals,
                     "price_decimals": 8 - sz_decimals if isinstance(sz_decimals, int) else None,
                     "full_name": stranger(pair["base_full_name"])})
    wanted = args.get("coin")
    if wanted:
        name = ctx.spot_coin(str(wanted))
        return {"network": ctx.network, "market": next(r for r in rows if r["coin"] == ticker(name))}
    limit = integer(args, "limit", 20, 1, 200)
    sort = args.get("sort") or "volume"
    if sort in ("oi", "funding_abs"):
        raise ChainError("spot markets sort by volume, change_abs or name")
    rows = _sort(rows, sort)
    return {"network": ctx.network, "count": len(rows), "spots": rows[:limit],
            "note": "spot tokens are deployed by third parties; a pair shown as @N is traded under that name"}


def _candles(ctx, coin: str, interval: str, start: int, end: int) -> list[dict]:
    found = ctx.api.info({"type": "candleSnapshot",
                          "req": {"coin": coin, "interval": interval, "startTime": start, "endTime": end}})
    return found if isinstance(found, list) else []


def _interval(args: dict) -> str:
    interval = args.get("interval") or "1h"
    if interval not in INTERVALS:
        raise ChainError(f"interval is one of {', '.join(INTERVALS)}")
    return interval


def _candle_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"candles": 0}
    highs = [num(r.get("h")) for r in rows if num(r.get("h")) is not None]
    lows = [num(r.get("l")) for r in rows if num(r.get("l")) is not None]
    return {"candles": len(rows), "first_open": rows[0].get("o"), "last_close": rows[-1].get("c"),
            "change_pct": pct(rows[-1].get("c"), rows[0].get("o")), "high": max(highs) if highs else None,
            "low": min(lows) if lows else None,
            "base_volume": rounded(sum(num(r.get("v")) or 0 for r in rows), 6)}


def _candle_rows(rows: list[dict]) -> dict:
    return {"columns": ["t", "open", "high", "low", "close", "volume", "trades"],
            "rows": [[r.get("t"), r.get("o"), r.get("h"), r.get("l"), r.get("c"), r.get("v"), r.get("n")]
                     for r in rows]}


def candles(ctx, args) -> dict:
    coin = ctx.coin(coin_arg(args))
    interval = _interval(args)
    start, end = window(args, 24, 24 * 365)
    limit = integer(args, "limit", 100, 1, 500)
    rows = _candles(ctx, coin, interval, start, end)
    result = {"network": ctx.network, "coin": ticker(coin), "interval": interval,
              "window": {"start": iso(start), "end": iso(end)}, "summary": _candle_summary(rows),
              "shown": min(limit, len(rows)), "candles": _candle_rows(rows[-limit:]),
              "note": "only the most recent 5000 candles of an interval exist; t is the open time in ms"}
    if len(rows) >= CANDLES_MAX:
        result["unread"] = UNREAD_CANDLES
    return result


def _funding(ctx, coin: str, start: int, end: int, pages: int = FUNDING_PAGES) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    cursor = start
    for _ in range(pages):
        page = ctx.api.info({"type": "fundingHistory", "coin": coin, "startTime": cursor, "endTime": end})
        page = page if isinstance(page, list) else []
        rows.extend(page)
        if len(page) < FUNDING_PAGE:
            return rows, True
        cursor = int(page[-1].get("time", end)) + 1
    return rows, cursor >= end


def _funding_summary(rows: list[dict]) -> dict:
    rates = [num(r.get("fundingRate")) for r in rows if num(r.get("fundingRate")) is not None]
    if not rates:
        return {"intervals": 0}
    mean = sum(rates) / len(rates)
    return {"intervals": len(rates), "mean_hourly": rounded(mean, 10), "mean_apr_pct": rounded(mean * 24 * 365 * 100, 2),
            "positive_share": rounded(sum(1 for r in rates if r > 0) / len(rates), 3),
            "latest_hourly": rows[-1].get("fundingRate")}


def funding(ctx, args) -> dict:
    coin = coin_arg(args)
    if is_spot(coin):
        raise ChainError("funding applies to perps only")
    start, end = window(args, 72, FUNDING_PAGE * FUNDING_PAGES)
    limit = integer(args, "limit", 100, 1, 500)
    rows, complete = _funding(ctx, coin, start, end)
    result = {"network": ctx.network, "coin": ticker(coin), "window": {"start": iso(start), "end": iso(end)},
              "summary": _funding_summary(rows), "shown": min(limit, len(rows)),
              "funding": {"columns": ["t", "rate_hourly", "premium"],
                          "rows": [[r.get("time"), r.get("fundingRate"), r.get("premium")] for r in rows[-limit:]]}}
    if not complete:
        result["unread"] = "the window holds more intervals than one read takes; shorten hours or move end_time"
    return result


def book(ctx, args) -> dict:
    coin = ctx.coin(coin_arg(args))
    levels = integer(args, "levels", 10, 1, 20)
    found = ctx.api.info({"type": "l2Book", "coin": coin})
    if not isinstance(found, dict) or not isinstance(found.get("levels"), list) or len(found["levels"]) != 2:
        raise ChainError(f"no order book for {coin!r} on {ctx.api.label}")
    bids, asks = ([{"px": l.get("px"), "sz": l.get("sz"), "orders": l.get("n")} for l in side[:levels]]
                  for side in found["levels"])
    best_bid, best_ask = (num(bids[0]["px"]) if bids else None), (num(asks[0]["px"]) if asks else None)
    result = {"network": ctx.network, "coin": ticker(coin), "time": iso(found.get("time")), "bids": bids, "asks": asks,
              "depth_usd": {"bids": rounded(sum(num(l["px"]) * num(l["sz"]) for l in bids), 2),
                            "asks": rounded(sum(num(l["px"]) * num(l["sz"]) for l in asks), 2)}}
    if best_bid and best_ask:
        mid = (best_bid + best_ask) / 2
        result.update({"mid": rounded(mid, 8), "spread_bps": rounded((best_ask - best_bid) / mid * 10_000, 3)})
    result["note"] = "a point-in-time snapshot of the shown levels"
    return result


# --- accounts -----------------------------------------------------------------------------------

# Account modes that keep one balance per asset for spot and every perp dex, held in the spot state:
# a perp dex's own account value and withdrawable mean nothing there, and the venue refuses spotSend
# and usdClassTransfer from them (sendAsset moves their funds).
UNIFIED = ("unifiedAccount", "portfolioMargin")
UNIFIED_NOTE = ("a unified account: spot and perp share one balance per asset, which balances shows; this dex's "
                "account value and withdrawable do not count it")


def abstraction(ctx, user: str) -> str:
    """The account's mode as the venue names it: default, disabled, unifiedAccount, portfolioMargin or
    dexAbstraction."""
    found = ctx.api.info({"type": "userAbstraction", "user": user})
    if not isinstance(found, str) or not found:
        raise ChainError(f"{ctx.api.label} returned an unexpected account mode")
    return found


def state(ctx, args) -> dict:
    user = address(args)
    dex = dex_arg(args)
    found = ctx.api.info({"type": "clearinghouseState", "user": user, **({"dex": dex} if dex else {})})
    if not isinstance(found, dict):
        raise ChainError(f"{ctx.api.label} returned an unexpected account state")
    mode = abstraction(ctx, user)
    positions = []
    for item in found.get("assetPositions", []):
        p = item.get("position") or {}
        size = num(p.get("szi")) or 0
        leverage = p.get("leverage") or {}
        positions.append({"coin": ticker(p.get("coin")),
                          "side": "long" if size > 0 else "short" if size < 0 else "flat",
                          "size": p.get("szi"), "entry": p.get("entryPx"), "value_usd": p.get("positionValue"),
                          "unrealized_pnl": p.get("unrealizedPnl"), "return_on_equity": p.get("returnOnEquity"),
                          "leverage": {"type": leverage.get("type"), "value": leverage.get("value")},
                          "liquidation": p.get("liquidationPx"), "margin_used": p.get("marginUsed"),
                          "max_leverage": p.get("maxLeverage"),
                          "funding_since_open": (p.get("cumFunding") or {}).get("sinceOpen")})
    summary = found.get("marginSummary") or {}
    cross = found.get("crossMarginSummary") or {}
    note = "perp positions and margin on this dex only; spot holdings are in balances"
    return {**ctx.account(user), "dex": dex, "time": iso(found.get("time")), "mode": mode,
            "account_value": summary.get("accountValue"), "margin_used": summary.get("totalMarginUsed"),
            "position_notional": summary.get("totalNtlPos"), "withdrawable": found.get("withdrawable"),
            "cross": {"account_value": cross.get("accountValue"), "margin_used": cross.get("totalMarginUsed"),
                      "maintenance_margin": found.get("crossMaintenanceMarginUsed")},
            "positions": positions,
            "note": f"positions on this dex; {UNIFIED_NOTE}" if mode in UNIFIED else note}


def balances(ctx, args) -> dict:
    user = address(args)
    found = ctx.api.info({"type": "spotClearinghouseState", "user": user})
    rows = [{"coin": ticker(b.get("coin")), "total": b.get("total"), "hold": b.get("hold"),
             "entry_notional": b.get("entryNtl")}
            for b in (found or {}).get("balances", []) if num(b.get("total"))]
    limit = integer(args, "limit", 50, 1, 200)
    mode = abstraction(ctx, user)
    note = "hold = committed to open spot orders"
    return {**ctx.account(user), "mode": mode, "count": len(rows), "balances": rows[:limit],
            "note": f"{note}; {UNIFIED_NOTE}" if mode in UNIFIED else note}


def _fills(ctx, user: str, start: int, end: int, aggregate: bool, latest: bool) -> tuple[list[dict], bool]:
    """(fills in the window, whether the window was read whole). Up to now (``latest``) one read of the
    account's newest fills covers it; a past window pages forward from its start, a few pages at most."""
    extra = {"aggregateByTime": True} if aggregate else {}
    if latest:
        found = ctx.api.info({"type": "userFills", "user": user, **extra})
        found = found if isinstance(found, list) else []
        rows = [f for f in found if start <= (f.get("time") or 0) <= end]
        complete = len(found) < FILLS_PAGE or min((f.get("time") or 0) for f in found) <= start
        return rows, complete
    rows: list[dict] = []
    seen: set = set()
    cursor = start
    for _ in range(FILLS_PAGES):
        page = ctx.api.info({"type": "userFillsByTime", "user": user, "startTime": cursor, "endTime": end, **extra})
        page = page if isinstance(page, list) else []
        for f in page:  # the next page starts at the last one's millisecond, so fills sharing it come twice
            key = (f.get("tid"), f.get("oid"), f.get("time"), f.get("sz"), f.get("px"))
            if key not in seen:
                seen.add(key)
                rows.append(f)
        if len(page) < FILLS_PAGE:
            return rows, True
        cursor = max((f.get("time") or 0) for f in page)
    return rows, False


def _fill_row(f: dict) -> dict:
    px, sz = num(f.get("px")), num(f.get("sz"))
    return {"time": iso(f.get("time")), "coin": ticker(f.get("coin")), "dir": f.get("dir"),
            "side": "buy" if f.get("side") == "B" else "sell", "px": f.get("px"), "sz": f.get("sz"),
            "notional_usd": rounded(px * sz, 4) if px is not None and sz is not None else None,
            "fee": f.get("fee"), "fee_token": ticker(f.get("feeToken")), "closed_pnl": f.get("closedPnl"),
            "taker": f.get("crossed"), "oid": f.get("oid"), "hash": f.get("hash")}


def fills(ctx, args) -> dict:
    user = address(args)
    start, end = window(args, 24, 24 * 90)
    limit = integer(args, "limit", 50, 1, 200)
    rows, complete = _fills(ctx, user, start, end, bool(args.get("aggregate")), args.get("end_time") is None)
    rows.sort(key=lambda f: f.get("time") or 0, reverse=True)
    result = {**ctx.account(user), "window": {"start": iso(start), "end": iso(end)},
              "count": len(rows), "fills": [_fill_row(f) for f in rows[:limit]],
              "note": "newest first; only the most recent 10000 fills of an account can be read"}
    if not complete:
        result["unread"] = UNREAD_FILLS
    return result


def _order_row(o: dict) -> dict:
    row = {"coin": ticker(o.get("coin")), "side": "buy" if o.get("side") == "B" else "sell", "type": o.get("orderType"),
           "price": o.get("limitPx"), "size": o.get("sz"), "original_size": o.get("origSz"),
           "reduce_only": o.get("reduceOnly"), "oid": o.get("oid"), "cloid": o.get("cloid"),
           "time": iso(o.get("timestamp"))}
    if o.get("isTrigger"):
        row.update({"trigger": o.get("triggerCondition"), "trigger_price": o.get("triggerPx"),
                    "position_tpsl": o.get("isPositionTpsl")})
    if o.get("tif"):
        row["tif"] = o["tif"]
    return row


def orders(ctx, args) -> dict:
    user = address(args)
    limit = integer(args, "limit", 50, 1, 200)
    oid = args.get("oid")
    if oid is not None:
        if isinstance(oid, str) and oid.isascii() and oid.isdigit():
            oid = int(oid)
        if not (isinstance(oid, int) and not isinstance(oid, bool)) and not (isinstance(oid, str) and _CLOID.match(oid)):
            raise ChainError("oid is an order id number or a 0x cloid of 32 hex digits")
        found = ctx.api.info({"type": "orderStatus", "user": user, "oid": oid})
        if not isinstance(found, dict) or found.get("status") != "order":
            return {**ctx.account(user), "oid": oid, "status": "unknown order"}
        entry = found.get("order") or {}
        return {**ctx.account(user), "status": entry.get("status"),
                "status_time": iso(entry.get("statusTimestamp")), "order": _order_row(entry.get("order") or {})}
    if args.get("history"):
        found = ctx.api.info({"type": "historicalOrders", "user": user})
        rows = [{**_order_row(e.get("order") or {}), "status": e.get("status"), "status_time": iso(e.get("statusTimestamp"))}
                for e in (found if isinstance(found, list) else [])]
        return {**ctx.account(user), "count": len(rows), "orders": rows[:limit],
                "note": "recent orders only, newest first; not a full archive"}
    dex = dex_arg(args)
    found = ctx.api.info({"type": "frontendOpenOrders", "user": user, **({"dex": dex} if dex else {})})
    rows = [_order_row(o) for o in (found if isinstance(found, list) else [])]
    return {**ctx.account(user), "dex": dex, "count": len(rows), "open_orders": rows[:limit]}


# --- review and export --------------------------------------------------------------------------

def _review_interval(hours: int) -> str:
    return "1h" if hours <= 48 else "4h" if hours <= 24 * 14 else "1d"


LONG_DIRS = ("Close Long", "Long > Short")
SHORT_DIRS = ("Close Short", "Short > Long")


def review(ctx, args) -> dict:
    user = address(args)
    start, end = window(args, 72, 24 * 30)
    limit = integer(args, "fills", 500, 1, FILLS_PAGE)
    wanted = ctx.coin(coin_arg(args)) if args.get("coin") else None  # a spot pair's fills carry its @N name
    rows, complete = _fills(ctx, user, start, end, False, args.get("end_time") is None)
    if wanted:
        rows = [f for f in rows if str(f.get("coin")).upper() == wanted.upper()]
    rows.sort(key=lambda f: f.get("time") or 0, reverse=True)
    capped = len(rows) > limit
    rows = rows[:limit]
    coins: dict[str, dict] = defaultdict(lambda: {"fills": 0, "volume_usd": 0.0, "closed_pnl": 0.0, "fees_usdc": 0.0,
                                                  "wins": 0, "losses": 0, "long_losses": 0.0, "short_losses": 0.0})
    other_fees: dict[str, float] = defaultdict(float)
    for f in rows:
        c = coins[f.get("coin")]
        px, sz, pnl, fee = (num(f.get(k)) or 0 for k in ("px", "sz", "closedPnl", "fee"))
        c["fills"] += 1
        c["volume_usd"] += px * sz
        c["closed_pnl"] += pnl
        if f.get("feeToken") in (None, "USDC"):
            c["fees_usdc"] += fee
        else:
            other_fees[f.get("feeToken")] += fee
        if pnl > 0:
            c["wins"] += 1
        elif pnl < 0:
            c["losses"] += 1
            if f.get("dir") in LONG_DIRS:
                c["long_losses"] += pnl
            elif f.get("dir") in SHORT_DIRS:
                c["short_losses"] += pnl
    total_pnl = sum(c["closed_pnl"] for c in coins.values())
    total_fees = sum(c["fees_usdc"] for c in coins.values())
    total_volume = sum(c["volume_usd"] for c in coins.values())
    interval = _review_interval((end - start) // HOUR_MS)
    traded = sorted((k for k in coins if not is_spot(str(k))), key=lambda k: -coins[k]["volume_usd"])
    context, unread = {}, []
    for coin in traded[:REVIEW_COINS]:
        try:
            trend = _candle_summary(_candles(ctx, coin, interval, start, end))
            funding_rows, funding_complete = _funding(ctx, coin, start, end)
            funded = _funding_summary(funding_rows)
        except ChainError as exc:
            unread.append({"coin": ticker(coin), "error": str(exc)})
            continue
        if not funding_complete:
            unread.append({"coin": ticker(coin), "error": "mean funding covers only the start of the window"})
        context[coin] = {"trend_pct": trend.get("change_pct"), "interval": interval,
                         "mean_funding_apr_pct": funded.get("mean_apr_pct")}
    unread += [{"coin": ticker(coin), "error": "market context limited to the most traded perps"}
               for coin in traded[REVIEW_COINS:]]
    if not complete:
        unread.append({"fills": UNREAD_FILLS})
    elif capped:
        unread.append({"fills": f"only the newest {limit} fills of the window were reviewed; raise fills or shorten hours"})
    findings = []
    if total_fees and total_pnl > 0 and total_fees > total_pnl * 0.3:
        findings.append({"finding": "fees took a large share of the realized profit",
                         "evidence": {"fees_usdc": rounded(total_fees, 4), "closed_pnl": rounded(total_pnl, 4)}})
    if total_fees and total_pnl <= 0 and total_fees > abs(total_pnl) * 0.3:
        findings.append({"finding": "fees added substantially to the realized loss",
                         "evidence": {"fees_usdc": rounded(total_fees, 4), "closed_pnl": rounded(total_pnl, 4)}})
    if total_volume and len(coins) > 1:
        top = max(coins, key=lambda k: coins[k]["volume_usd"])
        share = coins[top]["volume_usd"] / total_volume
        if share > 0.7:
            findings.append({"finding": "volume was concentrated in one market",
                             "evidence": {"coin": ticker(top), "volume_share": rounded(share, 3)}})
    for coin, info in context.items():
        trend = info.get("trend_pct")
        c = coins[coin]
        if trend is not None and trend < -2 and c["long_losses"] < 0:
            findings.append({"finding": "longs closed at a loss while the market fell",
                             "evidence": {"coin": ticker(coin), "trend_pct": trend,
                                          "long_losses": rounded(c["long_losses"], 4)}})
        if trend is not None and trend > 2 and c["short_losses"] < 0:
            findings.append({"finding": "shorts closed at a loss while the market rose",
                             "evidence": {"coin": ticker(coin), "trend_pct": trend,
                                          "short_losses": rounded(c["short_losses"], 4)}})
    breakdown = []
    for coin, c in sorted(coins.items(), key=lambda kv: -kv[1]["volume_usd"]):
        breakdown.append({"coin": ticker(coin), "fills": c["fills"], "volume_usd": rounded(c["volume_usd"], 2),
                          "closed_pnl": rounded(c["closed_pnl"], 4), "fees_usdc": rounded(c["fees_usdc"], 4),
                          "net": rounded(c["closed_pnl"] - c["fees_usdc"], 4), "wins": c["wins"], "losses": c["losses"],
                          **({"market": context[coin]} if coin in context else {})})
    result = {**ctx.account(user), "window": {"start": iso(start), "end": iso(end)},
              "fills": len(rows), "closed_pnl": rounded(total_pnl, 4), "fees_usdc": rounded(total_fees, 4),
              "net": rounded(total_pnl - total_fees, 4), "volume_usd": rounded(total_volume, 2),
              "wins": sum(c["wins"] for c in coins.values()), "losses": sum(c["losses"] for c in coins.values()),
              "coins": breakdown, "findings": findings,
              "note": "heuristics from fills alone: they cannot see intent, order placement or true slippage; "
                      "judge decisions apart from outcomes"}
    if other_fees:
        result["fees_other"] = {str(k): rounded(v, 8) for k, v in other_fees.items()}
    if unread:
        result["unread"] = unread
    return result


def export(ctx, args) -> dict:
    coin = ctx.coin(coin_arg(args))
    interval = _interval(args)
    start, end = window(args, 168, 24 * 365)
    candle_rows = _candles(ctx, coin, interval, start, end)
    if len(candle_rows) > 500:
        raise ChainError(f"{len(candle_rows)} candles; at most 500 per export: a longer interval or fewer hours")
    result = {"schema": EXPORT_SCHEMA,
              "source": {"venue": "hyperliquid", "network": ctx.network, "coin": ticker(coin), "interval": interval,
                         "endpoints": ["candleSnapshot"] + ([] if is_spot(coin) else ["fundingHistory"])},
              "window": {"start_ms": start, "end_ms": end, "start": iso(start), "end": iso(end)},
              "candles": _candle_rows(candle_rows), "summary": {"candles": _candle_summary(candle_rows)},
              "note": "a normalized dataset, not a backtest: bring your own fill and slippage model"}
    if not is_spot(coin):
        rows, complete = _funding(ctx, coin, start, end)
        result["funding"] = {"columns": ["t", "rate_hourly", "premium"],
                             "rows": [[r.get("time"), r.get("fundingRate"), r.get("premium")] for r in rows]}
        result["summary"]["funding"] = _funding_summary(rows)
        if not complete:
            result["unread"] = "funding beyond the first rows of the window was not read; shorten hours"
    return result


# --- backtests ----------------------------------------------------------------------------------

BACKTEST_BARS_MAX = 25_000   # bars one backtest trades over, both sources together
VENUE_PAGE = 500             # candles asked for per candleSnapshot request
BACKTEST_FUNDING_PAGES = 8   # the newest 4000 hours of funding are read; older hours take their mean
LONG_HISTORY = {"label": "Binance spot", "api": "https://data-api.binance.vision", "page": 1000}
_LONG_COIN = re.compile(r"^[A-Z0-9]{2,10}$")


def _venue_candles(ctx, coin: str, interval: str, start: int, end: int) -> list[dict]:
    """The venue's candles over a window, in pages; only its newest 5000 exist."""
    step = hl_strategy.INTERVAL_MS[interval]
    cursor, rows = max(start, end - CANDLES_MAX * step), []
    while cursor < end:
        upper = min(end, cursor + VENUE_PAGE * step)
        rows.extend(_candles(ctx, coin, interval, cursor, upper - 1))
        cursor = upper
    return rows


def _long_candles(payload: dict, coin: str, interval: str, start: int, end: int) -> tuple[list[dict], str | None]:
    """Older candles of the same coin's USDT pair from Binance's public market data, for the years
    before the venue's own 5000 candles: (rows, what could not be read, or None). Prices only."""
    label = LONG_HISTORY["label"]
    if not _LONG_COIN.match(coin):
        return [], f"{label} has no history mapped for {coin}; only the venue's own candles were used"
    base = payload.get("_long") if payload.get("_long") and rpc.testing() else LONG_HISTORY["api"]
    step = hl_strategy.INTERVAL_MS[interval]
    symbol, cursor, rows = f"{coin}USDT", start, []
    while cursor < end and len(rows) < BACKTEST_BARS_MAX:
        query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "startTime": cursor,
                                        "endTime": end - 1, "limit": LONG_HISTORY["page"]})
        request = urllib.request.Request(f"{base}/api/v3/klines?{query}",
                                         headers={"Accept": "application/json", "User-Agent": rpc.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                page = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                return rows, f"{label} has no {symbol}; only the venue's own candles were used"
            return rows, f"{label} refused the history (HTTP {exc.code}); only part of it was read"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return rows, f"{label} could not be reached; only part of the older history was read"
        if not isinstance(page, list) or not page:
            break
        rows.extend({"t": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in page
                    if isinstance(r, list) and len(r) >= 5)
        last = page[-1][0] if isinstance(page[-1], list) and isinstance(page[-1][0], int) else None
        if last is None or last < cursor:
            break
        cursor = last + step
    return rows, None


def _backtest_args(args: dict) -> dict:
    try:
        rule_set = hl_strategy.rules(args.get("rules"))
        out = {"rules": rule_set, "costs": hl_strategy.costs(args.get("costs")),
               "limits": hl_strategy.backtest_limits(args.get("limits")),
               "stance": hl_strategy.timeline(args.get("stance"))}
    except hl_strategy.StrategyError as exc:
        raise ChainError(str(exc)) from None
    direction = args.get("direction") or "both"
    if direction not in hl_strategy.DIRECTIONS:
        raise ChainError(f"direction is one of {', '.join(hl_strategy.DIRECTIONS)}")
    long_history = args.get("long_history", False)
    if not isinstance(long_history, bool):
        raise ChainError("long_history is true (older Binance spot candles of the coin's USDT pair before the "
                         "venue's own) or false")
    history = "long" if long_history else "venue"
    interval = args.get("interval") or "4h"
    if interval not in hl_strategy.INTERVAL_MS:
        raise ChainError(f"a backtest's interval is one of {', '.join(hl_strategy.INTERVAL_MS)}")
    return {**out, "direction": direction, "history": history, "interval": interval}


def backtest(ctx, args) -> dict:
    """Trade a rule set over past candles with fees, slippage and funding, optionally walking forward:
    the same signal the cron gate reads (hl_strategy.py). A result, not a forecast."""
    coin = coin_arg(args)
    if is_spot(coin) or ":" in coin or not hl_strategy._COIN.match(coin):
        raise ChainError("a backtest takes a main-dex perp by its ticker, like BTC")
    spec = _backtest_args(args)
    interval, step = spec["interval"], hl_strategy.INTERVAL_MS[spec["interval"]]
    end = window({"end_time": args.get("end_time")}, 1, 1)[1]
    unread: list[str] = []
    if args.get("hours") is not None:
        start = end - integer(args, "hours", 1, 24, 24 * 365 * 10) * HOUR_MS
    else:
        start = end - (BACKTEST_BARS_MAX if spec["history"] == "long" else CANDLES_MAX) * step
    if (end - start) // step > BACKTEST_BARS_MAX:
        start = end - BACKTEST_BARS_MAX * step
        unread.append(f"at most {BACKTEST_BARS_MAX} bars are traded: the window starts at {iso(start)}")
    venue_rows = hl_strategy.bars(_venue_candles(ctx, coin, interval, start, end), interval, end)
    if spec["history"] == "venue" and start < end - CANDLES_MAX * step:
        unread.append(UNREAD_CANDLES + ", or long_history")
    long_rows: list[dict] = []
    first_venue = venue_rows[0]["t"] if venue_rows else end
    if spec["history"] == "long" and start < first_venue:
        raw, problem = _long_candles(args, coin, interval, start, first_venue)
        long_rows = [b for b in hl_strategy.bars(raw, interval, end) if b["t"] < first_venue]
        if problem:
            unread.append(problem)
    series = long_rows + venue_rows
    if len(series) < hl_strategy.warmup(spec["rules"]) + 50:
        raise ChainError(f"{len(series)} completed {interval} bars of {coin} on {ctx.api.label}: too few for these "
                         "rules; a longer window, a shorter interval or long_history")
    rows, _ = _funding(ctx, coin, max(start, end - BACKTEST_FUNDING_PAGES * FUNDING_PAGE * HOUR_MS), end,
                       BACKTEST_FUNDING_PAGES)
    funding = {}
    for r in rows:
        rate, t = num(r.get("fundingRate")), r.get("time")
        if rate is not None and isinstance(t, int):
            funding[t - t % HOUR_MS] = rate
    mean = sum(funding.values()) / len(funding) if funding else hl_strategy.BASELINE_FUNDING
    rates = hl_strategy.funding_by_bar(series, interval, funding, mean, spec["costs"]["funding"])
    cost, limits, rule_set = spec["costs"], spec["limits"], spec["rules"]
    try:
        run = hl_strategy.simulate(series, rule_set, interval, cost, limits, rates=rates, stance=spec["stance"],
                                   direction=spec["direction"])
        walked = None
        if args.get("walk_forward") is not None:
            walked = hl_strategy.walk_forward(series, rule_set, interval, cost, limits, args["walk_forward"],
                                              rates=rates, stance=spec["stance"], direction=spec["direction"])
    except hl_strategy.StrategyError as exc:
        raise ChainError(str(exc)) from None
    sources = []
    if long_rows:
        sources.append({"source": f"{LONG_HISTORY['label']} {coin}USDT (prices only)", "bars": len(long_rows),
                        "start": iso(long_rows[0]["t"]), "end": iso(long_rows[-1]["t"])})
    if venue_rows:
        sources.append({"source": f"{ctx.api.label} {coin}", "bars": len(venue_rows),
                        "start": iso(venue_rows[0]["t"]), "end": iso(venue_rows[-1]["t"])})
    assumed = run["totals"]["assumed_hours"]
    result = {"schema": hl_strategy.BACKTEST_SCHEMA, "network": ctx.network, "coin": coin, "interval": interval,
              "rules": rule_set, "fingerprint": hl_strategy.fingerprint(rule_set, interval), "costs": cost,
              "limits": limits, "direction": spec["direction"], "stance_windows": len(spec["stance"]),
              "data": {"bars": len(series), "start": iso(series[0]["t"]), "end": iso(series[-1]["t"]),
                       "end_ms": end, "sources": sources,
                       "funding": {"hours_read": len(funding), "mean_hourly": hl_strategy.sig5(abs(mean)) if mean else "0",
                                   "mean_sign": "longs pay" if mean > 0 else "shorts pay" if mean < 0 else "none",
                                   "hours_assumed_while_held": assumed, "mode": cost["funding"]}},
              "result": hl_strategy.metrics(run),
              "trades": {"count": len(run["trades"]), "newest": run["trades"][-hl_strategy.TRADES_SHOWN:]},
              "equity": hl_strategy.curve_points(run["curve"]),
              "note": ("a simulation on past bars from a notional 1000 USDC (fees_pct and funding_pct are of that "
                       "start): fills at the next bar's open with slippage and the taker fee, stops inside a bar "
                       "at the stop or a gapped open; neither a forecast nor a fill guarantee. A strategy may run "
                       "this rule set on this interval only under its fingerprint.")}
    if walked is not None:
        result["walk_forward"] = walked
    if assumed:
        unread.append(f"{assumed} held hours had no venue funding read and took the mean rate")
    if unread:
        result["unread"] = unread
    return result


def deposit_info(ctx, args) -> dict:
    """How USDC enters the venue: Circle's CCTP from the network's chains, from the chain table; no request
    is made."""
    testnet = ctx.network == "testnet"
    sources = [c for c in chains.CCTP_USDC if chains.EVM[c]["testnet"] == testnet]
    note = ("the evm tool's quote with kind deposit (account, chain, amount; to = the Hyperliquid account, default "
            "the sender's own; dex = perp or spot) builds it in two transactions, an approval of exactly the amount "
            "and then the burn, each sent with transfer; Circle's fee (about 0.2 USDC, more from Ethereum) comes off "
            "the amount and the account is credited within about a minute. Hyperliquid's legacy bridge is never "
            "used: the evm tool refuses anything sent to it")
    if testnet:
        note += (f"; on testnet Circle credits only accounts that exist on Hyperliquid mainnet, at most "
                 f"{chains.HYPERLIQUID_TESTNET_DEPOSIT_CAP} USDC, and the quote refuses others")
    return {"network": ctx.network, "route": "Circle CCTP", "from_chains": sources,
            "usdc": {c: chains.CCTP_USDC[c] for c in sources}, "note": note}


ACTIONS = {"deposit_info": deposit_info, "dexs": dexs, "markets": markets, "spots": spots, "candles": candles, "funding": funding, "book": book,
           "state": state, "balances": balances, "fills": fills, "orders": orders, "review": review, "export": export,
           "backtest": backtest}


def run(payload: dict) -> dict:
    action, network = payload.get("action"), payload.get("network")
    if network not in NETWORKS:
        raise ChainError(f"network is one of {', '.join(NETWORKS)}")
    if action not in ACTIONS:
        raise ChainError(f"{action!r} is not a Hyperliquid read; use one of: {', '.join(ACTIONS)}")
    return ACTIONS[action](Ctx(network, payload), payload)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ChainError("the request must be a JSON object")
        reply = {"ok": True, "data": run(payload)}
    except ChainError as exc:
        reply = {"ok": False, "error": rpc.mask(exc)}
    except Exception as exc:  # an engine bug or an unexpected reply: say what, never where
        reply = {"ok": False, "error": rpc.mask(f"{type(exc).__name__}: {exc}")[:500]}
    sys.stdout.write(rpc.mask(json.dumps(reply, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
