"""The wallet's signer: one operation per process, run by the web3 venv's interpreter.

The only code that reads seed phrases: ``WEB3_SEED_<NAME>`` items from the Keychain scope
``web3-wallet``, stdin closed, one per seed the settings name. Seeds, derived keys and raw signed
transactions stay in this process: replies carry addresses, quotes, approval card text and
transaction hashes, and every string leaving is scrubbed of the phrases it read.

    {"op": "derive" | "accounts" | "quote" | "send" | "status", "settings": {…normalized…},
     "state": "<the wallet's state directory>", …the op's arguments}
    → {"ok": true, "data": {…}} or {"ok": false, "error": "…"}

A quote is the exact transfer, built and simulated, stored as a single-use file that expires after
``QUOTE_TTL`` and carries an HMAC keyed from its sending seed, so neither its transaction nor its
card can be edited between approval and send. ``send`` re-checks the MAC, the expiry, the hourly
cap and — for a send approved as own — that the recipient really is one of the seeds' addresses;
the quote is consumed and written to the ledger before it is broadcast. ``_seeds`` (name → phrase)
and ``_rpc`` are honoured only under the engine's tests (``WEB3_ENGINE_TEST=1``).
Contract: docs/web3.md "Transfers" and "Approval".
"""

from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
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
import prices  # noqa: E402
import rpc  # noqa: E402
from rpc import ChainError  # noqa: E402
import settings as conf  # noqa: E402

SCOPE = "web3-wallet"
QUOTE_TTL = 900            # outlives the 600 s approval wait
OWN_INDEXES = 20           # each seed's accounts 0..19 count as own, configured or not
GAS_MARGIN = Decimal("1.2")
SOL_SIG_FEE = 5000
ATA_SPACE = {"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": 165, "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": 170}
SYSTEM = "11111111111111111111111111111111"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
QUOTE_ID = re.compile(r"^q[0-9a-f]{8}$")
SYMBOL = re.compile(r"^[A-Za-z0-9.$_-]{1,12}$")


def seed_set(name: str) -> str:
    return f"secret set {conf.seed_item(name)} -p hermes --scope {SCOPE} -D MNEMONIC"


# --- keys ---------------------------------------------------------------------------------------

class Keys:
    """The seeds of one call, held in memory only."""

    def __init__(self, payload: dict, names: list[str]):
        from eth_account.hdaccount import seed_from_mnemonic
        from mnemonic import Mnemonic
        test = rpc.testing()
        overrides = payload.get("_seeds") if test else None
        self.seeds: dict[str, bytes] = {}
        for name in names:
            words = (overrides or {}).get(name) if overrides is not None else rpc.secret(conf.seed_item(name), SCOPE)
            if not words:
                raise ChainError(f"seed {name!r} is not in the Keychain; the user stores it with `{seed_set(name)}`")
            rpc.SECRETS.append(words)
            words = " ".join(words.split())
            rpc.SECRETS.append(words)
            if not Mnemonic("english").check(words):
                raise ChainError(f"{conf.seed_item(name)} is not a valid English BIP39 phrase; the user stores it again")
            self.seeds[name] = seed_from_mnemonic(words, "")

    def evm_key(self, seed: str, index: int) -> bytes:
        from eth_account.hdaccount import key_from_seed
        return key_from_seed(self.seeds[seed], f"m/44'/60'/0'/0/{index}")

    def sol_keypair(self, seed: str, index: int):
        from solders.keypair import Keypair
        return Keypair.from_seed_and_derivation_path(self.seeds[seed], f"m/44'/501'/{index}'/0'")

    @staticmethod
    def evm_address(key: bytes) -> str:
        from eth_account import Account
        return Account.from_key(key).address

    def address(self, seed: str, index: int, family: str) -> str:
        if family == "evm":
            return self.evm_address(self.evm_key(seed, index))
        return str(self.sol_keypair(seed, index).pubkey())

    def signer(self, account: dict, family: str):
        """(address, signing secret) of a settings account on a chain family."""
        if family == "evm":
            key = self.evm_key(account["seed"], account["index"])
            return self.evm_address(key), key
        pair = self.sol_keypair(account["seed"], account["index"])
        return str(pair.pubkey()), pair

    def own(self, family: str, settings: dict) -> set[str]:
        """Every address the seeds control: each seed's accounts 0..19 and every configured account."""
        pairs = {(seed, i) for seed in self.seeds for i in range(OWN_INDEXES)}
        pairs |= {(a["seed"], a["index"]) for a in settings["accounts"].values() if a["seed"] in self.seeds}
        found = {self.address(seed, index, family) for seed, index in pairs}
        return {a.lower() for a in found} if family == "evm" else found

    def mac(self, quote: dict) -> str:
        """Keyed from the quote's sending seed; covers everything but the MAC and the consumed mark."""
        key = hashlib.sha256(b"hermes-web3-quote\x00" + self.seeds[quote["seed"]]).digest()
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


def card(quote: dict) -> str:
    """The approval card: one fact per line, every value from this quote, addresses in full. A token's
    symbol is whatever its contract says, so it is quoted and the token's address follows."""
    info = chains.info(quote["chain"])
    if quote["asset"] == "native":
        what = f"{quote['amount']} {quote['symbol']}"
    else:
        what = f"{quote['amount']} of token \"{quote['symbol']}\""
    if quote.get("usd") is not None:
        what += f" (≈ ${quote['usd']:,.2f})"
    lines = [f"Send {what} on {info['name']}"]
    if quote["asset"] != "native":
        lines.append(f"Token: {quote['asset_address']}")
    lines.append(f"From: {quote['role']} {quote['from']}")
    lines.append(f"To: {(quote['ens'] + ' = ') if quote.get('ens') else ''}{quote['to']} "
                 f"({'your own account' if quote['own'] else 'external'})")
    lines.append(f"Max fee: {quote['max_fee']} {info['symbol']}")
    expires = datetime.fromtimestamp(quote["expires"]).astimezone().strftime("%H:%M UTC%z")
    lines.append(f"Quote: {quote['id']}, expires {expires}")
    return "\n".join(lines)


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


def _chain(settings: dict, chain) -> str:
    family = chains.family(chain) if isinstance(chain, str) else None
    if family is None:
        raise ChainError(f"unknown chain {chain!r}; use one of: {', '.join(chains.CHAINS)}")
    if not conf.chain_allowed(settings, chains.info(chain)["testnet"]):
        raise ChainError(f"{chain} is a mainnet and mainnet is off; the user sets mainnet: true in "
                         f"{conf.FILE} after trying the testnets")
    return family


def _account(settings: dict, role) -> dict:
    account = settings["accounts"].get(role)
    if account is None:
        raise ChainError(f"no account {role!r}; the accounts are " + ", ".join(settings["accounts"]))
    return account


def op_derive(payload: dict, settings: dict) -> dict:
    """One seed's first accounts on both families, for funding before any account is named."""
    seed, count = payload.get("seed"), payload.get("count", 3)
    if not isinstance(seed, str) or not conf.NAME.match(seed):
        raise ChainError("seed must be a seed name like main")
    if not isinstance(count, int) or not 1 <= count <= OWN_INDEXES:
        raise ChainError(f"count must be from 1 to {OWN_INDEXES}")
    keys = Keys(payload, [seed])
    return {"seed": seed, "accounts": [{"index": i, "evm": keys.address(seed, i, "evm"),
                                        "solana": keys.address(seed, i, "solana")} for i in range(count)]}


def op_accounts(payload: dict, settings: dict) -> dict:
    """Every account's addresses; with chain, also its native balance there."""
    keys = Keys(payload, settings["seeds"])
    chain = payload.get("chain")
    family = _chain(settings, chain) if chain else None
    ctx = Ctx(chain, _override(payload)) if chain else None
    rows = []
    for role, account in settings["accounts"].items():
        row = {"account": role, "seed": account["seed"], "index": account["index"],
               "evm": keys.address(account["seed"], account["index"], "evm"),
               "solana": keys.address(account["seed"], account["index"], "solana")}
        if ctx:
            info = chains.info(chain)
            try:
                if family == "evm":
                    wei = evm.h2i(ctx.rpc.call("eth_getBalance", [row["evm"], "latest"]))
                    row["balance"] = f"{evm.units(wei, info['decimals'])} {info['symbol']}"
                else:
                    import sol
                    got = ctx.rpc.call("getBalance", [row["solana"], {"commitment": "confirmed"}]) or {}
                    row["balance"] = f"{sol.sol(got.get('value', 0))} SOL"
            except ChainError as exc:
                row["balance_error"] = str(exc)
        rows.append(row)
    return {"mainnet": settings["mainnet"], "accounts": rows,
            "note": "token balances: chain portfolio on an address"}


def op_quote(payload: dict, settings: dict) -> dict:
    state = _state(payload)
    account = _account(settings, payload.get("account"))
    chain = payload.get("chain")
    family = _chain(settings, chain)
    token = payload.get("token")
    if token in (None, "", "native"):
        asset = "native"
    elif family == "evm" and isinstance(token, str) and re.match(r"^0x[0-9a-fA-F]{40}$", token):
        asset = token.lower()
    elif family == "solana" and isinstance(token, str) and re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token):
        asset = token
    else:
        raise ChainError("token must be a token contract (EVM) or mint (Solana) address; omit it for the native coin")
    keys = Keys(payload, settings["seeds"])
    sender, _ = keys.signer(account, family)
    ctx = Ctx(chain, _override(payload))
    built = evm_quote(ctx, sender, payload, asset) if family == "evm" else sol_quote(ctx, sender, payload, asset)
    try:
        conf.check_rate(state)
    except conf.SettingsError as exc:
        raise ChainError(str(exc)) from None
    own = (built["to"].lower() if family == "evm" else built["to"]) in keys.own(family, settings)
    now = time.time()
    quote = {"id": "q" + random.token_hex(4), "created": now, "expires": now + QUOTE_TTL,
             "role": payload["account"], "seed": account["seed"], "index": account["index"], "chain": chain,
             "family": family, "from": sender, "asset": asset, "own": own, **built}
    price = None
    if not chains.info(chain)["testnet"]:
        book = prices.Prices(online=not (rpc.testing() and payload.get("_offline")))
        price = book.native(chain) if asset == "native" else book.tokens_usd(chain, [built["asset_address"]]).get(asset)
    quote["usd"] = round(float(Decimal(built["amount"]) * Decimal(str(price))), 2) if price else None
    quote["card"] = card(quote)
    quote["mac"] = keys.mac(quote)
    fd = os.open(state / "quotes" / f"{quote['id']}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(quote, handle, ensure_ascii=False)
    return {"quote": quote["id"], "own": own, "card": quote["card"], "expires_in_seconds": QUOTE_TTL,
            "summary": {k: quote[k] for k in ("role", "chain", "from", "to", "ens", "amount", "symbol",
                                              "asset_address", "max_fee", "usd")}}


def load_quote(state: Path, quote_id) -> dict:
    if not isinstance(quote_id, str) or not QUOTE_ID.match(quote_id):
        raise ChainError("quote must be an id like q1a2b3c4d from wallet quote")
    path = state / "quotes" / f"{quote_id}.json"
    if not path.exists():
        raise ChainError(f"no quote {quote_id}; make one with wallet quote")
    return json.loads(path.read_text(encoding="utf-8"))


def op_send(payload: dict, settings: dict) -> dict:
    state = _state(payload)
    approval = payload.get("approval")
    if approval not in ("own", "card"):
        raise ChainError("a send needs the plugin's approval decision")
    with conf.locked(state):
        quote = load_quote(state, payload.get("quote"))
        if quote.get("seed") not in settings["seeds"]:
            raise ChainError("this quote's seed is no longer in the settings")
        keys = Keys(payload, settings["seeds"])
        if not hmac.compare_digest(str(quote.get("mac")), keys.mac(quote)):
            raise ChainError("this quote was changed after it was made; it is refused")
        if quote.get("consumed"):
            raise ChainError("this quote was already used; make a new one")
        now = time.time()
        if now > quote["expires"]:
            raise ChainError("this quote expired; make a new one")
        family = _chain(settings, quote["chain"])
        own = (quote["to"].lower() if family == "evm" else quote["to"]) in keys.own(family, settings)
        if approval == "own" and not (own and quote["own"]):
            raise ChainError("this transfer is not to an own account, so it needs the approval card")
        try:
            conf.check_rate(state, now)
        except conf.SettingsError as exc:
            raise ChainError(str(exc)) from None
        address, secret = keys.signer({"seed": quote["seed"], "index": quote["index"]}, family)
        if address != quote["from"]:
            raise ChainError("this quote's sending account does not match its seed")
        quote["consumed"] = now
        path = state / "quotes" / f"{quote['id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        row = {"time": now, "quote": quote["id"], "account": quote["role"], "seed": quote["seed"],
               "chain": quote["chain"], "from": quote["from"], "to": quote["to"], "asset": quote["asset"],
               "symbol": quote["symbol"], "amount": quote["amount"], "max_fee": quote["max_fee"], "own": own,
               "approval": approval, "outcome": "unknown"}
        conf.append(state, row)
        ctx = Ctx(quote["chain"], _override(payload))
        try:
            sent = evm_send(ctx, quote, secret) if family == "evm" else sol_send(ctx, quote, secret)
        except Unknown:
            # the ledger keeps "unknown", which counts against the hourly cap
            raise ChainError("the send's outcome is unknown (no answer after broadcasting); check the account "
                             "before making a new quote") from None
        except ChainError as exc:
            # refused before or at broadcast: nothing moved
            conf.append(state, {**row, "outcome": "rejected", "error": str(exc)[:300]})
            raise ChainError(f"not sent: {exc}; make a new quote to try again") from None
        except Exception as exc:
            conf.append(state, {**row, "outcome": "rejected", "error": type(exc).__name__})
            raise ChainError(f"not sent: the signer failed before broadcasting ({type(exc).__name__})") from None
        conf.append(state, {**row, "outcome": "sent", "hash": sent})
    return {"sent": True, "hash": sent, "chain": quote["chain"], "amount": quote["amount"], "symbol": quote["symbol"],
            "to": quote["to"], "explorer": chains.explorer(quote["chain"], "tx", sent),
            "note": "use wallet status with this hash for confirmation"}


def op_status(payload: dict, settings: dict) -> dict:
    chain = payload.get("chain")
    if not isinstance(chain, str) or chains.family(chain) is None:
        raise ChainError("status needs the chain")
    ctx = Ctx(chain, _override(payload))
    tx_hash = payload.get("hash")
    if chains.family(chain) == "evm":
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


OPS = {"derive": op_derive, "accounts": op_accounts, "quote": op_quote, "send": op_send, "status": op_status}


def run(payload: dict) -> dict:
    op = payload.get("op")
    if op not in OPS:
        raise ChainError(f"unknown op {op!r}")
    if op == "derive":  # setup: no settings yet, nothing that signs
        return op_derive(payload, {})
    try:
        settings = conf.parse(payload.get("settings"))
    except conf.SettingsError as exc:
        raise ChainError(f"{conf.FILE}: {exc}") from None
    return OPS[op](payload, settings)


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
