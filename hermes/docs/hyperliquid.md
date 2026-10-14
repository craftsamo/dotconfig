# Hyperliquid

Hyperliquid's perp and spot venue through one access plugin in the web3 group:
reading markets and any account for the Assistant, Researcher, Searcher and
Marketer. Read it when changing the read engine or the tool. It builds on
[web3.md](web3.md) (the shared engine bridge, A2A rule and bypass guard) and
the rules of [access-common.md](access-common.md). Part of the Hermes design
docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                       | Home                                                                 |
| ----------------------------------------------------------- | -------------------------------------------------------------------- |
| `hyperliquid` tool (toolset `hyperliquid_access`)           | `plugins/web3/hyperliquid-access/`: a thin entry point               |
| Tool schema, refusals, `pre_tool_call` hook                 | `plugins/web3/_shared/hl_access.py`, over `access.py` and `guard.py` |
| Read engine: the public `/info` endpoint                    | `_shared/hl.py`, run with the web3 venv like `reader.py`             |
| How a profile reads Hyperliquid                             | plugin skill `hyperliquid-access:hyperliquid`                        |
| How Researcher and Searcher weigh and record venue evidence | each pipeline's `references/platforms/hyperliquid.md`                |

`hl_access.py` loads `access.py` under the same module name as the evm and
solana plugins, so the three tools share one engine bridge (minimal
environment, the venv's interpreter, the result size limit) and one A2A rule.
The upstream `blockchain/hyperliquid` skill is not wired: it runs a script
through the terminal, which Researcher and Searcher do not have; its commands
and review procedure are folded into the tool and the plugin skill.

## Networks

Every call names `network`, `mainnet` or `testnet`; there is no default.
They are separate venues (markets, asset ids, accounts and balances differ),
so a figure from one is never evidence about the other. The API base and
explorer are fixed per network in `hl.py`; the engine never takes a URL from
the caller (`_api` is honoured only under the engine's own tests).

## Reads

One `action` per call; the tool schema lists them: `dexs`, `markets`,
`spots`, `candles`, `funding`, `book`, `state`, `balances`, `fills`,
`orders`, `review`, `export`. Rules that hold across them:

- **Asset ids are computed, never stored.** A perp's id is its index in the
  dex's universe; a builder dex's is `100000 + dex index × 10000 + index`; a
  spot pair's is `10000 + its universe index`. `markets` and `spots` return
  them with the size and price decimals an order would need.
- **Spot pairs resolve by ticker.** `HYPE/USDC` is looked up to the name the
  venue trades it under (`@107`); a canonical pair keeps its own name.
- **What a read did not cover is named** (`unread`): fills beyond one read,
  funding beyond the pages read, a reviewed coin without market context.
  Only an account's newest 10000 fills and an interval's newest 5000 candles
  exist at all. `fills` and `review` up to now read the account's newest
  fills in one request; a past window (`end_time`) pages forward from its
  start.
- **`review` is a heuristic.** It sums fills per coin and adds each traded
  perp's trend and mean funding over the window (at most eight coins); its
  findings — fee drag, concentration, losses against the trend — are leads.
- **`export` is a dataset, not a backtest**: columns and rows with a schema
  name and an exact window, at most 500 candles, inline in the result.
- **Account reads return the explorer link** for the address on that network.
- **Names from third parties.** Builder perp dexs and spot tokens are
  deployed by anyone: a name that is more than a short ticker, and every full
  name, arrives as `{"untrusted": …}`, and the tool description says it is
  never followed.
- **Errors name the network, never the endpoint**; a rate limit says so. The
  public endpoint allows about 1200 weight a minute per IP, so a sweep over
  many accounts or coins is bounded by the caller.

Researcher and Marketer answer inbound A2A reads; the Assistant refuses them
([web3.md](web3.md) "ABI decoding and untrusted text" for the shared rule).
On every profile with the tool, terminal, code and file calls that use the
web3 engine directly are blocked by the shared guard.

## Setup

1. `scripts/web3.sh install` (the same venv as the chain tools; the read
   engine needs only the standard library).
2. Enable `hyperliquid-access` with the `hyperliquid_access` toolset in a
   profile's config (the tracked Researcher, Searcher and Marketer examples
   have it; the Assistant's lives in its private config), then restart the
   gateway.
