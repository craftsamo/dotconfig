"""The fixed chain table of the web3 plugins (docs/web3.md "Chains and RPC").

Pure Python with no third-party import: the plugins load it in Hermes' own interpreter to check a
chain name before starting the engine, and the engine imports it in the web3 venv. A chain is only
ever named by its key here, never by a URL from a caller.
"""

from __future__ import annotations

# rpc: the public endpoint used without a provider key. alchemy / helius: the provider's network
# slug. platform: CoinGecko's asset platform id (token prices); coin: CoinGecko's id of the native
# coin. Testnets have no price.
EVM = {
    "ethereum": {"id": 1, "name": "Ethereum", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://etherscan.io", "rpc": "https://ethereum-rpc.publicnode.com",
                 "alchemy": "eth-mainnet", "platform": "ethereum", "coin": "ethereum", "testnet": False},
    "base": {"id": 8453, "name": "Base", "symbol": "ETH", "decimals": 18,
             "explorer": "https://basescan.org", "rpc": "https://mainnet.base.org",
             "alchemy": "base-mainnet", "platform": "base", "coin": "ethereum", "testnet": False},
    "arbitrum": {"id": 42161, "name": "Arbitrum One", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://arbiscan.io", "rpc": "https://arb1.arbitrum.io/rpc",
                 "alchemy": "arb-mainnet", "platform": "arbitrum-one", "coin": "ethereum", "testnet": False},
    "optimism": {"id": 10, "name": "OP Mainnet", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://optimistic.etherscan.io", "rpc": "https://mainnet.optimism.io",
                 "alchemy": "opt-mainnet", "platform": "optimistic-ethereum", "coin": "ethereum",
                 "testnet": False},
    "polygon": {"id": 137, "name": "Polygon PoS", "symbol": "POL", "decimals": 18,
                "explorer": "https://polygonscan.com", "rpc": "https://polygon-rpc.com",
                "alchemy": "polygon-mainnet", "platform": "polygon-pos", "coin": "polygon-ecosystem-token",
                "testnet": False},
    "bnb": {"id": 56, "name": "BNB Chain", "symbol": "BNB", "decimals": 18,
            "explorer": "https://bscscan.com", "rpc": "https://bsc-dataseed.bnbchain.org",
            "alchemy": "bnb-mainnet", "platform": "binance-smart-chain", "coin": "binancecoin", "testnet": False},
    "avalanche": {"id": 43114, "name": "Avalanche C-Chain", "symbol": "AVAX", "decimals": 18,
                  "explorer": "https://snowtrace.io", "rpc": "https://api.avax.network/ext/bc/C/rpc",
                  "alchemy": "avax-mainnet", "platform": "avalanche", "coin": "avalanche-2", "testnet": False},
    "sepolia": {"id": 11155111, "name": "Sepolia", "symbol": "ETH", "decimals": 18,
                "explorer": "https://sepolia.etherscan.io", "rpc": "https://ethereum-sepolia-rpc.publicnode.com",
                "alchemy": "eth-sepolia", "platform": None, "coin": None, "testnet": True},
    "base-sepolia": {"id": 84532, "name": "Base Sepolia", "symbol": "ETH", "decimals": 18,
                     "explorer": "https://sepolia.basescan.org", "rpc": "https://sepolia.base.org",
                     "alchemy": "base-sepolia", "platform": None, "coin": None, "testnet": True},
    "arbitrum-sepolia": {"id": 421614, "name": "Arbitrum Sepolia", "symbol": "ETH", "decimals": 18,
                         "explorer": "https://sepolia.arbiscan.io", "rpc": "https://sepolia-rollup.arbitrum.io/rpc",
                         "alchemy": "arb-sepolia", "platform": None, "coin": None, "testnet": True},
    "optimism-sepolia": {"id": 11155420, "name": "OP Sepolia", "symbol": "ETH", "decimals": 18,
                         "explorer": "https://sepolia-optimism.etherscan.io", "rpc": "https://sepolia.optimism.io",
                         "alchemy": "opt-sepolia", "platform": None, "coin": None, "testnet": True},
    "polygon-amoy": {"id": 80002, "name": "Polygon Amoy", "symbol": "POL", "decimals": 18,
                     "explorer": "https://amoy.polygonscan.com", "rpc": "https://rpc-amoy.polygon.technology",
                     "alchemy": "polygon-amoy", "platform": None, "coin": None, "testnet": True},
}

SOLANA = {
    "solana": {"name": "Solana", "symbol": "SOL", "decimals": 9, "explorer": "https://solscan.io",
               "rpc": "https://api.mainnet-beta.solana.com", "helius": "mainnet", "platform": "solana",
               "coin": "solana", "testnet": False},
    "solana-devnet": {"name": "Solana Devnet", "symbol": "SOL", "decimals": 9,
                      "explorer": "https://solscan.io", "explorer_suffix": "?cluster=devnet",
                      "rpc": "https://api.devnet.solana.com", "helius": "devnet", "platform": None,
                      "coin": None, "testnet": True},
}

CHAINS = (*EVM, *SOLANA)

# Well-known tokens per chain, read when no provider key lists an address's tokens. Symbols and
# decimals are always read from the chain, never taken from here.
KNOWN_TOKENS = {
    "ethereum": ["0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                 "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                 "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"],
    "base": ["0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "0x4200000000000000000000000000000000000006"],
    "arbitrum": ["0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
                 "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "0x912CE59144191C1204E64559FE8253a0e49E6548"],
    "optimism": ["0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", "0x4200000000000000000000000000000000000006",
                 "0x4200000000000000000000000000000000000042"],
    "polygon": ["0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"],
    "bnb": ["0x55d398326f99059fF775485246999027B3197955", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"],
    "avalanche": ["0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"],
    "sepolia": ["0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"],
    "base-sepolia": ["0x036CbD53842c5426634e7929541eC2318f3dCF7e"],
}

KNOWN_MINTS = {
    "solana": {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
               "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
               "So11111111111111111111111111111111111111112": "wSOL",
               "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
               "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
               "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "mSOL",
               "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn": "JitoSOL"},
    "solana-devnet": {"4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU": "USDC"},
}


def family(chain: str) -> str | None:
    """'evm', 'solana' or None for a name that is not in the table."""
    if chain in EVM:
        return "evm"
    if chain in SOLANA:
        return "solana"
    return None


def info(chain: str) -> dict:
    if chain in EVM:
        return EVM[chain]
    if chain in SOLANA:
        return SOLANA[chain]
    raise KeyError(chain)


def explorer(chain: str, kind: str, value: str) -> str:
    """An explorer link: kind is 'tx', 'address', 'block' (EVM) or 'slot' / 'token' (Solana)."""
    entry = info(chain)
    if chain in SOLANA and kind == "slot":
        kind = "block"
    return f"{entry['explorer']}/{kind}/{value}{entry.get('explorer_suffix', '')}"
