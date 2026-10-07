"""The wallet's signer: one operation per process, run by the web3 venv's interpreter.

The only code that reads wallet secrets: every Keychain item whose kind is a seed phrase or a private
key, in any project, found by ``keychain.discover`` (other secrets are never read). Only those with
HERMES in their name sign; the rest are watch-only. Seeds, keys and raw signed transactions stay in
this process: replies carry addresses, quotes, approval card text and transaction hashes, and every
string leaving is scrubbed of the values it read.

    {"op": "accounts" | "quote" | "send" | "status", "state": "<the wallet's state directory>",
     …the op's arguments}
    → {"ok": true, "data": {…}} or {"ok": false, "error": "…"}

Accounts are ``<source>#<index>`` for a seed (``hermes/HERMES_MAIN#0``) and ``<source>`` for a key, where a
source is ``<project>[/<scope>]/<name>``. A quote is the exact transfer, built and simulated, stored
as a single-use file that expires after ``QUOTE_TTL`` and carries an HMAC keyed from its sending
secret, so neither its transaction nor its card can be edited between approval and send. ``send``
re-checks the MAC, the expiry, the hourly cap and — for a send approved as own — that the recipient
really is one of the secrets' addresses; the quote is consumed and written to the ledger before it is
broadcast. ``_sources`` (a list of items with values) and ``_rpc`` are honoured only under the
engine's tests (``WEB3_ENGINE_TEST=1``). Contract: docs/web3.md "Transfers" and "Approval".
"""

from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import re
import secrets as random
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "_shared"), str(HERE)]

import chains  # noqa: E402
import evm  # noqa: E402
import keychain  # noqa: E402
import ledger  # noqa: E402
import prices  # noqa: E402
import rpc  # noqa: E402
from rpc import ChainError  # noqa: E402

QUOTE_TTL = 900            # outlives the 600 s approval wait
OWN_INDEXES = 101          # each seed's accounts 0..100 count as own
LIST_DEFAULT = 5           # accounts lists this many per seed unless asked for more
GAS_MARGIN = Decimal("1.2")
SOL_SIG_FEE = 5000
ATA_SPACE = {"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": 165, "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": 170}
SYSTEM = "11111111111111111111111111111111"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
QUOTE_ID = re.compile(r"^q[0-9a-f]{8}$")
SYMBOL = re.compile(r"^[A-Za-z0-9.$_-]{1,12}$")
MEMO_CLIP = 40
CARD_BUDGET = 480          # Telegram cuts an approval card's reason at 500 escaped UTF-16 units
SHORT_BUDGET = 290         # Discord cuts it at 300
SETUP = ("store a Hermes-only seed phrase under a name with HERMES in it, like `secret set HERMES_MAIN -p <project> "
         "-D MNEMONIC` (a private key: -D PRIVATE_KEY); seed phrases and keys under other names are watch-only")


# --- secrets ------------------------------------------------------------------------------------

class Secrets:
    """The wallet secrets of one call, held in memory only: seeds by source id, and keys by source
    id as (family, secret), each with its Keychain metadata. Only sources with HERMES in their name
    (``use`` "sign") sign or count as own; the others are watch-only."""

    def __init__(self, payload: dict):
        from eth_account.hdaccount import seed_from_mnemonic
        from mnemonic import Mnemonic
        items = payload.get("_sources") if rpc.testing() and payload.get("_sources") is not None else None
        if items is None:
            try:
                items = keychain.discover()
            except keychain.KeychainError as exc:
                raise ChainError(str(exc)) from None
        self.seeds: dict[str, bytes] = {}
        self.keys: dict[str, tuple[str, object]] = {}
        self.meta: dict[str, dict] = {}
        self.problems: list[dict] = []
        fingerprints: dict[bytes, str] = {}
        # the name decides, here as in discovery: a secret stored under both kinds of name is kept as
        # the Hermes one, and anything without HERMES in its name is watch-only
        def name_of(item):
            return item.get("name") or str(item.get("id", "")).rsplit("/", 1)[-1]

        items = sorted(items, key=lambda item: keychain.use_of(name_of(item)) != "sign")
        for item in items:
            value, source = item.get("value"), item.get("id") or keychain.source_id(item)
            use = keychain.use_of(name_of(item))
            if value:
                rpc.SECRETS.append(value)
            if not value:
                self.problems.append({"source": source, "problem": "could not be read"})
                continue
            if item["role"] == "seed":
                words = " ".join(value.split())
                rpc.SECRETS.append(words)
                if not Mnemonic("english").check(words):
                    self.problems.append({"source": source, "problem": "labelled MNEMONIC but not a valid English "
                                                                       "BIP39 phrase"})
                    continue
                secret = seed_from_mnemonic(words, "")
            else:
                parsed = self._parse_key(value.strip())
                if parsed is None:
                    self.problems.append({"source": source, "problem": "labelled PRIVATE_KEY but neither a 32-byte "
                                                                       "hex EVM key nor a Solana keypair"})
                    continue
                secret = parsed
            fingerprint = hashlib.sha256(self._material(secret)).digest()
            if fingerprint in fingerprints:
                self.problems.append({"source": source, "problem": f"the same secret as {fingerprints[fingerprint]}; "
                                                                   "ignored"})
                continue
            fingerprints[fingerprint] = source
            if item["role"] == "seed":
                self.seeds[source] = secret
            else:
                self.keys[source] = secret
            self.meta[source] = {"project": item.get("project"), "scope": item.get("scope"),
                                 "name": item.get("name"), "label": item.get("label"),
                                 "kind": item["role"], "use": use, "memo": one_line(item.get("memo"), MEMO_CLIP)}
        self._parents: dict[str, tuple[bytes, bytes]] = {}

    def signable(self, source: str) -> bool:
        return self.meta.get(source, {}).get("use") == "sign"

    @staticmethod
    def _material(secret) -> bytes:
        """The raw bytes of a seed (bytes) or a key ((family, secret))."""
        if isinstance(secret, bytes):
            return secret
        kind, value = secret
        return value if kind == "evm" else bytes(value)

    @staticmethod
    def _parse_key(value: str):
        text = value[2:] if value.startswith("0x") else value
        if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
            return "evm", bytes.fromhex(text)
        from solders.keypair import Keypair
        try:
            if value.startswith("["):
                return "solana", Keypair.from_bytes(bytes(json.loads(value)))
            return "solana", Keypair.from_base58_string(value)
        except Exception:
            return None

    def require_any(self) -> None:
        if not any(self.signable(source) for source in [*self.seeds, *self.keys]):
            raise ChainError("no Hermes seed phrase or private key is in the Keychain; " + SETUP)

    # derivation

    def _evm_parent(self, source: str) -> tuple[bytes, bytes]:
        """m/44'/60'/0'/0 of a seed, derived once per call."""
        from eth_account.hdaccount.deterministic import HDPath, derive_child_key, hmac_sha512
        if source not in self._parents:
            node = hmac_sha512(b"Bitcoin seed", self.seeds[source])
            key, code = node[:32], node[32:]
            for part in HDPath("m/44'/60'/0'/0")._path:
                key, code = derive_child_key(key, code, part)
            self._parents[source] = (key, code)
        return self._parents[source]

    def evm_key(self, source: str, index: int) -> bytes:
        from eth_account.hdaccount.deterministic import SoftNode, derive_child_key
        key, code = self._evm_parent(source)
        return derive_child_key(key, code, SoftNode(index))[0]

    def sol_keypair(self, source: str, index: int):
        from solders.keypair import Keypair
        return Keypair.from_seed_and_derivation_path(self.seeds[source], f"m/44'/501'/{index}'/0'")

    @staticmethod
    def evm_address(key: bytes) -> str:
        from eth_keys import keys
        return keys.PrivateKey(key).public_key.to_checksum_address()

    def account(self, account_id) -> tuple[str, int | None]:
        """(source, index) of an account id; index is None for a key."""
        if not isinstance(account_id, str) or not account_id:
            raise ChainError("account is required, like hermes/MAIN#0; wallet accounts lists them")
        source, _, index = account_id.partition("#")
        if index:
            if source not in self.seeds:
                raise ChainError(f"no seed phrase {source!r}; wallet accounts lists them")
            if not index.isdigit() or int(index) > 2 ** 31 - 1:
                raise ChainError("the account index must be a number, like #0")
            return source, int(index)
        if source in self.keys:
            return source, None
        if source in self.seeds:
            raise ChainError(f"{source} is a seed phrase; name an account in it, like {source}#0")
        raise ChainError(f"no account {account_id!r}; wallet accounts lists them")

    def address_of(self, account_id: str, family: str) -> str:
        """An account's address on a family, watch-only accounts included."""
        return self._derive(account_id, family)[0]

    def signer(self, account_id: str, family: str):
        """(address, signing secret) of an account Hermes may sign with on a chain family."""
        source, _ = self.account(account_id)
        if not self.signable(source):
            raise ChainError(f"{source} is watch-only (no HERMES in its name): Hermes reads its addresses but never "
                             "signs with it; a Hermes wallet is stored under a name like HERMES_MAIN")
        return self._derive(account_id, family)

    def _derive(self, account_id: str, family: str):
        source, index = self.account(account_id)
        if index is None:
            kind, secret = self.keys[source]
            if kind != family:
                raise ChainError(f"{source} is a{'n EVM' if kind == 'evm' else ' Solana'} key; it cannot sign on "
                                 f"{'EVM chains' if family == 'evm' else 'Solana'}")
            return (self.evm_address(secret), secret) if family == "evm" else (str(secret.pubkey()), secret)
        if family == "evm":
            key = self.evm_key(source, index)
            return self.evm_address(key), key
        pair = self.sol_keypair(source, index)
        return str(pair.pubkey()), pair

    def addresses(self, family: str, use: str) -> dict[str, str]:
        """Address → account id for every source of a use ('sign' or 'watch'): each seed's accounts
        0..100 and every key of the family. EVM addresses are lowercased."""
        found: dict[str, str] = {}
        for source in self.seeds:
            if self.meta[source]["use"] != use:
                continue
            for index in range(OWN_INDEXES):
                if family == "evm":
                    found.setdefault(self.evm_address(self.evm_key(source, index)).lower(), f"{source}#{index}")
                else:
                    found.setdefault(str(self.sol_keypair(source, index).pubkey()), f"{source}#{index}")
        for source, (kind, secret) in self.keys.items():
            if self.meta[source]["use"] != use or kind != family:
                continue
            found.setdefault(self.evm_address(secret).lower() if kind == "evm" else str(secret.pubkey()), source)
        return found

    def own(self, family: str) -> set[str]:
        """Every address the Hermes wallets control; watch-only wallets are not own."""
        return set(self.addresses(family, "sign"))

    def party(self, account_id: str) -> dict:
        """An account's Keychain metadata as the approval card shows it."""
        source, index = self.account(account_id)
        meta = self.meta[source]
        return {"account": account_id, "project": meta["project"], "scope": meta["scope"] or "Shared",
                "name": meta["name"], "index": index, "memo": meta.get("memo"), "use": meta["use"]}

    def mac(self, quote: dict) -> str:
        """Keyed from the quote's sending secret; covers everything but the MAC and the consumed mark."""
        source = quote["source"]
        material = self._material(self.seeds[source] if source in self.seeds else self.keys[source])
        key = hashlib.sha256(b"hermes-web3-quote\x00" + material).digest()
        body = json.dumps({k: v for k, v in quote.items() if k not in ("mac", "consumed")}, sort_keys=True,
                          ensure_ascii=False)
        return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


class Rejected(ChainError):
    """The node answered the broadcast with an error: the transaction did not enter the network."""


class Unknown(ChainError):
    """The broadcast's answer never arrived: the transaction may or may not be in the network."""


def broadcast(r, method: str, params: list):
    try:
        reply = r.request(method, params)
    except ChainError as exc:
        raise Unknown(str(exc)) from None
    if reply.get("error"):
        error = reply["error"]
        message = error.get("message") if isinstance(error, dict) else error
        raise Rejected(f"{r.label} refused the transaction: {rpc.mask(message)[:300]}")
    return reply.get("result")


class Ctx:
    """What evm.resolve_address and evm.token_meta need."""

    def __init__(self, chain: str, override: str | None):
        self.chain, self.override = chain, override
        self.rpc = rpc.Rpc(chain, override)

    def rpc_for(self, chain: str):
        return rpc.Rpc(chain, self.override)


# --- amounts and cards --------------------------------------------------------------------------

def to_base(text, decimals: int) -> tuple[Decimal, int]:
    try:
        amount = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise ChainError(f"amount must be a number like 0.05, got {text!r}") from None
    if not amount.is_finite() or amount <= 0:
        raise ChainError("amount must be above zero")
    base = amount * (Decimal(10) ** decimals)
    if base != base.to_integral_value():
        raise ChainError(f"amount has more than {decimals} decimal places")
    return amount.normalize(), int(base)


def plain(amount: Decimal) -> str:
    return format(amount.normalize(), "f")


def native_units(base: int, decimals: int) -> Decimal:
    return (Decimal(base) / (Decimal(10) ** decimals)).normalize()


def one_line(text, clip: int) -> str | None:
    """User text on one line, without control characters, clipped."""
    if not isinstance(text, str):
        return None
    text = " ".join("".join(c if c.isprintable() else " " for c in text).split())
    if not text:
        return None
    return text if len(text) <= clip else text[:clip - 1] + "…"


def card_units(text: str) -> int:
    """Length as Telegram's approval card counts it: HTML-escaped, in UTF-16 units."""
    return len(html.escape(text).encode("utf-16-le")) // 2


def _what(quote: dict) -> str:
    if quote["asset"] == "native":
        what = f"{quote['amount']} {quote['symbol']}"
    else:
        what = f"{quote['amount']} \"{quote['symbol']}\" token"
    if quote.get("usd") is not None:
        what += f" (≈ ${quote['usd']:,.2f})"
    return what


def _to_type(quote: dict) -> str:
    if quote["own"]:
        return "Type: Your own"
    if quote.get("to_party"):
        return "Type: Watch-only (external)"
    return "Type: External"


def _party_lines(party: dict | None, address: str, drop: tuple) -> list[str]:
    if not party:
        return [f"Address: {address}"]
    index = party.get("index")
    lines = [f"Project: {party['project']}({party['scope']})", f"Name: {party['name']}",
             f"Address #{index}: {address}" if index is not None else f"Address (key): {address}"]
    if party.get("memo") and "memo" not in drop:
        lines.append(f"Memo: {party['memo']}")
    return lines


def card(quote: dict, drop: tuple = ()) -> str:
    """The detailed approval card (Telegram, CLI): the transfer first, then a block per side with the
    Keychain's project (scope), name, address and memo; every value from this quote, addresses in full.
    A token's symbol is whatever its contract says, so it is quoted and the token's address shown."""
    info = chains.info(quote["chain"])
    expires = datetime.fromtimestamp(quote["expires"]).astimezone().strftime("%H:%M UTC%z")
    lines = [f"Chain: {info['name']}({'testnet' if info['testnet'] else 'MAINNET'})"]
    if quote["asset"] != "native":
        lines.append(f"Token: {quote['asset_address']}")
    lines += [f"Send: {_what(quote)}", f"Fee: up to {quote['max_fee']} {info['symbol']}",
              f"Quote: {quote['id']} · expires {expires}",
              "", "--- From ---", *_party_lines(quote["from_party"], quote["from"], drop),
              "", "--- To ---", _to_type(quote)]
    if quote.get("ens"):
        lines.append(f"ENS: {quote['ens']}")
    lines += _party_lines(quote.get("to_party"), quote["to"], drop)
    return "\n".join(lines)


def card_short(quote: dict) -> str:
    """The compact approval card for surfaces with a small reason budget (Discord): the facts that
    decide, addresses still in full."""
    info = chains.info(quote["chain"])
    lines = [("" if info["testnet"] else "MAINNET ") + f"Send {_what(quote)} on {info['name']}"]
    if quote["asset"] != "native":
        lines.append(f"Token: {quote['asset_address']}")
    lines.append(f"From {one_line(quote['account'], 40)}: {quote['from']}")
    whose = "own" if quote["own"] else ("watch-only" if quote.get("to_party") else "external")
    lines.append(f"To ({whose}): {quote['to']}")
    lines.append(f"Fee ≤ {quote['max_fee']} {info['symbol']} · {quote['id']}")
    return "\n".join(lines)


def cards(quote: dict) -> tuple[str, str]:
    """(detailed, compact): the detailed card sheds the memos to fit Telegram's budget, and falls back to
    the compact one."""
    short = card_short(quote)
    for drop in ((), ("memo",)):
        text = card(quote, drop)
        if card_units(text) <= CARD_BUDGET:
            return text, short
    return short, short


def safe_symbol(text) -> str:
    return text if isinstance(text, str) and SYMBOL.match(text) else "?"


# --- EVM ----------------------------------------------------------------------------------------

def _evm_fees(r) -> tuple[int, int]:
    head = r.call("eth_getBlockByNumber", ["latest", False]) or {}
    base = evm.h2i(head.get("baseFeePerGas"))
    tip, _ = r.try_call("eth_maxPriorityFeePerGas")
    return base, evm.h2i(tip) if tip else 10 ** 9


def evm_quote(ctx: Ctx, sender: str, args: dict, asset: str) -> dict:
    from eth_abi import encode as abi_encode
    from eth_utils import to_checksum_address
    info = chains.EVM[ctx.chain]
    to, ens = evm.resolve_address(ctx, args.get("to"))
    if int(to, 16) == 0:
        raise ChainError("the zero address burns funds; refused")
    if to.lower() == sender.lower():
        raise ChainError("the recipient is the sending account itself")
    r = ctx.rpc
    if asset == "native":
        decimals, symbol = info["decimals"], info["symbol"]
        amount, base = to_base(args.get("amount"), decimals)
        call = {"from": sender, "to": to, "value": hex(base), "data": "0x"}
    else:
        token = to_checksum_address(asset)
        if to.lower() == asset:
            raise ChainError("the recipient is the token contract itself; tokens sent there are lost")
        if r.call("eth_getCode", [token, "latest"]) in (None, "0x", ""):
            raise ChainError("there is no contract at that token address on this chain")
        meta = evm.token_meta(ctx, [token]).get(asset, {})
        decimals = meta.get("decimals")
        if decimals is None:
            raise ChainError("the token's decimals could not be read; is it an ERC-20 token?")
        symbol = safe_symbol((meta.get("symbol") or {}).get("untrusted"))
        amount, base = to_base(args.get("amount"), decimals)
        held = evm.h2i(r.call("eth_call", [{"to": token, "data": "0x" + evm.SEL["balanceOf"]
                                            + sender[2:].lower().rjust(64, "0")}, "latest"]) or "0x0")
        if held < base:
            raise ChainError(f"the account holds {evm.units(held, decimals)} of this token, less than {plain(amount)}")
        data = "0xa9059cbb" + abi_encode(["address", "uint256"], [to, base]).hex()
        call = {"from": sender, "to": token, "value": "0x0", "data": data}
        raw = bytes.fromhex((r.call("eth_call", [call, "latest"]) or "0x")[2:])
        if len(raw) >= 32 and int.from_bytes(raw[:32], "big") == 0:
            raise ChainError("the token's transfer returned false in simulation")
    estimate = evm.h2i(r.call("eth_estimateGas", [call]))
    gas = estimate if estimate == 21000 else int(Decimal(estimate) * GAS_MARGIN)
    fee_base, tip = _evm_fees(r)
    max_fee_per_gas = 2 * fee_base + tip
    max_fee = gas * max_fee_per_gas
    balance = evm.h2i(r.call("eth_getBalance", [sender, "latest"]))
    value = evm.h2i(call["value"])
    if balance < value + max_fee:
        raise ChainError(f"the account holds {evm.units(balance, info['decimals'])} {info['symbol']}, less than "
                         f"the amount plus the maximum fee ({evm.units(value + max_fee, info['decimals'])})")
    return {"to": to, "ens": ens, "symbol": symbol, "decimals": decimals, "amount": plain(amount),
            "asset_address": None if asset == "native" else to_checksum_address(asset),
            "max_fee": plain(native_units(max_fee, info["decimals"])),
            "build": {"to": call["to"], "value": call["value"], "data": call["data"], "gas": gas,
                      "max_fee_per_gas": max_fee_per_gas, "chain_id": info["id"]}}


def evm_send(ctx: Ctx, quote: dict, key: bytes) -> str:
    from eth_account import Account
    build = quote["build"]
    r = ctx.rpc
    nonce = evm.h2i(r.call("eth_getTransactionCount", [quote["from"], "pending"]))
    fee_base, tip = _evm_fees(r)
    cap = build["max_fee_per_gas"]
    if fee_base + tip > cap:
        raise ChainError("network fees rose above this quote's maximum; quote again")
    tx = {"type": 2, "chainId": build["chain_id"], "nonce": nonce, "to": build["to"],
          "value": evm.h2i(build["value"]), "data": build["data"], "gas": build["gas"],
          "maxFeePerGas": cap, "maxPriorityFeePerGas": min(tip, cap - fee_base)}
    signed = Account.sign_transaction(tx, key)
    return broadcast(r, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])


# --- Solana -------------------------------------------------------------------------------------

def _sol_account(r, address: str) -> dict | None:
    got = r.call("getAccountInfo", [address, {"encoding": "jsonParsed", "commitment": "confirmed"}])
    return (got or {}).get("value")


def _sol_instructions(build: dict, sender: str):
    from solders.instruction import AccountMeta, Instruction
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    payer = Pubkey.from_string(sender)
    if build["kind"] == "native":
        return [transfer(TransferParams(from_pubkey=payer, to_pubkey=Pubkey.from_string(build["to"]),
                                        lamports=build["lamports"]))]
    program, mint = Pubkey.from_string(build["program"]), Pubkey.from_string(build["mint"])
    source, dest = Pubkey.from_string(build["source_ata"]), Pubkey.from_string(build["dest_ata"])
    ixs = []
    if build["create_ata"]:
        ixs.append(Instruction(Pubkey.from_string(ATA_PROGRAM), b"\x01", [
            AccountMeta(payer, True, True), AccountMeta(dest, False, True),
            AccountMeta(Pubkey.from_string(build["to"]), False, False), AccountMeta(mint, False, False),
            AccountMeta(Pubkey.from_string(SYSTEM), False, False), AccountMeta(program, False, False)]))
    data = bytes([12]) + build["amount_base"].to_bytes(8, "little") + bytes([build["decimals"]])
    ixs.append(Instruction(program, data, [AccountMeta(source, False, True), AccountMeta(mint, False, False),
                                           AccountMeta(dest, False, True), AccountMeta(payer, True, False)]))
    return ixs


def _sol_simulate(r, build: dict, sender: str) -> None:
    from solders.hash import Hash
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.transaction import Transaction
    message = Message.new_with_blockhash(_sol_instructions(build, sender), Pubkey.from_string(sender), Hash.default())
    raw = base64.b64encode(bytes(Transaction.new_unsigned(message))).decode()
    got = r.call("simulateTransaction", [raw, {"encoding": "base64", "sigVerify": False,
                                               "replaceRecentBlockhash": True, "commitment": "confirmed"}])
    value = (got or {}).get("value") or {}
    if value.get("err") is not None:
        logs = "\n".join((value.get("logs") or [])[-6:])
        raise ChainError(f"the transfer fails in simulation: {json.dumps(value['err'])[:200]}; logs: "
                         f"{json.dumps({'untrusted': logs[:600]})}")


def sol_quote(ctx: Ctx, sender: str, args: dict, asset: str) -> dict:
    from solders.pubkey import Pubkey
    from solders.token.associated import get_associated_token_address
    import sol
    r = ctx.rpc
    to = sol.require_address(args.get("to"))
    if to == sender:
        raise ChainError("the recipient is the sending account itself")
    recipient = _sol_account(r, to)
    if recipient and recipient.get("executable"):
        raise ChainError("the recipient is a program; refused")
    if recipient and recipient.get("owner") in ATA_SPACE:
        raise ChainError("the recipient is a token account; give the owner's wallet address instead")
    rent_floor = evm.h2i(r.call("getMinimumBalanceForRentExemption", [0]))
    balance = (r.call("getBalance", [sender, {"commitment": "confirmed"}]) or {}).get("value", 0)
    fee = SOL_SIG_FEE
    if asset == "native":
        amount, lamports = to_base(args.get("amount"), 9)
        if recipient is None and lamports < rent_floor:
            raise ChainError(f"a new account needs at least {sol.sol(rent_floor)} SOL to exist")
        left = balance - lamports - fee
        if left < 0 or 0 < left < rent_floor:
            raise ChainError(f"the account holds {sol.sol(balance)} SOL; after this transfer and its fee it would "
                             f"keep less than the {sol.sol(rent_floor)} SOL an account needs")
        build = {"kind": "native", "to": to, "lamports": lamports}
        symbol, decimals, address = "SOL", 9, None
    else:
        mint_info = _sol_account(r, asset)
        program = (mint_info or {}).get("owner")
        data = (mint_info or {}).get("data")
        parsed = (data.get("parsed") or {}) if isinstance(data, dict) else {}
        if program not in ATA_SPACE or parsed.get("type") != "mint":
            raise ChainError("that asset is not a token mint")
        decimals = parsed["info"]["decimals"]
        amount, base = to_base(args.get("amount"), decimals)
        source = str(get_associated_token_address(Pubkey.from_string(sender), Pubkey.from_string(asset),
                                                  Pubkey.from_string(program)))
        dest = str(get_associated_token_address(Pubkey.from_string(to), Pubkey.from_string(asset),
                                                Pubkey.from_string(program)))
        held = (r.try_call("getTokenAccountBalance", [source, {"commitment": "confirmed"}])[0] or {}).get("value") or {}
        if int(held.get("amount") or 0) < base:
            raise ChainError(f"the account holds {held.get('uiAmountString') or 0} of this token, less than "
                             f"{plain(amount)}")
        create = _sol_account(r, dest) is None
        if create:
            fee += evm.h2i(r.call("getMinimumBalanceForRentExemption", [ATA_SPACE[program]]))
        if balance < fee:
            raise ChainError(f"the account holds {sol.sol(balance)} SOL, less than the fee of {sol.sol(fee)}")
        build = {"kind": "token", "to": to, "mint": asset, "program": program, "decimals": decimals,
                 "amount_base": base, "source_ata": source, "dest_ata": dest, "create_ata": create}
        symbol = chains.KNOWN_MINTS.get(ctx.chain, {}).get(asset) or "?"
        address = asset
    _sol_simulate(r, build, sender)
    return {"to": to, "ens": None, "symbol": symbol, "decimals": decimals, "amount": plain(amount),
            "asset_address": address, "max_fee": sol.sol(fee), "build": build}


def sol_send(ctx: Ctx, quote: dict, pair) -> str:
    from solders.hash import Hash
    from solders.message import Message
    from solders.transaction import Transaction
    r = ctx.rpc
    latest = r.call("getLatestBlockhash", [{"commitment": "confirmed"}])
    blockhash = Hash.from_string(((latest or {}).get("value") or {})["blockhash"])
    message = Message.new_with_blockhash(_sol_instructions(quote["build"], quote["from"]), pair.pubkey(), blockhash)
    signed = Transaction([pair], message, blockhash)
    raw = base64.b64encode(bytes(signed)).decode()
    return broadcast(r, "sendTransaction", [raw, {"encoding": "base64", "preflightCommitment": "confirmed"}])


# --- operations ---------------------------------------------------------------------------------

def _state(payload: dict) -> Path:
    state = payload.get("state")
    if not isinstance(state, str) or not os.path.isabs(state):
        raise ChainError("the wallet's state directory is missing")
    path = Path(state)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    (path / "quotes").mkdir(mode=0o700, exist_ok=True)
    return path


def _override(payload: dict) -> str | None:
    return payload.get("_rpc") if rpc.testing() else None


def _family(chain) -> str:
    family = chains.family(chain) if isinstance(chain, str) else None
    if family is None:
        raise ChainError(f"unknown chain {chain!r}; use one of: {', '.join(chains.CHAINS)}")
    return family


def _balances(ctx: Ctx, family: str, addresses: list[str]) -> list[str | None]:
    info = chains.info(ctx.chain)
    if family == "evm":
        got = ctx.rpc.batch([("eth_getBalance", [a, "latest"]) for a in addresses])
        return [f"{evm.units(evm.h2i(g), info['decimals'])} {info['symbol']}" if g else None for g in got]
    import sol
    out: list[str | None] = []
    for start in range(0, len(addresses), 100):
        part = addresses[start:start + 100]
        got = ctx.rpc.call("getMultipleAccounts", [part, {"commitment": "confirmed"}]) or {}
        out += [f"{sol.sol((v or {}).get('lamports', 0))} SOL" for v in got.get("value") or [None] * len(part)]
    return out


def op_accounts(payload: dict) -> dict:
    """Every labelled secret and its accounts' addresses; with chain, their native balances there."""
    secrets_ = Secrets(payload)
    count = payload.get("count", LIST_DEFAULT)
    if not isinstance(count, int) or not 1 <= count <= OWN_INDEXES:
        raise ChainError(f"count must be from 1 to {OWN_INDEXES}")
    rows = []
    for source in secrets_.seeds:
        for index in range(count):
            account = f"{source}#{index}"
            rows.append({"account": account, **secrets_.meta[source], "index": index,
                         "evm": secrets_.address_of(account, "evm"), "solana": secrets_.address_of(account, "solana")})
    for source, (kind, _) in secrets_.keys.items():
        rows.append({"account": source, **secrets_.meta[source], kind: secrets_.address_of(source, kind)})
    chain = payload.get("chain")
    if chain:
        family = _family(chain)
        with_address = [row for row in rows if row.get(family)]
        try:
            for row, balance in zip(with_address, _balances(Ctx(chain, _override(payload)), family,
                                                            [row[family] for row in with_address])):
                row["balance"] = balance
        except ChainError as exc:
            for row in with_address:
                row["balance_error"] = str(exc)
    result = {"accounts": rows, "seeds_list": count,
              "note": f"use sign: a Hermes wallet (HERMES in its name) that can send, and whose seeds' accounts "
                      f"0-{OWN_INDEXES - 1} count as own; use watch: a wallet Hermes only reads, never signs with, "
                      "and treats as external. Token balances: chain portfolio"}
    if secrets_.problems:
        result["skipped"] = secrets_.problems
    if not rows:
        result["setup"] = SETUP
    return result


def op_quote(payload: dict) -> dict:
    state = _state(payload)
    chain = payload.get("chain")
    family = _family(chain)
    token = payload.get("token")
    if token in (None, "", "native"):
        asset = "native"
    elif family == "evm" and isinstance(token, str) and re.match(r"^0x[0-9a-fA-F]{40}$", token):
        asset = token.lower()
    elif family == "solana" and isinstance(token, str) and re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token):
        asset = token
    else:
        raise ChainError("token must be a token contract (EVM) or mint (Solana) address; omit it for the native coin")
    secrets_ = Secrets(payload)
    secrets_.require_any()
    account = payload.get("account")
    source, index = secrets_.account(account)
    sender, _ = secrets_.signer(account, family)
    ctx = Ctx(chain, _override(payload))
    built = evm_quote(ctx, sender, payload, asset) if family == "evm" else sol_quote(ctx, sender, payload, asset)
    try:
        ledger.check_rate(state)
    except ledger.CapReached as exc:
        raise ChainError(str(exc)) from None
    recipient = built["to"].lower() if family == "evm" else built["to"]
    own_account = secrets_.addresses(family, "sign").get(recipient)
    watched = None if own_account else secrets_.addresses(family, "watch").get(recipient)
    own = own_account is not None
    now = time.time()
    quote = {"id": "q" + random.token_hex(4), "created": now, "expires": now + QUOTE_TTL, "account": account,
             "source": source, "index": index, "chain": chain, "family": family, "from": sender, "asset": asset,
             "own": own, "watched": watched, "from_party": secrets_.party(account),
             "to_party": secrets_.party(own_account or watched) if (own_account or watched) else None, **built}
    price = None
    if not chains.info(chain)["testnet"]:
        book = prices.Prices(online=not (rpc.testing() and payload.get("_offline")))
        price = book.native(chain) if asset == "native" else book.tokens_usd(chain, [built["asset_address"]]).get(asset)
    quote["usd"] = round(float(Decimal(built["amount"]) * Decimal(str(price))), 2) if price else None
    quote["card"], quote["card_short"] = cards(quote)
    quote["mac"] = secrets_.mac(quote)
    fd = os.open(state / "quotes" / f"{quote['id']}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(quote, handle, ensure_ascii=False)
    return {"quote": quote["id"], "own": own, "card": quote["card"], "expires_in_seconds": QUOTE_TTL,
            "summary": {k: quote[k] for k in ("account", "chain", "from", "to", "ens", "amount", "symbol",
                                              "asset_address", "max_fee", "usd")}}


def load_quote(state: Path, quote_id) -> dict:
    if not isinstance(quote_id, str) or not QUOTE_ID.match(quote_id):
        raise ChainError("quote must be an id like q1a2b3c4d from wallet quote")
    path = state / "quotes" / f"{quote_id}.json"
    if not path.exists():
        raise ChainError(f"no quote {quote_id}; make one with wallet quote")
    return json.loads(path.read_text(encoding="utf-8"))


def op_send(payload: dict) -> dict:
    state = _state(payload)
    approval = payload.get("approval")
    if approval not in ("own", "card"):
        raise ChainError("a send needs the plugin's approval decision")
    with ledger.locked(state):
        quote = load_quote(state, payload.get("quote"))
        secrets_ = Secrets(payload)
        if quote.get("source") not in secrets_.seeds and quote.get("source") not in secrets_.keys:
            raise ChainError("this quote's seed phrase or key is no longer in the Keychain")
        if not hmac.compare_digest(str(quote.get("mac")), secrets_.mac(quote)):
            raise ChainError("this quote was changed after it was made; it is refused")
        if quote.get("consumed"):
            raise ChainError("this quote was already used; make a new one")
        now = time.time()
        if now > quote["expires"]:
            raise ChainError("this quote expired; make a new one")
        family = _family(quote["chain"])
        own = (quote["to"].lower() if family == "evm" else quote["to"]) in secrets_.own(family)
        if approval == "own" and not (own and quote["own"]):
            raise ChainError("this transfer is not to an own account, so it needs the approval card")
        try:
            ledger.check_rate(state, now)
        except ledger.CapReached as exc:
            raise ChainError(str(exc)) from None
        address, secret = secrets_.signer(quote["account"], family)
        if address != quote["from"]:
            raise ChainError("this quote's sending account does not match its secret")
        quote["consumed"] = now
        path = state / "quotes" / f"{quote['id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        row = {"time": now, "quote": quote["id"], "account": quote["account"], "chain": quote["chain"],
               "from": quote["from"], "to": quote["to"], "asset": quote["asset"], "symbol": quote["symbol"],
               "amount": quote["amount"], "max_fee": quote["max_fee"], "own": own, "approval": approval,
               "outcome": "unknown"}
        ledger.append(state, row)
        ctx = Ctx(quote["chain"], _override(payload))
        try:
            sent = evm_send(ctx, quote, secret) if family == "evm" else sol_send(ctx, quote, secret)
        except Unknown:
            # the ledger keeps "unknown", which counts against the hourly cap
            raise ChainError("the send's outcome is unknown (no answer after broadcasting); check the account "
                             "before making a new quote") from None
        except ChainError as exc:
            # refused before or at broadcast: nothing moved
            ledger.append(state, {**row, "outcome": "rejected", "error": str(exc)[:300]})
            raise ChainError(f"not sent: {exc}; make a new quote to try again") from None
        except Exception as exc:
            ledger.append(state, {**row, "outcome": "rejected", "error": type(exc).__name__})
            raise ChainError(f"not sent: the signer failed before broadcasting ({type(exc).__name__})") from None
        ledger.append(state, {**row, "outcome": "sent", "hash": sent})
    return {"sent": True, "hash": sent, "chain": quote["chain"], "amount": quote["amount"], "symbol": quote["symbol"],
            "to": quote["to"], "explorer": chains.explorer(quote["chain"], "tx", sent),
            "note": "use wallet status with this hash for confirmation"}


def op_status(payload: dict) -> dict:
    chain = payload.get("chain")
    family = _family(chain)
    ctx = Ctx(chain, _override(payload))
    tx_hash = payload.get("hash")
    if family == "evm":
        evm.require_hash(tx_hash)
        receipt = ctx.rpc.call("eth_getTransactionReceipt", [tx_hash])
        if not receipt:
            return {"hash": tx_hash, "status": "pending or unknown"}
        head = evm.h2i(ctx.rpc.call("eth_blockNumber"))
        block = evm.h2i(receipt.get("blockNumber"))
        return {"hash": tx_hash, "status": "success" if evm.h2i(receipt.get("status")) == 1 else "failed",
                "block": block, "confirmations": head - block + 1}
    got = ctx.rpc.call("getSignatureStatuses", [[tx_hash], {"searchTransactionHistory": True}])
    value = ((got or {}).get("value") or [None])[0]
    if not value:
        return {"signature": tx_hash, "status": "pending or unknown"}
    return {"signature": tx_hash, "status": "failed" if value.get("err") else value.get("confirmationStatus"),
            "slot": value.get("slot")}


OPS = {"accounts": op_accounts, "quote": op_quote, "send": op_send, "status": op_status}


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
    except Exception as exc:  # never the exception's text: it may hold key material
        reply = {"ok": False, "error": f"the signer failed ({type(exc).__name__})"}
    sys.stdout.write(rpc.mask(json.dumps(reply, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
