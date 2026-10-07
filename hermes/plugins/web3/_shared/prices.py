"""USD price estimates from CoinGecko's public API (docs/web3.md "Chains and RPC").

Prices are estimates for reading only: nothing that signs or limits a transfer uses them.
Testnets have none. A failed lookup is an absent price, never an error.
"""

from __future__ import annotations

import urllib.parse

import chains
from rpc import http_json

API = "https://api.coingecko.com/api/v3"
BATCH = 30


class Prices:
    def __init__(self, online: bool = True):
        self.online = online
        self.coins: dict[str, float | None] = {}
        self.tokens: dict[tuple[str, str], float | None] = {}

    def native(self, chain: str) -> float | None:
        coin = chains.info(chain).get("coin")
        if not coin or not self.online:
            return None
        if coin not in self.coins:
            data = http_json(f"{API}/simple/price?ids={coin}&vs_currencies=usd")
            self.coins[coin] = (data or {}).get(coin, {}).get("usd") if isinstance(data, dict) else None
        return self.coins[coin]

    def tokens_usd(self, chain: str, addresses: list[str]) -> dict[str, float]:
        """Prices by address (lowercased for EVM, as given for Solana mints)."""
        platform = chains.info(chain).get("platform")
        if not platform or not self.online:
            return {}
        keys = [a.lower() if chain in chains.EVM else a for a in addresses]
        missing = [k for k in keys if (platform, k) not in self.tokens]
        for start in range(0, len(missing), BATCH):
            part = missing[start:start + BATCH]
            data = http_json(f"{API}/simple/token_price/{platform}?contract_addresses="
                             f"{urllib.parse.quote(','.join(part))}&vs_currencies=usd")
            data = data if isinstance(data, dict) else {}
            lowered = {k.lower(): v for k, v in data.items()}
            for key in part:
                entry = data.get(key) or lowered.get(key.lower()) or {}
                self.tokens[(platform, key)] = entry.get("usd") if isinstance(entry, dict) else None
        return {k: self.tokens[(platform, k)] for k in keys if self.tokens.get((platform, k)) is not None}

    def lookup(self, query: str) -> dict | None:
        """Market data of a coin by symbol or name: the best-ranked exact symbol match."""
        if not self.online:
            return None
        found = http_json(f"{API}/search?query={urllib.parse.quote(query)}")
        coins = (found or {}).get("coins") or [] if isinstance(found, dict) else []
        exact = [c for c in coins if str(c.get("symbol", "")).lower() == query.lower()] or coins
        exact = sorted(exact, key=lambda c: c.get("market_cap_rank") or 10 ** 9)
        if not exact:
            return None
        coin = exact[0]
        data = http_json(f"{API}/simple/price?ids={coin['id']}&vs_currencies=usd&include_24hr_change=true"
                         "&include_market_cap=true&include_24hr_vol=true")
        entry = (data or {}).get(coin["id"]) if isinstance(data, dict) else None
        if not entry:
            return None
        return {"id": coin["id"], "rank": coin.get("market_cap_rank"), "usd": entry.get("usd"),
                "change_24h_pct": _round(entry.get("usd_24h_change")),
                "market_cap_usd": _round(entry.get("usd_market_cap"), 0),
                "volume_24h_usd": _round(entry.get("usd_24h_vol"), 0),
                "other_matches": [c["id"] for c in exact[1:4]]}

    def token_market(self, chain: str, address: str) -> dict | None:
        platform = chains.info(chain).get("platform")
        if not platform or not self.online:
            return None
        data = http_json(f"{API}/simple/token_price/{platform}?contract_addresses={urllib.parse.quote(address)}"
                         "&vs_currencies=usd&include_24hr_change=true&include_market_cap=true")
        if not isinstance(data, dict) or not data:
            return None
        entry = next(iter(data.values()))
        return {"usd": entry.get("usd"), "change_24h_pct": _round(entry.get("usd_24h_change")),
                "market_cap_usd": _round(entry.get("usd_market_cap"), 0)}


def _round(value, digits: int = 2):
    return round(value, digits) if isinstance(value, (int, float)) else None


def usd(amount: float | None, price: float | None) -> float | None:
    if amount is None or price is None:
        return None
    return round(amount * price, 2)
