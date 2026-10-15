"""Hyperliquid moves of funds for the trader (docs/hyperliquid.md "Moving funds"): withdraw, send and
transfer, the user-signed actions they become, their card lines and their notes.

A quote kind is built by one builder into ``built`` with a ``move``: the wire type and its fields, which
is all that is signed. Each wire type has one entry in ``TYPES`` (how it is signed and what it means once
sent) and each kind one in ``KINDS`` (how it is built and shown), so a new move is a builder, its card
lines and a ``TYPES`` entry beside the signing in ``hl_sign``. A fee the venue takes is described the same
way by every builder (``fee``): how much, from where (``fee_from``: the amount, or a balance beside it),
what for (``fee_for``), and what arrives when it comes off the amount.

Runs in the trader's process only, with the web3 venv's interpreter; it reads accounts and markets but
never a key, and every effect is decided again by the trader from the secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Callable

import chains
import hl
import hl_sign
import rpc
import signer
from rpc import ChainError

MOVES = ("withdraw", "send", "transfer")  # funds moving out of a position: own or external, like a wallet send
# the venue's fee for a send to an address with no account there: usdSend takes it from the amount,
# spotSend and sendAsset take it in USDC from the sender beside the amount
NEW_ACCOUNT_FEE = Decimal("1")
WITHDRAW_TO = {"mainnet": "arbitrum", "testnet": "arbitrum-sepolia"}  # a withdrawal's chain unless one is named
CCTP_GAS_LIMIT = 200_000  # HyperEVM gas for the linked contract's burn, as Circle's withdrawal recipe sets it
FEE_SELECTOR = "e26f7d23"  # calculateCrossChainWithdrawalFee(bool shouldForward, uint32 destinationDomain)
USDC_MARKET = {"coin": "USDC", "label": "USDC", "spot": False}


def plain(number: Decimal) -> str:
    return hl_sign.wire(number)


def shown(number: Decimal) -> str:
    """A balance as context, at whatever precision it has (never signed, so never wire-limited)."""
    return signer.plain(number)


def _amount(payload: dict) -> Decimal:
    value = payload.get("amount")
    if value in (None, ""):
        raise ChainError("amount is required")
    try:
        number = hl_sign.decimal(value, "amount")
    except hl_sign.SignError as exc:
        raise ChainError(str(exc)) from None
    if number <= 0:
        raise ChainError("amount must be above zero")
    return number


def _usdc(payload: dict) -> Decimal:
    amount = _amount(payload)
    try:
        hl_sign.usd_int(amount)
    except hl_sign.SignError as exc:
        raise ChainError(str(exc)) from None
    return amount


def _fee(usdc: Decimal, source: str, why: str, amount: Decimal | None = None) -> dict:
    """A venue fee as every builder states it: from the amount (``arrives`` is what is left) or from a
    balance beside it."""
    fee = {"fee": plain(usdc), "fee_from": source, "fee_for": why}
    if source == "amount":
        fee["arrives"] = plain(amount - usdc)
    return fee


# --- accounts -----------------------------------------------------------------------------------

def _destination(payload: dict, default: str | None = None) -> str:
    value = payload.get("destination") or default
    if not isinstance(value, str) or not re.match(r"^0x[0-9a-fA-F]{40}$", value):
        raise ChainError("destination must be a 0x address of 40 hex digits")
    if int(value, 16) == 0:
        raise ChainError("the zero address burns funds; refused")
    if chains.hyperliquid_bridge(value):
        raise ChainError("that is Hyperliquid's deposit bridge, not an account; refused")
    return value.lower()


def _perp_free(ctx: hl.Ctx, user: str) -> Decimal:
    found = ctx.api.info({"type": "clearinghouseState", "user": user})
    if not isinstance(found, dict) or found.get("withdrawable") is None:
        raise ChainError(f"{ctx.api.label} returned an unexpected account state")
    return Decimal(str(found["withdrawable"]))


def _spot_free(ctx: hl.Ctx, user: str, token: dict) -> Decimal:
    """The spot balance of one token not held, matched by the token's index (names repeat; the index
    does not), and never more than the venue calls available after maintenance margin when it says
    (a unified account's one balance also backs its perp positions)."""
    found = ctx.api.info({"type": "spotClearinghouseState", "user": user})
    if not isinstance(found, dict) or not isinstance(found.get("balances"), list):
        raise ChainError(f"{ctx.api.label} returned unexpected spot balances")
    free = Decimal(0)
    for item in found["balances"]:
        if isinstance(item, dict) and item.get("token") == token.get("index"):
            free = Decimal(str(item.get("total") or "0")) - Decimal(str(item.get("hold") or "0"))
            break
    for pair in found.get("tokenToAvailableAfterMaintenance") or []:
        if isinstance(pair, list) and len(pair) == 2 and pair[0] == token.get("index"):
            free = min(free, Decimal(str(pair[1])))
    return free


def _usdc_token(ctx: hl.Ctx) -> dict:
    """The venue's own USDC: spot token 0 on both networks, found by its index, never by a name a
    deployer could reuse."""
    found = [t for t in ctx.spot()[0].get("tokens", []) if t.get("index") == 0]
    if len(found) != 1 or found[0].get("name") != "USDC":
        raise ChainError(f"{ctx.api.label} did not list USDC as spot token 0")
    return found[0]


def _unified(ctx: hl.Ctx, user: str) -> bool:
    """Whether the account keeps one balance for spot and perp (held in its spot state), where the venue
    refuses spotSend and usdClassTransfer and sendAsset moves funds."""
    return hl.abstraction(ctx, user) in hl.UNIFIED


def _spot_token(ctx: hl.Ctx, token) -> dict:
    """A spot token by its name, or by NAME:0x… (its id) when names repeat: deployers choose names."""
    if not isinstance(token, str) or not token.strip():
        raise ChainError("token is a spot token's name, like HYPE or USDC")
    name, _, token_id = token.strip().partition(":")
    found = [t for t in ctx.spot()[0].get("tokens", []) if str(t.get("name")).upper() == name.upper()
             and (not token_id or str(t.get("tokenId", "")).lower() == token_id.lower())]
    if not found:
        raise ChainError(f"no spot token {token!r} on {ctx.api.label}; balances lists what the account holds")
    if len(found) > 1:
        ids = ", ".join(f"{t['name']}:{t.get('tokenId')}" for t in found[:5])
        raise ChainError(f"{token!r} names several spot tokens ({ids}); give it as NAME:tokenId")
    return found[0]


def _new_account(ctx: hl.Ctx, address: str) -> bool:
    """Whether an address has no account on this network yet: a send to it pays the venue's fee to open one."""
    found = ctx.api.info({"type": "userRole", "user": address})
    role = found.get("role") if isinstance(found, dict) else None
    if not isinstance(role, str):
        raise ChainError(f"{ctx.api.label} returned an unexpected account role")
    return role == "missing"


def _spot_paid(ctx, user: str, token: dict, amount: Decimal, balance: str, new: bool) -> Decimal:
    """The token's free spot (or unified) balance, checked to cover the send and, to an address with no
    account, the venue's opening fee, which it takes in USDC beside the amount (seen for USDC sends; for
    another token the same USDC fee is assumed, so the check asks for 1 USDC free beside it)."""
    free = _spot_free(ctx, user, token)
    fee = NEW_ACCOUNT_FEE if new else Decimal(0)
    usdc = token.get("index") == 0
    if amount + (fee if usdc else 0) > free:
        extra = f" (and {fee} USDC more to open the destination's account)" if new and usdc else ""
        raise ChainError(f"the {balance} balance can send {shown(max(free - (fee if usdc else 0), Decimal(0)))} "
                         f"{token['name']} now{extra}")
    if new and not usdc and _spot_free(ctx, user, _usdc_token(ctx)) < fee:
        raise ChainError(f"the destination has no Hyperliquid account yet, and the venue takes {fee} USDC from the "
                         f"{balance} balance to open it, which does not hold that much USDC")
    return free


# --- builders -----------------------------------------------------------------------------------

class _HyperEvm(rpc.Rpc):
    """HyperEVM's public endpoint, for reads only: it is no chain of the wallet's table."""

    def __init__(self, network: str, override: str | None = None):
        entry = chains.HYPEREVM[network]
        self.chain, self.name = None, entry["name"]
        self.url, self.provider = (override, "test RPC") if override and rpc.testing() else (entry["rpc"], "public RPC")
        self.ids, self.timeout = 0, rpc.TIMEOUT

    @property
    def label(self) -> str:
        return f"{self.name} ({self.provider})"


def _withdraw_chain(network: str, payload: dict) -> tuple[str, int]:
    """(chain, CCTP domain) a withdrawal goes to: one of this network's chains Circle carries USDC on."""
    chain = payload.get("chain") or WITHDRAW_TO[network]
    testnet = network == "testnet"
    offered = [c for c in chains.CCTP_DOMAINS if chains.EVM[c]["testnet"] == testnet]
    if chain not in offered:
        raise ChainError(f"a {network} withdrawal goes to one of {', '.join(offered)} (USDC through Circle's CCTP)")
    return chain, chains.CCTP_DOMAINS[chain]


def _withdrawal_fee(ctx: hl.Ctx, payload: dict, domain: int) -> Decimal:
    """Circle's fee to burn and forward a withdrawal to a domain, as its HyperEVM contract states it now
    (calculateCrossChainWithdrawalFee, with forwarding): USDC that comes off the amount."""
    node = _HyperEvm(ctx.network, payload.get("_hyperevm"))
    data = "0x" + FEE_SELECTOR + f"{1:064x}{domain:064x}"
    found = node.call("eth_call", [{"to": chains.HYPEREVM[ctx.network]["core_deposit_wallet"], "data": data},
                                   "latest"])
    if not isinstance(found, str) or not re.match(r"^0x[0-9a-fA-F]{64}$", found):
        raise ChainError(f"{node.label} returned an unexpected withdrawal fee")
    return Decimal(int(found, 16)).scaleb(-6)


def build_withdraw(ctx, payload, user, mkt_unused, quote_id) -> dict:
    amount = _usdc(payload)
    chain, domain = _withdraw_chain(ctx.network, payload)
    destination = _destination(payload, user)
    unified = _unified(ctx, user)
    free = _spot_free(ctx, user, _usdc_token(ctx)) if unified else _perp_free(ctx, user)
    if amount > free:
        held = "unified balance after margin" if unified else "perp balance not held as margin"
        raise ChainError(f"the account can withdraw {shown(free)} USDC now ({held})")
    fee = _withdrawal_fee(ctx, payload, domain)
    if amount <= fee:
        raise ChainError(f"a withdrawal to {chains.info(chain)['name']} pays Circle {shown(fee)} USDC; withdraw "
                         "more than that")
    return {"action": None, "market": USDC_MARKET, "cloids": [], "amount": plain(amount), "destination": destination,
            **_fee(fee, "amount", "withdrawal", amount), "available": shown(free),
            "chain": chains.info(chain)["name"], "balance": "unified" if unified else "perp",
            "move": {"type": "sendToEvmWithData", "token": "USDC", "amount": plain(amount),
                     "sourceDex": hl_sign.SPOT_DEX if unified else "", "destination": destination, "chain": chain,
                     "domain": domain}}


def build_send(ctx, payload, user, mkt_unused, quote_id) -> dict:
    amount = _amount(payload)
    destination = _destination(payload)
    if destination == user:
        raise ChainError("the destination is the sending account itself")
    unified = _unified(ctx, user)
    if payload.get("token") in (None, ""):
        try:
            hl_sign.usd_int(amount)
        except hl_sign.SignError as exc:
            raise ChainError(str(exc)) from None
        new = _new_account(ctx, destination)
        if unified:
            # the one USDC balance, to the destination's perp balance, as usdSend would credit it
            return _send_asset(ctx, user, _usdc_token(ctx), amount, destination, "", new)
        if new and amount <= NEW_ACCOUNT_FEE:
            raise ChainError(f"{destination} has no Hyperliquid account yet, and the venue takes "
                             f"{NEW_ACCOUNT_FEE} USDC from this send to open it; send more than that")
        free = _perp_free(ctx, user)
        if amount > free:
            raise ChainError(f"the perp balance can send {shown(free)} USDC now")
        fee = _fee(NEW_ACCOUNT_FEE, "amount", "new account", amount) if new else {}
        return {"action": None, "market": USDC_MARKET, "cloids": [], "amount": plain(amount), "token": "USDC (perp)",
                "destination": destination, "available": shown(free), **fee,
                "move": {"type": "usdSend", "destination": destination, "amount": plain(amount)}}
    token = _spot_token(ctx, payload.get("token"))
    # the token's own precision, and never past what a signed amount carries
    decimals = min(int(token.get("weiDecimals", hl_sign.WIRE_DECIMALS)), hl_sign.WIRE_DECIMALS)
    if amount != amount.quantize(Decimal(1).scaleb(-decimals)):
        raise ChainError(f"{token['name']} has at most {decimals} decimal places")
    new = _new_account(ctx, destination)
    if unified:
        return _send_asset(ctx, user, token, amount, destination, hl_sign.SPOT_DEX, new)
    free = _spot_paid(ctx, user, token, amount, "spot", new)
    wire_token = f"{token['name']}:{token.get('tokenId')}"
    fee = _fee(NEW_ACCOUNT_FEE, "spot", "new account") if new else {}
    return {"action": None, "market": {"coin": token["name"], "label": token["name"], "spot": True}, "cloids": [],
            "amount": plain(amount), "token": hl.ticker(token["name"]), "token_id": token.get("tokenId"),
            "destination": destination, "available": shown(free), **fee,
            "move": {"type": "spotSend", "destination": destination, "token": wire_token, "amount": plain(amount)}}


def _send_asset(ctx, user: str, token: dict, amount: Decimal, destination: str, destination_dex: str,
                new: bool) -> dict:
    """A send from a unified account's one balance (sendAsset from spot), to the destination's spot
    balance or its default perp one."""
    free = _spot_paid(ctx, user, token, amount, "unified", new)
    wire_token = f"{token['name']}:{token.get('tokenId')}"
    fee = _fee(NEW_ACCOUNT_FEE, "unified", "new account") if new else {}
    return {"action": None, "market": {"coin": token["name"], "label": token["name"], "spot": True}, "cloids": [],
            "amount": plain(amount), "token": hl.ticker(token["name"]), "token_id": token.get("tokenId"),
            "destination": destination, "available": shown(free), "balance": "unified",
            "to_balance": "spot" if destination_dex == hl_sign.SPOT_DEX else "perp", **fee,
            "move": {"type": "sendAsset", "destination": destination, "sourceDex": hl_sign.SPOT_DEX,
                     "destinationDex": destination_dex, "token": wire_token, "amount": plain(amount)}}


def build_transfer(ctx, payload, user, mkt_unused, quote_id) -> dict:
    amount = _usdc(payload)
    to_perp = payload.get("to_perp")
    if not isinstance(to_perp, bool):
        raise ChainError("to_perp is true (spot to perp) or false (perp to spot)")
    if _unified(ctx, user):
        raise ChainError("this is a unified account: spot and perp share one balance, so there is nothing to move "
                         "between them (the venue refuses usdClassTransfer here)")
    free = _spot_free(ctx, user, _usdc_token(ctx)) if to_perp else _perp_free(ctx, user)
    if amount > free:
        raise ChainError(f"the {'spot' if to_perp else 'perp'} balance can move {shown(free)} USDC now")
    return {"action": None, "market": USDC_MARKET, "cloids": [], "amount": plain(amount), "to_perp": to_perp,
            "available": shown(free), "move": {"type": "usdClassTransfer", "amount": plain(amount), "toPerp": to_perp}}


# --- cards --------------------------------------------------------------------------------------

def _withdraw_lines(b: dict, whose: str) -> list[str]:
    return [f"Withdraw: {b['amount']} USDC from the {b.get('balance', 'perp')} balance to {b['chain']}",
            f"To ({whose}): {b['destination']}",
            f"Fee: {b['fee']} USDC to Circle's CCTP (about {b['arrives']} arrives, usually within a minute)"]


def _withdraw_short(b: dict, lines: list[str]) -> list[str]:
    """The compact card's withdrawal keeps what arrives: Circle's fee differs by chain."""
    return [line + f" ({b['arrives']} arrives)" if line.startswith("Withdraw:") else line for line in lines]


def _send_lines(b: dict, whose: str) -> list[str]:
    token = b["token"] if isinstance(b["token"], str) else f"\"{b['token']['untrusted']}\""
    fee = []
    if b.get("fee_from") == "amount":
        fee = [f"Fee: {b['fee']} USDC from the amount opens their account (about {b['arrives']} arrives)"]
    elif b.get("fee_from"):
        fee = [f"Fee: {b['fee']} USDC more, from the {b['fee_from']} balance, opens their account"]
    if b.get("balance") == "unified":
        return [f"Send on Hyperliquid: {b['amount']} {token} ({b['token_id']})",
                f"From the unified balance to their {b['to_balance']} balance",
                f"To ({whose}): {b['destination']}", *fee]
    what = token if b.get("token_id") is None else f"{token} (spot, {b['token_id']})"
    return [f"Send on Hyperliquid: {b['amount']} {what}", f"To ({whose}): {b['destination']}", *fee]


def _send_short(b: dict, lines: list[str]) -> list[str]:
    """The compact card's send: the unified route said briefly, and an account-opening fee kept, since it
    changes what arrives or what leaves."""
    lines = [line.replace("From the unified balance to their ", "Unified → their ").removesuffix(" balance")
             if line.startswith("From the unified balance") else line for line in lines]
    if b.get("fee_from"):
        tail = f" ({b['arrives']} arrives)" if b["fee_from"] == "amount" else f" +{b['fee']} USDC fee"
        lines = [line + tail if line.startswith("Send on Hyperliquid:") else line for line in lines]
    return lines


def _transfer_lines(b: dict, whose: str) -> list[str]:
    return [f"Move: {b['amount']} USDC {'spot → perp' if b['to_perp'] else 'perp → spot'} (same account)"]


# --- the tables ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Kind:
    """A quote kind that moves funds: how it is built, its card lines, and how the compact card shortens them."""
    build: Callable
    lines: Callable[[dict, str], list[str]]
    short: Callable[[dict, list[str]], list[str]] | None = None


@dataclass(frozen=True)
class Type:
    """A signed move: its action from the stored fields and the nonce, and what the user is told once sent
    (a text, or one made from the move). ``internal`` moves stay in the account (no destination), so they
    are always own. ``recheck`` reads again, just before signing, what the quote priced but the action
    does not bind, and refuses when it changed."""
    action: Callable[[dict, int], dict]
    note: str | Callable[[dict], str]
    internal: bool = False
    recheck: Callable[[hl.Ctx, dict, dict], None] | None = None


def _recheck_withdrawal_fee(ctx: hl.Ctx, payload: dict, quote: dict) -> None:
    """Circle's fee is set on its contract and the signed burn carries no ceiling, so a fee raised since the
    quote would take more than the card said: the quote is refused instead."""
    built, move = quote["built"], quote["built"]["move"]
    now = plain(_withdrawal_fee(ctx, payload, move["domain"]))
    if now != built["fee"]:
        raise ChainError(f"Circle's fee to {built['chain']} is {now} USDC now, not the {built['fee']} USDC this "
                         "quote showed; nothing was sent: quote it again")


KINDS = {
    "withdraw": Kind(build_withdraw, _withdraw_lines, _withdraw_short),
    "send": Kind(build_send, _send_lines, _send_short),
    "transfer": Kind(build_transfer, _transfer_lines),
}
TYPES = {
    "sendToEvmWithData": Type(
        lambda m, n: hl_sign.send_to_evm_action(m["token"], m["amount"], m["sourceDex"], m["destination"],
                                                m["domain"], CCTP_GAS_LIMIT, n),
        lambda m: f"Circle burns it now and mints it on {chains.info(m['chain'])['name']}, usually within a minute; "
                  "check the balance there with the evm tool before anything else",
        recheck=_recheck_withdrawal_fee),
    "usdSend": Type(lambda m, n: hl_sign.usd_send_action(m["destination"], m["amount"], n),
                    "it arrives on the destination's Hyperliquid account at once"),
    "spotSend": Type(lambda m, n: hl_sign.spot_send_action(m["destination"], m["token"], m["amount"], n),
                     "it arrives on the destination's Hyperliquid spot balance at once"),
    "sendAsset": Type(lambda m, n: hl_sign.send_asset_action(m["destination"], m["sourceDex"], m["destinationDex"],
                                                             m["token"], m["amount"], n),
                      "it arrives on the destination's Hyperliquid account at once"),
    "usdClassTransfer": Type(lambda m, n: hl_sign.usd_class_transfer_action(m["amount"], m["toPerp"], n),
                             "the balance moved within the account", internal=True),
}
BUILDERS = {kind: spec.build for kind, spec in KINDS.items()}


def _type(move: dict) -> Type:
    spec = TYPES.get(move.get("type"))
    if spec is None:
        raise ChainError(f"{move.get('type')!r} is not a move here")
    return spec


def effect(quote: dict, secrets_) -> str:
    """own when the funds stay in the user's own Hermes wallets — a move within the account, or a
    destination the secrets derive as own (computed from them, never taken from the model) — else external."""
    move = quote["built"]["move"]
    if _type(move).internal:
        return "own"
    return "own" if move["destination"].lower() in secrets_.own("evm") else "external"


def action(move: dict, nonce: int) -> dict:
    """The user-signed action of a stored move, with its time (the nonce it is signed under)."""
    return _type(move).action(move, nonce)


def note(move: dict) -> str:
    said = _type(move).note
    return said(move) if callable(said) else said


def recheck(quote: dict, ctx: hl.Ctx, payload: dict) -> None:
    """Before signing: refuse a quote whose unbound price changed (a no-op for moves that have none)."""
    check = _type(quote["built"]["move"]).recheck
    if check:
        check(ctx, payload, quote)


def lines(quote: dict) -> list[str]:
    whose = "own" if quote.get("effect") == "own" else "external"
    return KINDS[quote["kind"]].lines(quote["built"], whose)


def short(quote: dict, lines_: list[str]) -> list[str]:
    spec = KINDS[quote["kind"]]
    return spec.short(quote["built"], lines_) if spec.short else lines_


def trail(quote: dict) -> dict:
    """What a move's ledger rows keep beyond the quote, which is pruned: the chain it went to and the fee
    priced, with what was to arrive."""
    built, move = quote["built"], quote["built"]["move"]
    kept = {"to_chain": move.get("chain"), "fee": built.get("fee"), "fee_from": built.get("fee_from"),
            "arrives": built.get("arrives")}
    return {k: v for k, v in kept.items() if v is not None}


def recorded(quote: dict) -> dict:
    """Where a move goes and what it moves, as the wallet's transfer ledger records it."""
    move = quote["built"]["move"]
    return {"to": move.get("destination", quote["from"]), "asset": move.get("token", "USDC"), **trail(quote)}
