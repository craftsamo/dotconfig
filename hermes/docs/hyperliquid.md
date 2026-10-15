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
| Mandates: terms, cards, storage, fitting                         | `_shared/hl_mandate.py`, used by the trader                                 |
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
- **`state` and `balances` report the account's mode** (`userAbstraction`).
  A unified account (`unifiedAccount`, or `portfolioMargin`) keeps one
  balance per asset for spot and every perp dex, held in the spot state, so
  its perp `account_value` and `withdrawable` read 0 with funds in it; both
  reads say so for such an account.
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
`waiting for trigger` for an accepted TP/SL leg, `error`; the venue's other
bare answer, `waitingForFill`, reads `waiting for fill`), or `rejected` when it refused everything. No answer leaves
`unknown`, and so does any reply that is neither `ok` nor the venue's
explicit `err`: the client order ids are looked up once and nothing is
re-sent. An HTTP 4xx comes back before the venue processes anything (a
malformed request, a rate limit) and is a refusal. The card names the venue's
own id of a spot pair beside its tickers, and the compact card keeps every
signed leg, dropping only context. A quote that will ask on a card is refused
when its compact card would not fit Discord's limit, rather than shown cut.

## Moving funds

`quote` also builds the user-signed moves: `withdraw` (`withdraw3`: USDC from
the perp balance to an Arbitrum address, default the account's own; the venue
takes a 1 USDC fee), `send` (`usdSend` from the perp balance, or `spotSend`
of a named spot token from the spot balance, to a Hyperliquid address) and
`transfer` (`usdClassTransfer`, spot ↔ perp within the account). Each checks
the balance it draws on, the amount's precision, a destination that is not
the zero address, the sender itself or the deposit bridge, and a spot token
named unambiguously (`NAME:tokenId` when deployers reuse a name).

A unified account (its mode, as the reads report it) has one balance for spot
and perp, and the venue refuses `spotSend` and `usdClassTransfer` from it. Its
`send` is `sendAsset` from that balance (`sourceDex: "spot"`) to the
destination's spot balance for a named token, or its default perp balance for
USDC — where `spotSend` and `usdSend` would have credited it — and its card
says so; its `withdraw` draws on the same balance, at quote time never above
what the venue calls available after maintenance margin when it says; its
`transfer` is refused, since
there is nothing to move. `sendAsset`'s signatures match the SDK's own signing
function; that the venue still accepts `withdraw3` from a unified account is
unverified (a refusal moves nothing). USDC that a move does not name is the
venue's own, spot token 0, found by its index: deployers can reuse the name.

A move's effect is `own` when the funds stay in the user's Hermes wallets —
a transfer, or a destination the secrets derive as own, exactly as for wallet
transfers ([web3.md](web3.md) "Approval") — and `external` otherwise. The
hook runs `own` without asking, anywhere; `external` shows its card and is
blocked where no person can answer; no mandate covers either. Submit
re-derives `own` from the secrets, signs with the nonce as the action's time
(user-signed actions take no `expiresAfter`), checks the signature recovers to
the account, and writes a row both to `hyperliquid.jsonl` and to the
wallet's transfer ledger before posting, so moves count in its ten transfers
an hour.

## Deposits

USDC enters the venue through its legacy bridge on Arbitrum
(`chains.HYPERLIQUID_BRIDGES`, from the venue's docs): native USDC sent to it
is credited to the sender's Hyperliquid account. A deposit is the `evm`
tool's ordinary quote and transfer; the signer refuses anything to a bridge
address that would be lost — another chain's bridge, any token but that
chain's USDC, less than 5 USDC, any NFT — and the card labels the bridge.
`deposit_info` returns the bridge, the token and the minimum without a
request. The venue calls this bridge deprecated in favour of Circle's CCTP,
which needs a contract call the signer does not make; a CCTP path would be a
new signed call, not a change to this one.

## Mandates

A mandate is the one way an increase runs without its card
([decision](decisions/hyperliquid-mandates.md)). It is a quote of kind
`mandate` — one Hermes account, one network, a list of perp markets,
`max_order_usd`, `max_exposure_usd` (positions plus every order that is not
reduce-only, triggers included, in those markets), `max_leverage`,
`per_hour` (at most 30) and `days` (at most 30, ending when its card said),
with a purpose — submitted on its own card only: never on a mandate, never as
a reduce, never where no person can answer. Both its cards carry every bound
(the compact one leaves out only the purpose); terms that do not fit are
refused at quote time.

It is stored in `<state>/hl-mandates/` under an HMAC keyed from the account's
secret. Which mandate is in force for an account and network is one MAC'd
head file per pair: making a mandate points it there, revoking points it at
none, and only the head decides; `hl-mandates.jsonl` is history for
`mandates`. A newer mandate replaces the old one, its card names the one it
replaces, and it is refused if a different one is in force by the time it is
submitted.

- **Fitting.** At verify the trader reads the account and says whether the
  quote fits: an `order`, `modify` or `leverage` on a covered perp, worth at
  most `max_order_usd`, with the market's leverage within `max_leverage`, the
  markets' total after it within `max_exposure_usd` and the mandate's hourly
  orders not used up. An order is worth its size at the highest of its own
  price and the market's price now (a sell can fill above its limit); a
  modify frees only what the old order still counts for in the fresh read,
  and is refused when that order is gone; a leverage change needs the
  markets' total within bounds already. A read that fails, or a reply of a
  shape it does not know, is a no.
- **The hook** runs a fitting increase without a card, unattended too, and
  records the decision as `mandate`. Outside the mandate the increase asks
  on its card, and the block message names why it does not fit.
- **Submit** reads the account again under the wallet lock and refuses
  (nothing sent) when the mandate is gone, revoked, expired or no longer
  fits. The ledger row names the mandate, which is how its hourly use is
  counted.
- **Revoking** (`revoke_mandate`) needs no card and holds at once; `mandates`
  lists every mandate with its standing and its use this hour.
- Never covered: spot, margin taken out, any withdrawal or send, a new
  mandate.
- **What the files cannot stop.** The MACs stop an edited mandate or head,
  but not a whole earlier head file copied back over the current one, which
  would put an earlier, unexpired mandate back in force. As with the
  transfer ledger, the boundary there is the guard and the state
  directory's permissions; the 30-day ceiling bounds it.

## Approval

The hook decides each `submit` from the quote as the trader verifies it:

- **reduce** runs without asking, wherever it runs, cron included: closing,
  cancelling and protecting a position must never wait on a card.
- **increase inside a mandate** runs without asking (above).
- **a move** runs without asking when `own` and asks on its card when
  `external` ("Moving funds").
- **any other increase** shows its card through Hermes' gate, under a fresh
  rule key per card (session and always never answer another card), and is
  blocked wherever no person can answer (`_no_human`, as for external
  transfers).
- The decision and the verified MAC travel in memory to the tool, once; a
  submit the hook did not see never reaches the trader.
- **Caps:** at most 30 increases an hour, and 200 actions of any kind (a
  loop stops there), counted in `hyperliquid.jsonl` like the transfer
  ledger: `sent` and `unknown` count, `rejected` does not. There are no size
  limits: an account should hold only what the user is ready to lose.

Quotes live in `<state>/hl-quotes/` and mandates in `<state>/hl-mandates/`,
beside the transfer quotes in the
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
   profile's config (the tracked Assistant, Researcher, Searcher and
   Marketer examples have it, and the private configs pair with them; the
   Assistant's a2a toolsets leave it out, since it refuses inbound A2A),
   then restart the gateway.
3. To trade, a Hermes wallet ([web3.md](web3.md) "Setup") with USDC on the
   venue, on the network the user means ("Deposits").
