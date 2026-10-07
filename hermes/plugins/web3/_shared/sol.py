"""Solana reads of the ``solana`` tool, run in the engine venv (docs/web3.md "Reads").

Transactions and accounts are read with ``jsonParsed``, so the RPC itself decodes the System,
Token, Token-2022, Associated Token Account, Memo and other native programs; other programs'
instructions come back as program id, accounts and data size. Memos and program logs are text
written by strangers and are wrapped as ``{"untrusted": …}``.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import re

import abi
import chains
from prices import usd
from rpc import ChainError

TOP = 5
MAX_INSTRUCTIONS = 60
MAX_LOG_LINES = 60
MAX_TOKENS = 40
LAMPORTS = 10 ** 9
BASE_FEE = 5000  # lamports per signature

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
PROGRAMS = {
    "11111111111111111111111111111111": "System Program",
    TOKEN_PROGRAM: "Token Program",
    TOKEN_2022: "Token-2022",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr": "Memo",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo": "Memo (v1)",
    "ComputeBudget111111111111111111111111111111": "Compute Budget",
    "Vote111111111111111111111111111111111111111": "Vote",
    "Stake11111111111111111111111111111111111111": "Stake",
    "AddressLookupTab1e1111111111111111111111111": "Address Lookup Table",
    "BPFLoaderUpgradeab1e11111111111111111111111": "BPF Upgradeable Loader",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s": "Metaplex Token Metadata",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator v6",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun",
}
_ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,90}$")


def when(timestamp) -> str | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def sol(lamports: int) -> str:
    text = format(Decimal(lamports) / LAMPORTS, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def program_name(program_id: str | None) -> str | None:
    return PROGRAMS.get(program_id or "")


def require_address(value) -> str:
    if not isinstance(value, str) or not _ADDRESS.match(value.strip()):
        raise ChainError("a Solana address (base58) is required")
    return value.strip()


def _native(ctx) -> dict:
    return chains.SOLANA[ctx.chain]


# --- block --------------------------------------------------------------------------------------

def block(ctx, args) -> dict:
    ref = args.get("block")
    if ref in (None, "", "latest"):
        slot = ctx.rpc.call("getSlot", [{"commitment": "finalized"}])
    elif isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        slot = int(ref)
    else:
        raise ChainError("block must be a slot number or latest")
    detail = bool(args.get("detail"))
    config = {"encoding": "json", "maxSupportedTransactionVersion": 0, "rewards": True,
              "transactionDetails": "full" if detail else "signatures", "commitment": "finalized"}
    data = ctx.rpc.call("getBlock", [slot, config])
    if not data:
        raise ChainError(f"slot {slot} has no block (skipped or not yet finalized)")
    leader = ctx.rpc.try_call("getSlotLeaders", [slot, 1])[0]
    price = ctx.prices.native(ctx.chain)
    rewards = data.get("rewards") or []
    fee_reward = sum(r.get("lamports", 0) for r in rewards if r.get("rewardType") == "Fee")
    result = {"chain": ctx.chain, "slot": slot, "block_height": data.get("blockHeight"),
              "time": when(data.get("blockTime")), "blockhash": data.get("blockhash"),
              "parent_slot": data.get("parentSlot"), "leader": (leader or [None])[0],
              "leader_fee_reward": sol(fee_reward), "leader_fee_reward_usd": usd(fee_reward / LAMPORTS, price),
              "explorer": chains.explorer(ctx.chain, "slot", str(slot))}
    if not detail:
        result["transactions"] = len(data.get("signatures") or [])
        return result
    txs = data.get("transactions") or []
    programs, fees, failed, votes = Counter(), [], 0, 0
    for entry in txs:
        meta, message = entry.get("meta") or {}, (entry.get("transaction") or {}).get("message") or {}
        keys = message.get("accountKeys") or []
        invoked = {keys[ix["programIdIndex"]] for ix in message.get("instructions") or []
                   if ix.get("programIdIndex") is not None and ix["programIdIndex"] < len(keys)}
        if "Vote111111111111111111111111111111111111111" in invoked:
            votes += 1
            continue
        programs.update(invoked)
        failed += meta.get("err") is not None
        fees.append((meta.get("fee", 0), (entry.get("transaction") or {}).get("signatures", [None])[0],
                     meta.get("computeUnitsConsumed")))
    fees.sort(key=lambda item: item[0], reverse=True)
    total = sum(fee for fee, _, _ in fees)
    result.update({
        "transactions": len(txs), "vote_transactions": votes, "non_vote_transactions": len(txs) - votes,
        "failed_non_vote": failed, "fees_total": sol(total), "fees_total_usd": usd(total / LAMPORTS, price),
        "most_invoked_programs": [{"program": p, "name": program_name(p), "transactions": n}
                                  for p, n in programs.most_common(TOP)],
        "top_by_fee": [{"signature": s, "fee": sol(f), "compute_units": cu} for f, s, cu in fees[:TOP]],
    })
    return result


# --- transaction --------------------------------------------------------------------------------

def tx(ctx, args) -> dict:
    signature = args.get("hash") or args.get("signature")
    if not isinstance(signature, str) or not _SIGNATURE.match(signature):
        raise ChainError("hash must be a base58 transaction signature")
    data = ctx.rpc.call("getTransaction", [signature, {"encoding": "jsonParsed", "commitment": "confirmed",
                                                       "maxSupportedTransactionVersion": 0}])
    if not data:
        raise ChainError(f"transaction {signature[:16]}… not found on {ctx.chain} (or not yet confirmed)")
    meta = data.get("meta") or {}
    message = (data.get("transaction") or {}).get("message") or {}
    keys = message.get("accountKeys") or []
    price = ctx.prices.native(ctx.chain)
    result = {
        "chain": ctx.chain, "signature": signature, "slot": data.get("slot"), "time": when(data.get("blockTime")),
        "status": "success" if meta.get("err") is None else "failed",
        "version": data.get("version"), "fee": sol(meta.get("fee", 0)),
        "fee_usd": usd(meta.get("fee", 0) / LAMPORTS, price),
        "compute_units": meta.get("computeUnitsConsumed"),
        "signers": [k.get("pubkey") for k in keys if k.get("signer")],
        "explorer": chains.explorer(ctx.chain, "tx", signature),
    }
    if meta.get("err") is not None:
        result["error"] = meta["err"]
    inner = {group.get("index"): group.get("instructions") or [] for group in meta.get("innerInstructions") or []}
    instructions = []
    for index, ix in enumerate((message.get("instructions") or [])[:MAX_INSTRUCTIONS]):
        entry = _instruction(ix)
        if inner.get(index):
            entry["inner"] = [_instruction(i) for i in inner[index][:MAX_INSTRUCTIONS]]
        instructions.append(entry)
    result["instructions"] = instructions
    result["balance_changes"] = _balance_changes(meta, keys)
    lines = meta.get("logMessages") or []
    result["logs"] = abi.untrusted("\n".join(lines[:MAX_LOG_LINES]))
    if len(lines) > MAX_LOG_LINES:
        result["logs_omitted"] = len(lines) - MAX_LOG_LINES
    return result


def _instruction(ix: dict) -> dict:
    program_id = ix.get("programId")
    entry = {"program": program_id, "name": program_name(program_id) or ix.get("program")}
    parsed = ix.get("parsed")
    if isinstance(parsed, dict):
        entry["type"] = parsed.get("type")
        entry["info"] = parsed.get("info")
    elif isinstance(parsed, str):  # the Memo program
        entry["memo"] = abi.untrusted(parsed)
    else:
        entry["accounts"] = len(ix.get("accounts") or [])
        entry["data_size"] = len(_b58decode(ix.get("data") or ""))
    return entry


def _b58decode(text: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in text:
        if char not in alphabet:
            return b""
        number = number * 58 + alphabet.index(char)
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * (len(text) - len(text.lstrip("1"))) + raw


def _balance_changes(meta: dict, keys: list[dict]) -> list[dict]:
    changes: dict[str, list] = defaultdict(list)
    pre, post = meta.get("preBalances") or [], meta.get("postBalances") or []
    for i, key in enumerate(keys):
        if i < len(pre) and i < len(post) and pre[i] != post[i]:
            changes[key.get("pubkey")].append({"asset": "SOL", "change": sol(post[i] - pre[i])})
    tokens: dict[tuple, dict] = {}
    for side, rows in (("pre", meta.get("preTokenBalances") or []), ("post", meta.get("postTokenBalances") or [])):
        for row in rows:
            key = (row.get("accountIndex"), row.get("mint"))
            amount = row.get("uiTokenAmount") or {}
            slot = tokens.setdefault(key, {"owner": row.get("owner"), "mint": row.get("mint"),
                                           "decimals": amount.get("decimals"), "pre": 0, "post": 0})
            slot[side] = int(amount.get("amount") or 0)
            slot["owner"] = slot["owner"] or row.get("owner")
    for slot in tokens.values():
        delta = slot["post"] - slot["pre"]
        if delta:
            decimals = slot["decimals"] or 0
            text = format(Decimal(delta) / (Decimal(10) ** decimals), "f")
            text = text.rstrip("0").rstrip(".") if "." in text else text
            changes[slot["owner"] or "unknown owner"].append({"mint": slot["mint"], "change": text})
    return [{"account": account, "changes": rows} for account, rows in changes.items()]


# --- address, token, portfolio, activity --------------------------------------------------------

def address(ctx, args) -> dict:
    target = require_address(args.get("address"))
    info = ctx.rpc.call("getAccountInfo", [target, {"encoding": "jsonParsed", "commitment": "confirmed"}])
    value = (info or {}).get("value")
    price = ctx.prices.native(ctx.chain)
    result = {"chain": ctx.chain, "address": target, "explorer": chains.explorer(ctx.chain, "account", target)}
    if not value:
        result.update(exists=False, balance="0", note="no account at this address (never funded or closed)")
        return result
    lamports = value.get("lamports", 0)
    owner = value.get("owner")
    result.update(exists=True, balance=sol(lamports), symbol="SOL", balance_usd=usd(lamports / LAMPORTS, price),
                  owner_program=owner, owner_name=program_name(owner), executable=value.get("executable"),
                  data_size=value.get("space"))
    data = value.get("data")
    if isinstance(data, dict) and isinstance(data.get("parsed"), dict):
        result["parsed"] = {"type": data["parsed"].get("type"), "info": data["parsed"].get("info")}
    if owner == "11111111111111111111111111111111" and not value.get("executable"):
        result["kind"] = "wallet (system account)"
    elif value.get("executable"):
        result["kind"] = "program"
    elif owner in (TOKEN_PROGRAM, TOKEN_2022):
        result["kind"] = f"token {(result.get('parsed') or {}).get('type') or 'account'}"
    else:
        result["kind"] = "data account"
    return result


def token(ctx, args) -> dict:
    mint = require_address(args.get("token") or args.get("address"))
    info = ctx.rpc.call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    value = (info or {}).get("value") or {}
    parsed = ((value.get("data") or {}).get("parsed") or {}) if isinstance(value.get("data"), dict) else {}
    if parsed.get("type") != "mint":
        raise ChainError("that address is not a token mint")
    details = parsed.get("info") or {}
    decimals = details.get("decimals") or 0
    supply = int(details.get("supply") or 0)
    text = format(Decimal(supply) / (Decimal(10) ** decimals), "f")
    result = {"chain": ctx.chain, "mint": mint, "program": program_name(value.get("owner")),
              "known_symbol": chains.KNOWN_MINTS.get(ctx.chain, {}).get(mint),
              "decimals": decimals, "supply": text.rstrip("0").rstrip(".") if "." in text else text,
              "mint_authority": details.get("mintAuthority"), "freeze_authority": details.get("freezeAuthority"),
              "explorer": chains.explorer(ctx.chain, "token", mint)}
    if details.get("extensions"):
        result["extensions"] = [e.get("extension") for e in details["extensions"]]
    if result["mint_authority"]:
        result["warning"] = "the mint authority can still create more of this token"
    market = ctx.prices.token_market(ctx.chain, mint)
    if market:
        result["market"] = market
    return result


def _token_accounts(ctx, owner: str) -> list[dict]:
    rows = []
    for program in (TOKEN_PROGRAM, TOKEN_2022):
        got = ctx.rpc.call("getTokenAccountsByOwner", [owner, {"programId": program},
                                                       {"encoding": "jsonParsed", "commitment": "confirmed"}])
        for item in (got or {}).get("value") or []:
            info = (((item.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
            rows.append({"account": item.get("pubkey"), "program": program, **info})
    return rows


def portfolio(ctx, args) -> dict:
    owner = require_address(args.get("address"))
    lamports = (ctx.rpc.call("getBalance", [owner, {"commitment": "confirmed"}]) or {}).get("value", 0)
    price = ctx.prices.native(ctx.chain)
    holdings: dict[str, dict] = {}
    for row in _token_accounts(ctx, owner):
        amount = row.get("tokenAmount") or {}
        if not int(amount.get("amount") or 0):
            continue
        slot = holdings.setdefault(row.get("mint"), {"raw": 0, "decimals": amount.get("decimals") or 0})
        slot["raw"] += int(amount["amount"])
    prices = ctx.prices.tokens_usd(ctx.chain, list(holdings)) if holdings else {}
    known = chains.KNOWN_MINTS.get(ctx.chain, {})
    rows = []
    for mint, slot in holdings.items():
        amount = Decimal(slot["raw"]) / (Decimal(10) ** slot["decimals"])
        text = format(amount, "f")
        rows.append({"mint": mint, "known_symbol": known.get(mint),
                     "balance": text.rstrip("0").rstrip(".") if "." in text else text,
                     "usd": usd(float(amount), prices.get(mint))})
    rows.sort(key=lambda r: r["usd"] or -1, reverse=True)
    native_usd = usd(lamports / LAMPORTS, price)
    total = (native_usd or 0) + sum(r["usd"] or 0 for r in rows)
    return {"chain": ctx.chain, "address": owner, "native": {"symbol": "SOL", "balance": sol(lamports),
                                                             "usd": native_usd},
            "tokens": rows[:MAX_TOKENS], "tokens_omitted": max(len(rows) - MAX_TOKENS, 0),
            "unpriced_tokens": sum(1 for r in rows if r["usd"] is None), "total_usd": round(total, 2),
            "note": "only known mints carry a symbol; unpriced tokens are often spam"}


def activity(ctx, args) -> dict:
    owner = require_address(args.get("address"))
    limit = args.get("limit") or 20
    if not isinstance(limit, int) or limit < 1:
        raise ChainError("limit must be a positive integer")
    got = ctx.rpc.call("getSignaturesForAddress", [owner, {"limit": min(limit, 50), "commitment": "confirmed"}])
    return {"chain": ctx.chain, "address": owner, "signatures": [
        {"signature": row.get("signature"), "slot": row.get("slot"), "time": when(row.get("blockTime")),
         "status": "failed" if row.get("err") else "success",
         **({"memo": abi.untrusted(row["memo"])} if row.get("memo") else {})} for row in got or []],
        "note": "use tx on a signature for what it did"}


def allowances(ctx, args) -> dict:
    owner = require_address(args.get("address"))
    delegated = []
    for row in _token_accounts(ctx, owner):
        if row.get("delegate"):
            delegated.append({"token_account": row.get("account"), "mint": row.get("mint"),
                              "delegate": row["delegate"], "delegated_amount": (row.get("delegatedAmount") or {})
                              .get("uiAmountString")})
    return {"chain": ctx.chain, "address": owner, "delegations": delegated,
            "note": "a delegate can move up to the delegated amount from that token account"}


# --- decode, gas, price -------------------------------------------------------------------------

def decode(ctx, args) -> dict:
    from solders.transaction import Transaction, VersionedTransaction
    text = args.get("data")
    if not isinstance(text, str) or not text:
        raise ChainError("data must be a base64 or base58 transaction")
    raw = None
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception:
        raw = _b58decode(text) or None
    if not raw:
        raise ChainError("data is neither base64 nor base58")
    try:
        transaction = VersionedTransaction.from_bytes(raw)
        message = transaction.message
        legacy = False
    except Exception:
        try:
            transaction = Transaction.from_bytes(raw)
            message = transaction.message
            legacy = True
        except Exception as exc:
            raise ChainError("data does not parse as a Solana transaction") from exc
    keys = [str(k) for k in message.account_keys]
    header = message.header
    signers = keys[:header.num_required_signatures]
    signed = [str(s) for s in transaction.signatures if any(bytes(s))]
    out = {"kind": "transaction", "version": "legacy" if legacy or not hasattr(message, "address_table_lookups")
           else "v0", "recent_blockhash": str(message.recent_blockhash), "signers": signers,
           "signatures_present": len(signed), "instructions": []}
    lookups = getattr(message, "address_table_lookups", None) or []
    if lookups:
        out["address_lookup_tables"] = [str(l.account_key) for l in lookups]
    for ix in message.instructions:
        program = keys[ix.program_id_index] if ix.program_id_index < len(keys) else None
        data = bytes(ix.data)
        entry = {"program": program, "name": program_name(program),
                 "accounts": [keys[i] if i < len(keys) else f"lookup #{i}" for i in ix.accounts],
                 "data_size": len(data)}
        entry.update(_known_instruction(program, data, entry["accounts"]))
        out["instructions"].append(entry)
    return out


def _known_instruction(program: str | None, data: bytes, accounts: list[str]) -> dict:
    if program == "11111111111111111111111111111111" and len(data) >= 12 and \
            int.from_bytes(data[:4], "little") == 2:
        return {"type": "transfer", "from": accounts[0] if accounts else None,
                "to": accounts[1] if len(accounts) > 1 else None, "sol": sol(int.from_bytes(data[4:12], "little"))}
    if program in (TOKEN_PROGRAM, TOKEN_2022) and data:
        if data[0] == 12 and len(data) >= 10:
            return {"type": "transferChecked", "source": accounts[0] if accounts else None,
                    "mint": accounts[1] if len(accounts) > 1 else None,
                    "destination": accounts[2] if len(accounts) > 2 else None,
                    "authority": accounts[3] if len(accounts) > 3 else None,
                    "amount": int.from_bytes(data[1:9], "little"), "decimals": data[9]}
        if data[0] == 3 and len(data) >= 9:
            return {"type": "transfer", "source": accounts[0] if accounts else None,
                    "destination": accounts[1] if len(accounts) > 1 else None,
                    "amount": int.from_bytes(data[1:9], "little")}
        if data[0] == 4 and len(data) >= 9:
            return {"type": "approve", "delegate": accounts[1] if len(accounts) > 1 else None,
                    "amount": int.from_bytes(data[1:9], "little"),
                    "warning": "lets the delegate move tokens from the source account"}
        if data[0] == 6:
            return {"type": "setAuthority", "warning": "changes who controls a token account or mint"}
    if program == "ComputeBudget111111111111111111111111111111" and data:
        if data[0] == 2 and len(data) >= 5:
            return {"type": "setComputeUnitLimit", "units": int.from_bytes(data[1:5], "little")}
        if data[0] == 3 and len(data) >= 9:
            return {"type": "setComputeUnitPrice", "micro_lamports": int.from_bytes(data[1:9], "little")}
    return {}


def gas(ctx, args) -> dict:
    fees = ctx.rpc.call("getRecentPrioritizationFees", [[]]) or []
    values = sorted(f.get("prioritizationFee", 0) for f in fees)

    def pick(q):
        return values[min(int(len(values) * q), len(values) - 1)] if values else 0

    price = ctx.prices.native(ctx.chain)
    return {"chain": ctx.chain, "base_fee_per_signature": sol(BASE_FEE),
            "base_fee_usd": usd(BASE_FEE / LAMPORTS, price),
            "priority_fee_micro_lamports_per_cu": {"low": pick(0.25), "medium": pick(0.5), "high": pick(0.9)},
            "samples": len(values)}


def price(ctx, args) -> dict:
    query = args.get("token") or args.get("symbol")
    if not query:
        raise ChainError("price needs symbol (e.g. SOL) or token (a mint address)")
    if isinstance(query, str) and _ADDRESS.match(query) and len(query) >= 32:
        market = ctx.prices.token_market(ctx.chain, query)
        return {"chain": ctx.chain, "mint": query, "market": market,
                **({} if market else {"note": "no price found (devnet has none)"})}
    found = ctx.prices.lookup(str(query))
    return {"query": str(query), "market": found, **({} if found else {"note": "no matching coin found"})}


ACTIONS = {"block": block, "tx": tx, "address": address, "portfolio": portfolio, "activity": activity,
           "token": token, "allowances": allowances, "decode": decode, "gas": gas, "price": price}
