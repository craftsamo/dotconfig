"""The fixed chain table of the web3 plugins (docs/web3.md "Chains and RPC").

Pure Python with no third-party import: the plugins load it in Hermes' own interpreter to check a
chain name before starting the engine, and the engine imports it in the web3 venv. A chain is only
ever named by its key here, never by a URL from a caller.
"""

from __future__ import annotations

# rpc: the public endpoint used without a provider key. alchemy / helius: the provider's network
# slug. platform: CoinGecko's asset platform id (token prices); coin: CoinGecko's id of the native
# coin. Testnets have no price. fee: how a transfer's fee goes beyond gas x max fee per gas, which the
# signer adds to the stated maximum: "op" (an OP Stack L1 data fee and operator fee from the
# GasPriceOracle), "op-token" (the same, the L1 fee converted by the oracle's tokenRatio into a
# native token other than ETH: Mantle), "scroll" (Scroll's L1GasPriceOracle); none: gas covers it all.
EVM = {
    "ethereum": {"id": 1, "name": "Ethereum", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://etherscan.io", "rpc": "https://ethereum-rpc.publicnode.com",
                 "alchemy": "eth-mainnet", "platform": "ethereum", "coin": "ethereum", "testnet": False},
    "base": {"id": 8453, "name": "Base", "symbol": "ETH", "decimals": 18,
             "explorer": "https://basescan.org", "rpc": "https://mainnet.base.org",
             "alchemy": "base-mainnet", "platform": "base", "coin": "ethereum", "fee": "op", "testnet": False},
    "arbitrum": {"id": 42161, "name": "Arbitrum One", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://arbiscan.io", "rpc": "https://arb1.arbitrum.io/rpc",
                 "alchemy": "arb-mainnet", "platform": "arbitrum-one", "coin": "ethereum", "testnet": False},
    "optimism": {"id": 10, "name": "OP Mainnet", "symbol": "ETH", "decimals": 18,
                 "explorer": "https://optimistic.etherscan.io", "rpc": "https://mainnet.optimism.io",
                 "alchemy": "opt-mainnet", "platform": "optimistic-ethereum", "coin": "ethereum", "fee": "op",
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
    "linea": {"id": 59144, "name": "Linea", "symbol": "ETH", "decimals": 18,
        "explorer": "https://lineascan.build", "rpc": "https://rpc.linea.build",
        "alchemy": "linea-mainnet", "platform": "linea", "coin": "ethereum", "testnet": False},
    "scroll": {"id": 534352, "name": "Scroll", "symbol": "ETH", "decimals": 18,
        "explorer": "https://scrollscan.com", "rpc": "https://rpc.scroll.io",
        "alchemy": "scroll-mainnet", "platform": "scroll", "coin": "ethereum", "fee": "scroll", "testnet": False},
    "zksync": {"id": 324, "name": "ZKsync Era", "symbol": "ETH", "decimals": 18,
        "explorer": "https://explorer.zksync.io", "rpc": "https://mainnet.era.zksync.io",
        "alchemy": "zksync-mainnet", "platform": "zksync", "coin": "ethereum", "testnet": False},
    "unichain": {"id": 130, "name": "Unichain", "symbol": "ETH", "decimals": 18,
        "explorer": "https://uniscan.xyz", "rpc": "https://mainnet.unichain.org",
        "alchemy": "unichain-mainnet", "platform": "unichain", "coin": "ethereum", "fee": "op", "testnet": False},
    "gnosis": {"id": 100, "name": "Gnosis", "symbol": "xDAI", "decimals": 18,
        "explorer": "https://gnosisscan.io", "rpc": "https://rpc.gnosischain.com",
        "alchemy": "gnosis-mainnet", "platform": "xdai", "coin": "xdai", "testnet": False},
    "celo": {"id": 42220, "name": "Celo", "symbol": "CELO", "decimals": 18,
        "explorer": "https://celoscan.io", "rpc": "https://forno.celo.org",
        "alchemy": "celo-mainnet", "platform": "celo", "coin": "celo", "fee": "op", "testnet": False},
    "mantle": {"id": 5000, "name": "Mantle", "symbol": "MNT", "decimals": 18,
        "explorer": "https://mantlescan.xyz", "rpc": "https://rpc.mantle.xyz",
        "alchemy": "mantle-mainnet", "platform": "mantle", "coin": "mantle", "fee": "op-token", "testnet": False},
    "sonic": {"id": 146, "name": "Sonic", "symbol": "S", "decimals": 18,
        "explorer": "https://sonicscan.org", "rpc": "https://rpc.soniclabs.com",
        "alchemy": "sonic-mainnet", "platform": "sonic", "coin": "sonic-3", "testnet": False},
    "world-chain": {"id": 480, "name": "World Chain", "symbol": "ETH", "decimals": 18,
        "explorer": "https://worldscan.org", "rpc": "https://worldchain-mainnet.g.alchemy.com/public",
        "alchemy": "worldchain-mainnet", "platform": "world-chain", "coin": "ethereum", "fee": "op", "testnet": False},
    "ink": {"id": 57073, "name": "Ink", "symbol": "ETH", "decimals": 18,
        "explorer": "https://explorer.inkonchain.com", "rpc": "https://rpc-gel.inkonchain.com",
        "alchemy": "ink-mainnet", "platform": "ink", "coin": "ethereum", "fee": "op", "testnet": False},
    "zora": {"id": 7777777, "name": "Zora", "symbol": "ETH", "decimals": 18,
        "explorer": "https://explorer.zora.energy", "rpc": "https://rpc.zora.energy",
        "alchemy": "zora-mainnet", "platform": "zora-network", "coin": "ethereum", "fee": "op", "testnet": False},
    "sepolia": {"id": 11155111, "name": "Sepolia", "symbol": "ETH", "decimals": 18,
                "explorer": "https://sepolia.etherscan.io", "rpc": "https://ethereum-sepolia-rpc.publicnode.com",
                "alchemy": "eth-sepolia", "platform": None, "coin": None, "testnet": True},
    "base-sepolia": {"id": 84532, "name": "Base Sepolia", "symbol": "ETH", "decimals": 18,
                     "explorer": "https://sepolia.basescan.org", "rpc": "https://sepolia.base.org",
                     "alchemy": "base-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "arbitrum-sepolia": {"id": 421614, "name": "Arbitrum Sepolia", "symbol": "ETH", "decimals": 18,
                         "explorer": "https://sepolia.arbiscan.io", "rpc": "https://sepolia-rollup.arbitrum.io/rpc",
                         "alchemy": "arb-sepolia", "platform": None, "coin": None, "testnet": True},
    "optimism-sepolia": {"id": 11155420, "name": "OP Sepolia", "symbol": "ETH", "decimals": 18,
                         "explorer": "https://sepolia-optimism.etherscan.io", "rpc": "https://sepolia.optimism.io",
                         "alchemy": "opt-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "polygon-amoy": {"id": 80002, "name": "Polygon Amoy", "symbol": "POL", "decimals": 18,
                     "explorer": "https://amoy.polygonscan.com", "rpc": "https://rpc-amoy.polygon.technology",
                     "alchemy": "polygon-amoy", "platform": None, "coin": None, "testnet": True},
    "linea-sepolia": {"id": 59141, "name": "Linea Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://sepolia.lineascan.build", "rpc": "https://rpc.sepolia.linea.build",
        "alchemy": "linea-sepolia", "platform": None, "coin": None, "testnet": True},
    "zksync-sepolia": {"id": 300, "name": "ZKsync Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://sepolia.explorer.zksync.io", "rpc": "https://sepolia.era.zksync.dev",
        "alchemy": "zksync-sepolia", "platform": None, "coin": None, "testnet": True},
    "unichain-sepolia": {"id": 1301, "name": "Unichain Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://sepolia.uniscan.xyz", "rpc": "https://sepolia.unichain.org",
        "alchemy": "unichain-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "gnosis-chiado": {"id": 10200, "name": "Gnosis Chiado", "symbol": "xDAI", "decimals": 18,
        "explorer": "https://gnosis-chiado.blockscout.com", "rpc": "https://rpc.chiadochain.net",
        "alchemy": "gnosis-chiado", "platform": None, "coin": None, "testnet": True},
    "celo-sepolia": {"id": 11142220, "name": "Celo Sepolia", "symbol": "CELO", "decimals": 18,
        "explorer": "https://celo-sepolia.blockscout.com", "rpc": "https://forno.celo-sepolia.celo-testnet.org",
        "alchemy": "celo-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "mantle-sepolia": {"id": 5003, "name": "Mantle Sepolia", "symbol": "MNT", "decimals": 18,
        "explorer": "https://explorer.sepolia.mantle.xyz", "rpc": "https://rpc.sepolia.mantle.xyz",
        "alchemy": "mantle-sepolia", "platform": None, "coin": None, "fee": "op-token", "testnet": True},
    "sonic-testnet": {"id": 14601, "name": "Sonic Testnet", "symbol": "S", "decimals": 18,
        "explorer": "https://testnet.sonicscan.org", "rpc": "https://rpc.testnet.soniclabs.com",
        "alchemy": "sonic-testnet", "platform": None, "coin": None, "testnet": True},
    "world-chain-sepolia": {"id": 4801, "name": "World Chain Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://sepolia.worldscan.org", "rpc": "https://worldchain-sepolia.g.alchemy.com/public",
        "alchemy": "worldchain-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "ink-sepolia": {"id": 763373, "name": "Ink Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://explorer-sepolia.inkonchain.com", "rpc": "https://rpc-gel-sepolia.inkonchain.com",
        "alchemy": "ink-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
    "zora-sepolia": {"id": 999999999, "name": "Zora Sepolia", "symbol": "ETH", "decimals": 18,
        "explorer": "https://sepolia.explorer.zora.energy", "rpc": "https://sepolia.rpc.zora.energy",
        "alchemy": "zora-sepolia", "platform": None, "coin": None, "fee": "op", "testnet": True},
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
    "linea": ["0x176211869cA2b568f2A7D4EE941E073a821EE1ff", "0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f"],
    "scroll": ["0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4", "0x5300000000000000000000000000000000000004"],
    "zksync": ["0x1d17CBcF0D6D143135aE902365D2E5e2A16538D4", "0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91"],
    "unichain": ["0x078D782b760474a361dDA0AF3839290b0EF57AD6", "0x4200000000000000000000000000000000000006"],
    "gnosis": ["0x2a22f9c3b484c3629090FeED35F17Ff8F88f76F0", "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"],
    # not CELO's own ERC-20 face (0x471E…a438): it is the native balance, which would count twice
    "celo": ["0xcebA9300f2b948710d2653dD7B07f33A8B32118C", "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e"],
    "mantle": ["0x09Bc4E0D864854c6aFB6eB9A9cdF58aC190D0dF9", "0xdEAddEaDdeadDEadDEADDEAddEADDEAddead1111"],
    "sonic": ["0x29219dd400f2Bf60E5a23d13Be72B486D4038894", "0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38"],
    "world-chain": ["0x79A02482A880bCE3F13e09Da970dC34db4CD24d1", "0x4200000000000000000000000000000000000006"],
    "ink": ["0x2D270e6886d130D724215A266106e6832161EAEd", "0x4200000000000000000000000000000000000006"],
    "zora": ["0xCccCCccc7021b32EBb4e8C08314bD62F7c653EC4", "0x4200000000000000000000000000000000000006"],
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
