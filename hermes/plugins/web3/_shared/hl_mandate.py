"""Hyperliquid mandates: bounds the user approved once, inside which orders run without a card
(docs/hyperliquid.md "Mandates", docs/decisions/hyperliquid-mandates.md). Used by the trader in the
web3 venv.

A mandate names one Hermes account on one network, a list of perp markets, the most one order may be
worth, the most the account may hold in those markets (positions and every order that is not
reduce-only, triggers included), the highest leverage, how many orders an hour, and when it ends (at
most ``MAX_DAYS``, the moment its card showed). It is made only through its own approval card (a quote
of kind ``mandate``) and stored under an HMAC keyed from the account's secret.

Which mandate is in force for an account and network is one MAC'd head file, never the event log:
creating writes the new id there (replacing the one before), revoking writes none, and ``current``
trusts only the head. The event log (``hl-mandates.jsonl``) is history for listing. ``fits`` reads
the account as it is now, values every order conservatively and fails closed on any read it cannot
make; the trader asks it at verify and again under the wallet lock at submit. A mandate never covers
spot, margin taken out, withdrawals or sends, or another mandate.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets as random

import hl
import ledger
import signer
from rpc import ChainError

MANDATES = "hl-mandates"
EVENTS = "hl-mandates.jsonl"
MANDATE_ID = re.compile(r"^m[0-9a-f]{8}$")
MAX_DAYS = 30
MAX_MARKETS = 20
MAX_PER_HOUR = 30
MIN_ORDER = Decimal("10")
DAY = 86400
COVERED = ("order", "modify", "leverage")  # the kinds a mandate may approve; anything else needs its card


def _positive(payload: dict, key: str) -> Decimal:
    value = payload.get(key)
    try:
        number = Decimal(str(value).strip())
    except Exception:
        raise ChainError(f"{key} is required: a USDC amount like 200") from None
    if not number.is_finite() or number <= 0:
        raise ChainError(f"{key} must be above zero")
    return number.normalize()


def _whole(payload: dict, key: str, low: int, high: int) -> int:
    value = payload.get(key)
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ChainError(f"{key} is a whole number from {low} to {high}")
    return value


def build(payload: dict, resolve) -> dict:
    """The mandate's terms from a quote's arguments; ``resolve`` turns a coin into its market (or
    raises), so every market named exists on the network and is a perp."""
    markets = payload.get("markets")
    if not isinstance(markets, list) or not markets or len(markets) > MAX_MARKETS:
        raise ChainError(f"markets is a list of 1 to {MAX_MARKETS} perps, like [\"BTC\", \"ETH\"]")
    coins = []
    for coin in markets:
        mkt = resolve(coin)
        if mkt["spot"]:
            raise ChainError("a mandate covers perps only; spot orders always ask on their card")
        if mkt["coin"] not in coins:
            coins.append(mkt["coin"])
    max_order = _positive(payload, "max_order_usd")
    if max_order < MIN_ORDER:
        raise ChainError(f"max_order_usd is at least {MIN_ORDER}, the venue's minimum order")
    max_exposure = _positive(payload, "max_exposure_usd")
    if max_exposure < max_order:
        raise ChainError("max_exposure_usd is at least max_order_usd")
    purpose = signer.one_line(payload.get("purpose"), 120)
    if not purpose:
        raise ChainError("purpose is required: one line on what the mandate is for")
    return {"markets": coins, "max_order_usd": signer.plain(max_order), "max_exposure_usd": signer.plain(max_exposure),
            "max_leverage": _whole(payload, "max_leverage", 1, 50),
            "per_hour": _whole(payload, "per_hour", 1, MAX_PER_HOUR), "days": _whole(payload, "days", 1, MAX_DAYS),
            "purpose": purpose}


def until(quote: dict) -> float:
    """The mandate's end: the moment its card shows, counted from the quote."""
    return quote["created"] + quote["built"]["days"] * DAY


# --- cards --------------------------------------------------------------------------------------

def _when(moment: float) -> str:
    return datetime.fromtimestamp(moment).astimezone().strftime("%Y-%m-%d %H:%M UTC%z")


def _lines(quote: dict) -> list[str]:
    terms = quote["built"]
    lines = [f"Hyperliquid {'testnet' if quote['network'] == 'testnet' else 'MAINNET'} · MANDATE: orders without a card",
             f"Markets: {', '.join(terms['markets'])} (perps)",
             f"Per order: up to {terms['max_order_usd']} USDC · held in total: up to {terms['max_exposure_usd']} USDC",
             f"Leverage: up to {terms['max_leverage']}x · at most {terms['per_hour']} orders an hour",
             f"Until: {_when(until(quote))} ({terms['days']} day{'' if terms['days'] == 1 else 's'})",
             f"Purpose: {terms['purpose']}"]
    if terms.get("replaces"):
        lines.append(f"Replaces: {terms['replaces']}")
    return lines


def _short(quote: dict) -> str:
    """Every term that decides, in Discord's budget: the purpose is the one line it leaves out."""
    terms = quote["built"]
    net = "testnet" if quote["network"] == "testnet" else "MAINNET"
    lines = [f"Hyperliquid {net} MANDATE: orders without a card", f"Perps: {','.join(terms['markets'])}",
             f"Order ≤{terms['max_order_usd']} · total ≤{terms['max_exposure_usd']} USDC · ≤{terms['max_leverage']}x"
             f" · {terms['per_hour']}/h", f"Until {_when(until(quote))}",
             f"Account {signer.one_line(quote['account'], 40)}: {quote['from']}"]
    if terms.get("replaces"):
        lines.append(f"Replaces {terms['replaces']}")
    lines.append(f"Quote {quote['id']}")
    return "\n".join(lines)


def cards(quote: dict) -> tuple[str, str]:
    """(detailed, compact). Both carry every bound; a mandate whose compact card does not fit is
    refused rather than shown in part."""
    short = _short(quote)
    if signer.card_units(short) > signer.SHORT_BUDGET:
        raise ChainError("this mandate's terms do not fit on an approval card; name fewer markets")
    expires = datetime.fromtimestamp(quote["expires"]).astimezone().strftime("%H:%M UTC%z")
    for drop in ((), ("memo",)):
        text = "\n".join([*_lines(quote), f"Quote: {quote['id']} · expires {expires}", "", "--- Account ---",
                          *signer._party_lines(quote["from_party"], quote["from"], drop)])
        if signer.card_units(text) <= signer.CARD_BUDGET:
            return text, short
    return short, short


# --- storage ------------------------------------------------------------------------------------

def _mac(secrets_, body: dict, venue: str) -> str:
    return secrets_.mac({**{k: v for k, v in body.items() if k != "mac"}, "venue": venue})


def _dir(state: Path) -> Path:
    path = state / MANDATES
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def _write(path: Path, body: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read(path: Path) -> dict:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ChainError("a mandate file could not be read") from None
    if not isinstance(body, dict):
        raise ChainError("a mandate file holds something else")
    return body


def _head_path(state: Path, account: str, network: str) -> Path:
    key = hashlib.sha256(f"{account}\x00{network}".encode()).hexdigest()[:16]
    return _dir(state) / f"head-{key}.json"


def _set_head(state: Path, secrets_, account: str, network: str, mandate_id: str | None, now: float) -> None:
    source, _ = secrets_.account(account)
    head = {"account": account, "network": network, "source": source, "mandate": mandate_id, "time": now}
    head["mac"] = _mac(secrets_, head, "hyperliquid-mandate-head")
    _write(_head_path(state, account, network), head)


def _head(state: Path, secrets_, account: str, network: str) -> str | None:
    """The mandate id the account's authentic head names on a network, or None."""
    path = _head_path(state, account, network)
    if not path.exists():
        return None
    try:
        head = _read(path)
        if not isinstance(head.get("source"), str):
            return None
        if head["source"] not in secrets_.seeds and head["source"] not in secrets_.keys:
            return None
        if head.get("account") != account or head.get("network") != network:
            return None
        if not hmac.compare_digest(str(head.get("mac")), _mac(secrets_, head, "hyperliquid-mandate-head")):
            return None
    except (ChainError, KeyError, TypeError):
        return None
    mandate_id = head.get("mandate")
    return mandate_id if isinstance(mandate_id, str) and MANDATE_ID.match(mandate_id) else None


def _events(state: Path) -> list[dict]:
    path = state / EVENTS
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and MANDATE_ID.match(str(row.get("mandate", ""))):
            rows.append(row)
    return rows


def create(state: Path, secrets_, quote: dict, now: float) -> dict:
    """Store an approved mandate and make it the account's on that network, replacing the one before.
    Called under the wallet lock; refused when the mandate in force changed since the card showed."""
    terms = quote["built"]
    before = current(state, secrets_, quote["account"], quote["network"], now)
    if (before["id"] if before else None) != terms.get("replaces"):
        raise ChainError("the mandate in force changed since this card was shown; make a new mandate quote")
    mandate = {"id": "m" + random.token_hex(4), "created": now, "expires": until(quote),
               "account": quote["account"], "source": quote["source"], "from": quote["from"],
               "network": quote["network"], "quote": quote["id"],
               **{k: terms[k] for k in ("markets", "max_order_usd", "max_exposure_usd", "max_leverage", "per_hour",
                                        "purpose")}}
    if mandate["expires"] <= now:
        raise ChainError("this mandate would already have ended; make a new mandate quote")
    mandate["mac"] = _mac(secrets_, mandate, "hyperliquid-mandate")
    fd = os.open(_dir(state) / f"{mandate['id']}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(mandate, handle, ensure_ascii=False)
    _set_head(state, secrets_, quote["account"], quote["network"], mandate["id"], now)
    if before:
        ledger.append(state, {"time": now, "mandate": before["id"], "event": "replaced", "by": mandate["id"]}, EVENTS)
    ledger.append(state, {"time": now, "mandate": mandate["id"], "event": "active", "account": quote["account"],
                          "network": quote["network"]}, EVENTS)
    return mandate


def load(state: Path, secrets_, mandate_id) -> dict:
    if not isinstance(mandate_id, str) or not MANDATE_ID.match(mandate_id):
        raise ChainError("mandate must be an id like m1a2b3c4d from mandates")
    path = state / MANDATES / f"{mandate_id}.json"
    if not path.exists():
        raise ChainError(f"no mandate {mandate_id}")
    mandate = _read(path)
    if mandate.get("id") != mandate_id:
        raise ChainError("this mandate file holds another mandate; it is refused")
    if not all(isinstance(mandate.get(k), str) for k in ("source", "account", "network", "mac")):
        raise ChainError("this mandate file is not a mandate; it is refused")
    if mandate["source"] not in secrets_.seeds and mandate["source"] not in secrets_.keys:
        raise ChainError("this mandate's seed phrase or key is no longer in the Keychain")
    if not hmac.compare_digest(str(mandate.get("mac")), _mac(secrets_, mandate, "hyperliquid-mandate")):
        raise ChainError("this mandate was changed after it was approved; it is refused")
    return mandate


def current(state: Path, secrets_, account: str, network: str, now: float) -> dict | None:
    """The mandate the account's head names on a network, when it is authentic, its own and unexpired."""
    mandate_id = _head(state, secrets_, account, network)
    if mandate_id is None:
        return None
    try:
        mandate = load(state, secrets_, mandate_id)
        if mandate["account"] != account or mandate["network"] != network or now >= float(mandate["expires"]):
            return None
    except (ChainError, KeyError, TypeError, ValueError):
        return None
    return mandate


def revoke(state: Path, secrets_, mandate_id, now: float) -> str:
    """Revoke at once (under the wallet lock). A mandate no longer in force stays as it is."""
    mandate = load(state, secrets_, mandate_id)
    if _head(state, secrets_, mandate["account"], mandate["network"]) != mandate_id:
        return "not in force"
    _set_head(state, secrets_, mandate["account"], mandate["network"], None, now)
    ledger.append(state, {"time": now, "mandate": mandate_id, "event": "revoked"}, EVENTS)
    return "revoked"


def _in_force(state: Path, secrets_) -> list[str]:
    """Every mandate an authentic head names now, found from the heads themselves, so a mandate in
    force is always listed (and can be revoked) even when the history is gone."""
    found = []
    for path in sorted(_dir(state).glob("head-*.json")):
        try:
            head = _read(path)
            mandate_id = _head(state, secrets_, head.get("account"), head.get("network"))
        except (ChainError, TypeError, ValueError):
            continue
        if mandate_id and mandate_id not in found:
            found.append(mandate_id)
    return found


def listing(state: Path, secrets_, now: float, account=None, network=None) -> list[dict]:
    seen: list[str] = []
    ended: dict[str, str] = {}
    for row in _events(state):
        if row.get("event") == "active" and row["mandate"] not in seen:
            seen.append(row["mandate"])
        elif row.get("event") in ("revoked", "replaced"):
            ended.setdefault(row["mandate"], row["event"])
    seen += [m for m in _in_force(state, secrets_) if m not in seen]
    rows = []
    for mandate_id in reversed(seen):
        try:
            mandate = load(state, secrets_, mandate_id)
        except Exception as exc:  # one broken file never hides the others
            problem = str(exc) if isinstance(exc, ChainError) else "the mandate file could not be read"
            rows.append({"mandate": mandate_id, "standing": "unreadable", "problem": problem})
            continue
        if account and mandate["account"] != account or network and mandate["network"] != network:
            continue
        try:
            in_force = current(state, secrets_, mandate["account"], mandate["network"], now)
            if in_force and in_force["id"] == mandate_id:
                standing = "active"
            elif now >= float(mandate["expires"]) and mandate_id not in ended:
                standing = "expired"
            else:
                standing = ended.get(mandate_id, "not in force")
            rows.append({"mandate": mandate_id, "standing": standing, "account": mandate["account"],
                         "network": mandate["network"], "markets": mandate["markets"],
                         "max_order_usd": mandate["max_order_usd"], "max_exposure_usd": mandate["max_exposure_usd"],
                         "max_leverage": mandate["max_leverage"], "per_hour": mandate["per_hour"],
                         "used_this_hour": used(state, mandate_id, now), "purpose": mandate["purpose"],
                         "until": datetime.fromtimestamp(float(mandate["expires"])).astimezone()
                         .isoformat(timespec="minutes")})
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            rows.append({"mandate": mandate_id, "standing": "unreadable", "problem": "the mandate file is malformed"})
    return rows


def used(state: Path, mandate_id: str, now: float) -> int:
    return sum(1 for row in ledger.entries(state, now - ledger.HOUR, "hyperliquid.jsonl")
               if row.get("mandate") == mandate_id and row.get("outcome") in ledger.COUNTED)


# --- fitting ------------------------------------------------------------------------------------

def _order_value(order: dict) -> Decimal:
    """A resting order's worth: its size at the highest of its limit and trigger prices."""
    size = Decimal(str(order.get("sz") or "0"))
    prices = [Decimal(str(order.get(k))) for k in ("limitPx", "triggerPx") if order.get(k) not in (None, "")]
    return abs(size) * max(prices or [Decimal(0)])


def exposure(ctx: hl.Ctx, user: str, coins: list[str]) -> tuple[Decimal, dict]:
    """(what the account holds in these markets now, each counted open order's value by oid): every
    position's value and every order that is not reduce-only — triggers included — on every dex they
    trade on. A reply of an unexpected shape raises."""
    total = Decimal(0)
    counted: dict = {}
    for dex in sorted({c.split(":", 1)[0] if ":" in c else "" for c in coins}):
        extra = {"dex": dex} if dex else {}
        state = ctx.api.info({"type": "clearinghouseState", "user": user, **extra})
        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
            raise ChainError(f"{ctx.api.label} returned an unexpected account state")
        for item in state["assetPositions"]:
            p = item.get("position") or {}
            if p.get("coin") in coins:
                total += abs(Decimal(str(p.get("positionValue") or "0")))
        orders = ctx.api.info({"type": "frontendOpenOrders", "user": user, **extra})
        if not isinstance(orders, list):
            raise ChainError(f"{ctx.api.label} returned unexpected open orders")
        for order in orders:
            if order.get("coin") in coins and not order.get("reduceOnly"):
                value = _order_value(order)
                total += value
                counted[order.get("oid")] = value
    return total, counted


def _leverage(ctx: hl.Ctx, user: str, coin: str) -> int | None:
    found = ctx.api.info({"type": "activeAssetData", "user": user, "coin": coin})
    lev = (found or {}).get("leverage") if isinstance(found, dict) else None
    return lev.get("value") if isinstance(lev, dict) and isinstance(lev.get("value"), int) else None


def fits(ctx: hl.Ctx, state: Path, quote: dict, mandate: dict, now: float,
         reference: Decimal | None) -> tuple[bool, str]:
    """Whether a quote lies inside a mandate as the account stands now, and why not when it does not.
    ``reference`` is the market's price now (the higher of mid and mark): an order is worth its size at
    the highest of its own price and that, since a sell can fill above its limit. Any read that fails,
    or a shape it does not know, is a no: the quote then needs its card."""
    if quote["kind"] not in COVERED:
        return False, f"a mandate does not cover {quote['kind']}"
    if quote["market"]["spot"]:
        return False, "a mandate does not cover spot"
    if quote["account"] != mandate["account"] or quote["network"] != mandate["network"]:
        return False, "the mandate is for another account or network"
    coin = quote["market"]["coin"]
    if coin not in mandate["markets"]:
        return False, f"{coin} is not among the mandate's markets"
    if used(state, mandate["id"], now) >= mandate["per_hour"]:
        return False, f"the mandate's {mandate['per_hour']} orders this hour are used"
    built, user = quote["built"], quote["from"].lower()
    max_order, max_exposure = Decimal(mandate["max_order_usd"]), Decimal(mandate["max_exposure_usd"])
    try:
        held, counted = exposure(ctx, user, mandate["markets"])
        if quote["kind"] == "leverage":
            if built["leverage"] > mandate["max_leverage"]:
                return False, f"{built['leverage']}x is above the mandate's {mandate['max_leverage']}x"
            if held > max_exposure:
                return False, (f"the mandate's markets hold {signer.plain(held.quantize(Decimal('0.01')))} USDC, "
                               f"above its {mandate['max_exposure_usd']}")
            return True, "inside the mandate"
        leverage = _leverage(ctx, user, coin)
        if leverage is None or leverage > mandate["max_leverage"]:
            return False, f"the account's {coin} leverage is above the mandate's {mandate['max_leverage']}x"
        if reference is None or reference <= 0:
            return False, f"{coin}'s price could not be read to check the mandate"
        value = Decimal(built["size"]) * max(Decimal(built["price"]), reference)
        freed = Decimal(0)
        if quote["kind"] == "modify":  # only what the old order still counts for now is freed
            oid = built["order"].get("oid")
            if oid not in counted:
                return False, "the order to modify is no longer open as it was quoted"
            freed = counted[oid]
    except (ChainError, KeyError, ArithmeticError, TypeError, ValueError):
        return False, "the account could not be read to check the mandate"
    if value > max_order:
        return False, f"this order is worth {signer.plain(value.quantize(Decimal('0.01')))} USDC, above the mandate's " \
                      f"{mandate['max_order_usd']}"
    after = held - freed + value
    if after > max_exposure:
        return False, (f"the mandate's markets would hold {signer.plain(after.quantize(Decimal('0.01')))} USDC, "
                       f"above its {mandate['max_exposure_usd']}")
    return True, "inside the mandate"
