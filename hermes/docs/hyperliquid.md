# Hyperliquid

Hyperliquid's perp and spot venue through one access plugin in the web3 group:
reading markets and any account for the Assistant, Researcher, Searcher and
Marketer, and for the Assistant alone trading from its Hermes wallets. Read it
when changing the read engine, the trader, the signing or the approval path.
It builds on [web3.md](web3.md) (the wallet's accounts, the shared engine
bridge, A2A rule, approval record and bypass guard) and the rules of
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                            | Home                                                                        |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `hyperliquid` tool (toolset `hyperliquid_access`)                | `plugins/web3/hyperliquid-access/`: a thin entry point                      |
| Tool schema, refusals, `pre_tool_call` approval hook             | `plugins/web3/_shared/hl_access.py`, over `access.py` and `guard.py`        |
| Read engine: the public `/info` endpoint                         | `_shared/hl.py`, run with the web3 venv like `reader.py`                    |
| Trader: quotes, effects, cards, submits; reads the wallet's keys | `_shared/hl_trader.py`, over `signer.Secrets`, `ledger.py` and `hl_sign.py` |
| Action building and signing, byte-compatible with the SDK        | `_shared/hl_sign.py` (`msgpack` in `engines/web3/requirements.lock`)        |
| How a profile reads Hyperliquid; how the Assistant trades        | plugin skills `hyperliquid-access:hyperliquid`, `…:hyperliquid-trade`       |
| How Researcher and Searcher weigh and record venue evidence      | each pipeline's `references/platforms/hyperliquid.md`                       |
| What the Assistant does inline in Chat                           | the Assistant's Chat reference `web3.md`, section "Hyperliquid"             |

`hl_access.py` loads `access.py` under the same module name as the evm and
solana plugins, so the three tools share one engine bridge (minimal
environment, the venv's interpreter, the result size limit), one A2A rule and
one in-memory record of approval decisions. The upstream
`blockchain/hyperliquid` skill is not wired: it runs a script through the
terminal, which Researcher and Searcher do not have; its commands and review
procedure are folded into the tool and the read skill. The official SDK is not
a dependency either: it pins an eth-account older than the engine's lock, so
`hl_sign.py` reproduces its signing and its tests pin the SDK's own vectors.

## Networks

Every read and quote names `network`, `mainnet` or `testnet`; there is no
default (a submit takes its quote's). They are separate venues (markets, asset
ids, accounts and balances differ), so a figure from one is never evidence
about the other, and a signature for one never replays on the other. The API
base and explorer are fixed per network in `hl.py`; the engines never take a
URL from the caller (`_api` is honoured only under the engines' own tests).

## Reads

One `action` per call; the tool schema lists them: `dexs`, `markets`,
`spots`, `candles`, `funding`, `book`, `state`, `balances`, `fills`,
`orders`, `review`, `export`. Rules that hold across them:

- **Asset ids are computed, never stored.** A perp's id is its index in the
  dex's universe; a builder dex's is `100000 + dex index × 10000 + index`; a
  spot pair's is `10000 + its universe index`. `markets` and `spots` return
  them with the size and price decimals an order would need.
- **Spot pairs resolve by ticker, never to a look-alike.** `HYPE/USDC` is
  looked up to the name the venue trades it under (`@107`). Token names are
  chosen by their deployers, so a ticker naming several pairs resolves to the
  canonical one, or is refused with the `@N` candidates.
- **What a read did not cover is named** (`unread`): fills beyond one read,
  funding beyond the pages read, a candle window cut at the venue's 5000, a
  reviewed coin without market context. `fills` and `review` up to now read
  the account's newest fills in one request; a past window (`end_time`) pages
  forward from its start.
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

Researcher and Marketer answer inbound A2A reads; the Assistant refuses them,
and no inbound request ever trades ([web3.md](web3.md) "ABI decoding and
untrusted text" for the shared rule).

## Trading (the Assistant's actions)

The account is a Hermes wallet account ([web3.md](web3.md) "Accounts": only
names with `HERMES` sign); its Hyperliquid account is its EVM address. The
trader is part of the signer: it reads keys through `signer.Secrets`, keeps
them in its process and returns quotes, cards, order ids and statuses only.

`quote` reads the market and the account and builds the exact action —
orders (market as an IOC limit at most `slippage` beyond the mid, default 1%,
at most 5%; limit with a time in force; TP/SL legs on an opening perp order),
`close`, `tpsl` on the position held, `modify` of a resting limit order,
`cancel`, `leverage` and isolated `margin`. Price and size are rounded to the
venue's tick (5 significant figures, integers always allowed, 6 or 8 decimals
less the size decimals) and size step, and what the venue would refuse is
refused here first (below 10 USDC, a TP/SL that would fire at once, a
position that is not there). The quote is stored single-use for 15 minutes
under an HMAC keyed from its signing secret, so neither the action nor its
card can change between approval and submit; every order leg carries a client
order id derived from the quote.

**The effect** decides the approval, and is computed from the stored action,
never from the model's arguments:

- **reduce** — a signed action the venue itself holds to lowering exposure: a
  cancel, a perp order whose every leg is reduce-only (a close, TP/SL), a
  modify of a reduce-only order, added isolated margin.
- **increase** — everything else, every spot order included, and every
  leverage change: `updateLeverage` sets a value unconditionally, and another
  client (the venue's own app) can change the leverage between any read here
  and the venue's processing, so "lower than now" cannot be guaranteed.

Verify and submit recompute the effect from the authenticated action; the
stored verdict alone is never trusted.

`submit` re-checks, under the wallet lock, the MAC, expiry and single use,
that the MAC is the one the approval was given for, the effect as it reads
now, and the hourly caps. It then signs with a fresh nonce (milliseconds, kept
above every earlier one per signer in `hl-nonce.json`) and an `expiresAfter`
a minute ahead, so a signed action the venue has not seen by then is void,
checks that the signature recovers to the account, marks the quote consumed
and writes the ledger row as `unknown` — and only then posts. The venue's
reply sets the outcome: `sent` with one status per leg (`filled`, `resting`,
`error`), or `rejected` when it refused everything. No answer leaves
`unknown`, and so does any reply that is neither `ok` nor the venue's
explicit `err`: the client order ids are looked up once and nothing is
re-sent. An HTTP 4xx comes back before the venue processes anything (a
malformed request, a rate limit) and is a refusal. The card names the venue's
own id of a spot pair beside its tickers, and the compact card keeps every
signed leg, dropping only context.

## Approval

The hook decides each `submit` from the quote as the trader verifies it:

- **reduce** runs without asking, wherever it runs, cron included: closing,
  cancelling and protecting a position must never wait on a card.
- **increase** shows its card through Hermes' gate, under a fresh rule key
  per card (session and always never answer another card), and is blocked
  wherever no person can answer (`_no_human`, as for external transfers).
- The decision and the verified MAC travel in memory to the tool, once; a
  submit the hook did not see never reaches the trader.
- **Caps:** at most 30 increases an hour, and 200 actions of any kind (a
  loop stops there), counted in `hyperliquid.jsonl` like the transfer
  ledger: `sent` and `unknown` count, `rejected` does not. There are no size
  limits: an account should hold only what the user is ready to lose.

Quotes live in `<state>/hl-quotes/`, beside the transfer quotes in the
wallet's state directory, which the guard already keeps out of the terminal.
On the Assistant the guard also blocks the trader and signing modules, their
state files, the engine modules imported or run by name from another script,
any terminal or file-tool use of the shared code directory (reading its source
with `read_file` excepted), the venue's signed `/exchange` endpoint and the
official SDK; reading the public `/info` endpoint stays open. As with transfers, that is a
pattern match, not a sandbox: the boundaries are that keys never leave the
signer's process and that every increase shows its card.

## Setup

1. `scripts/web3.sh install` (the same venv as the chain tools).
2. Enable `hyperliquid-access` with the `hyperliquid_access` toolset in a
   profile's config (the tracked Researcher, Searcher and Marketer examples
   have it; the Assistant's lives in its private config), then restart the
   gateway.
3. To trade, a Hermes wallet ([web3.md](web3.md) "Setup") with USDC on the
   venue, on the network the user means.
