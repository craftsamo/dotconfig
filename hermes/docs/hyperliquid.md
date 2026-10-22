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

| Piece                                                            | Home                                                                          |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `hyperliquid` tool (toolset `hyperliquid_access`)                | `plugins/web3/hyperliquid-access/`: a thin entry point                        |
| Tool schema, refusals, `pre_tool_call` approval hook             | `plugins/web3/_shared/hl_access.py`, over `access.py` and `guard.py`          |
| Read engine: the public `/info` endpoint                         | `_shared/hl.py`, run with the web3 venv like `reader.py`                      |
| Trader: quotes, effects, cards, submits; reads the wallet's keys | `_shared/hl_trader.py`, over `signer.Secrets`, `ledger.py` and `hl_sign.py`   |
| Action building and signing, byte-compatible with the SDK        | `_shared/hl_sign.py` (`msgpack` in `engines/web3/requirements.lock`)          |
| Mandates: terms, cards, storage, fitting                         | `_shared/hl_mandate.py`, used by the trader                                   |
| Moves of funds: builders, signed types, card lines, notes        | `_shared/hl_moves.py`, one table entry per kind and per signed type           |
| Rules, backtests, specs and stances (pure, no network)           | `_shared/hl_strategy.py`, used by `hl.py` and the gate                        |
| The strategies' cron gate                                        | `_shared/hl_gate.py`, run by `profiles/assistant/scripts/hl-strategy-gate.sh` |
| How a profile reads Hyperliquid; how the Assistant trades        | plugin skills `hyperliquid-access:hyperliquid`, `…:hyperliquid-trade`         |
| How the Assistant runs a strategy                                | plugin skill `hyperliquid-access:hyperliquid-strategy`                        |
| How Researcher and Searcher weigh and record venue evidence      | each pipeline's `references/platforms/hyperliquid.md`                         |
| What the Assistant does inline in Chat                           | the Assistant's Chat reference `web3.md`, section "Hyperliquid"               |

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
`orders`, `review`, `export`, `backtest` ("Backtests"). Rules that hold
across them:

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
- **`state` gives the account's own fee rates** (`fees`: taker and maker,
  in basis points beside the venue's fractions, its tier and staking
  discount in them); a backtest for that account takes its taker rate as
  `costs.taker_bps`. When the venue does not say, `fees` is null and the
  rest of the read stands.
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
order id derived from the quote, except an order's main leg given its own
`cloid` (a strategy gate names its limit entry, to find it again).

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
malformed request, a rate limit) and is a refusal.

Cards are plain text (both surfaces escape markup), shaped like a wallet
transfer's: a title naming the network and the action, then the effect with a
marker (⚠️ for one that can add exposure or sends funds out of the Hermes
wallets, ✅ for one that cannot), then one fact a line, then a block per side
with the Keychain's project, name, address and memo. A move's `--- To ---`
block says whose the destination is (own, watch-only by its Keychain name, or
external) and shows the address in checksum case, though the signed action
carries it in lower case. The card names the venue's own id of a spot pair
beside its tickers, and the compact card keeps the title with the effect and
every signed leg, dropping only context and, when it is long, clipping the
account's name before anything else. The detailed card sheds memos to fit
Telegram's budget and otherwise falls back to the compact one. A quote that
will ask on a card is refused when its compact card would not fit Discord's
limit, rather than shown cut.

## Moving funds

`quote` also builds the user-signed moves: `withdraw` (`sendToEvmWithData`:
USDC from the perp balance through Circle's CCTP to an address on an EVM
chain, default Arbitrum and the account's own address), `send` (`usdSend`
from the perp balance, or `spotSend` of a named spot token from the spot
balance, to a Hyperliquid address) and `transfer` (`usdClassTransfer`, spot ↔
perp within the account). Each checks
the balance it draws on, the amount's precision, a destination that is not
the zero address, the sender itself or the deposit bridge, and a spot token
named unambiguously (`NAME:tokenId` when deployers reuse a name).

A send to an address with no account on that network (`userRole` reads
`missing`) pays the venue 1 USDC to open one, taken differently by action:
`usdSend` takes it from the amount (the destination gets 1 less), while
`spotSend` and `sendAsset` take it in USDC from the sender beside the amount
(seen for USDC; for another token the same USDC fee is assumed). The quote
checks the balance for both, and its cards name the fee, the compact one at
the end of the send line.

A withdrawal is a CCTP burn: the venue hands the USDC to Circle's linked
contract on HyperEVM, which burns it towards the chain's CCTP domain
(`chains.CCTP_DOMAINS`, Circle's own ids, never EVM chain ids), and Circle
mints it on that chain and pays the gas there itself, usually within a minute.
The chain is one of the network's chains Circle carries USDC on (`chain`,
default `arbitrum` or `arbitrum-sepolia`). Circle's fee comes off the amount
and differs by chain, so the quote reads it from that contract
(`calculateCrossChainWithdrawalFee`, with forwarding) through HyperEVM's
public endpoint, refuses an amount it would swallow, and both cards show what
arrives. The venue also takes a small fee of its own for running the burn on
HyperEVM, in USDC from the balance beside the amount; it is unpublished and
outside the signed action, so the cards state it as about 0.01 USDC and the
quote keeps 0.05 USDC of the balance free for it (`VENUE_FEE_ABOUT`,
`VENUE_FEE_RESERVE`). The signed burn carries no fee ceiling,
so submit reads Circle's fee again before signing and refuses the quote if it
changed (or cannot be read); the ledger rows keep the chain, the fee and what
was to arrive, since quotes are pruned. The signatures match the community
TypeScript SDK's for the same action ([decision](decisions/hyperliquid-cctp.md)).

A unified account (its mode, as the reads report it) has one balance for spot
and perp, and the venue refuses `spotSend` and `usdClassTransfer` from it. Its
`send` is `sendAsset` from that balance (`sourceDex: "spot"`) to the
destination's spot balance for a named token, or its default perp balance for
USDC — where `spotSend` and `usdSend` would have credited it — and its card
says so; its `withdraw` burns from the same balance (`sourceDex: "spot"`), at
quote time never above what the venue calls available after maintenance
margin when it says; its `transfer` is refused, since there is nothing to
move. `sendAsset`'s signatures match the SDK's own signing function. USDC that
a move does not name is the venue's own, spot token 0, found by its index:
deployers can reuse the name.

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

USDC enters the venue through Circle's CCTP, from any of the network's chains
Circle carries USDC on: the `evm` tool's quote with kind `deposit` (`cctp.py`
builds its pieces, the signer quotes and sends it like a transfer). It is up to
two transactions, each its own quote: while Circle's TokenMessenger may take
less than the amount, the quote is `approve` of exactly the amount; once it may
take the amount (at once, if an earlier approval allows it), the quote is the
burn, `depositForBurnWithHook` to HyperEVM
(domain 19) with the mint and its relay bound to Circle's `CctpForwarder` and
a 56-byte hook naming the Hyperliquid account (`to`, default the sender's own)
and its balance (`dex`, perp or spot). Every contract address and the token
come from `chains`, never from the caller.

Circle's fee is capped in the burn: its fast-transfer rate on the amount,
rounded up, plus the forwarding fee's high estimate, read from Circle's fee
service at quote time. Into an account HyperCore does not have yet, Circle's
`CoreDepositWallet` may also keep an owner-set opening fee
(`newCoreAccountFee`), read from it at quote time and named on the cards when
it is not zero. What arrives is at least the amount less both, within about a
minute, and Circle pays the gas on HyperEVM. Distinct burn quotes are not
deduplicated: the exact approval normally stops a second one, so a burn is
never sent twice on purpose. The quote refuses
an amount the cap would swallow, a token other than the chain's USDC, and on
testnet an account that does not exist on Hyperliquid mainnet or more than
1000 USDC, which Circle's testnet would not credit. The effect follows the
account like a transfer: into the user's own Hermes account it runs at once,
into anyone else's it asks on its card. The card names the step, the account
and Circle's cap; the token and spender are named rather than shown, being
fixed. The signer refuses anything sent to Hyperliquid's legacy bridge
(`chains.HYPERLIQUID_BRIDGES`), which the venue deprecates. `deposit_info`
returns the chains, their USDC and how, without a request
([decision](decisions/hyperliquid-cctp.md)).

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

## Backtests

`backtest` is a read: it fetches candles and funding and trades a rule set
over them in `hl_strategy.py`, the module the gate decides with, so what was
tested is what runs.

- **Rules** are a `kind` and its numbers: `breakout` (a close beyond the
  last `entry` bars' range enters, beyond the last `exit` bars' opposite
  range exits) or `ema_cross` (two EMAs cross), each with a stop at
  `stop_atr` ATRs from the signal's close, placed with the entry, and a
  `risk_pct` of equity lost at that stop. Two optional numbers: `trail_atr`
  moves the stop to that many ATRs behind each completed close when that is
  tighter, never looser; `regime_ema` takes longs only above that EMA and
  shorts only below it (exits are the rules' own; three lengths of bars
  warm it up, so a long one needs `long_history` to leave bars to trade).
  Left out or 0, each leaves the rule set and its fingerprint
  those of the rules without it. Only completed bars are read.
  `entry_order` says how an entry is sent: `market` (the default, likewise
  left out of the rule set), `limit` or `limit_then_market`, with
  `limit_atr` placing the limit that many ATRs better than the signal's
  close (at the close without it; less than `stop_atr`, and only with a
  limit).
- **Fills**: a signal at a bar's close fills at the next bar's open with
  slippage and the taker fee both ways; a stop fills inside a bar whose range
  reaches it, at the open when the bar gaps through; funding accrues each
  hour held at the venue's rate (a gap pays none for its bar; a stop inside
  a bar pays the bar's whole, since OHLC does not say its hour). Sizes are capped by `limits` (a share of
  equity and a leverage) and the venue's 10 USDC minimum.
- **Limit entries** are placed when the next bar opens, good till
  canceled. One the open already reached takes the book at once, as a
  taker: at the open with `slippage_bps`, never past its own price. Else it
  rests through the bar and fills at its price with `costs.maker_bps`
  (default 1.5, the lowest tier) and no slippage, only when the bar trades
  `limit_through_bps` (default 2) past the price: a bar that only touches
  it leaves the order in the queue, unfilled. Filled, the entry is the
  market one's in everything else: its stop and size come from the
  signal's close, and the bar's stop and funding count whole, as if it
  filled at the open. Unfilled, `limit` enters nothing (a rule still
  signalling at the next close places a new limit there), and
  `limit_then_market` enters at market at the next open, as an entry from
  that close, unless the close no longer holds the side. Figures with a
  limit entry carry `limit_entries`: placed, filled, its fill rate, filled
  at once (`crossed`), at market after, missed. Exits stay market orders.
  The gate places `limit_then_market` entries the same way (Strategies); a
  plain `limit` is tested here only.
- **Data**: the venue's newest 5000 candles, in pages; `long_history` adds
  the coin's USDT pair from Binance's public market data before them, prices
  only, for main-dex tickers that map plainly, from 2017-07 at the earliest
  (nothing was listed before, and a window reaching before the epoch would
  be refused). Funding is read for the newest
  4000 hours (the request weight stays inside the per-IP budget); older hours
  take the mean of what was read — a later figure, not a point-in-time one —
  and the result says how many held hours were assumed. At most 25000 bars.
- **Walk-forward**: a grid of at most 48 rule sets, 2–6 folds, anchored by
  default; each fold chooses by `mar`, `sharpe` or `return_pct` on the data
  before it and trades the choice on the next window; the stitched unseen
  windows are `out_of_sample`. A position open at a fold's end closes there.
  The grid may vary `entry_order` by name; a combination that is no rule
  set (a `limit_atr` with a market entry, an exit longer than the entry) is
  skipped.
- **Monte Carlo**: `result` and `out_of_sample` each carry `monte_carlo`, the
  trades redrawn 1000 times with replacement in random order. Each trade
  keeps its own path while held (its lowest and highest marks and its fall
  from its own high, relative to the equity before it), which is enough to
  rebuild the bar-by-bar drawdown of any order exactly, so a drawdown inside
  a trade counts. It reports drawdown, return and the longest losing streak
  at percentiles beside the observed order, and is null below 20 trades. A
  draw that loses the whole account stops there, as the backtest opens
  nothing after it. The draws are seeded from the request, so a backtest
  read again with the same `end_time` gives the same spread. They are
  independent, which spreads out losses that cluster in one regime: a
  planning floor, not a bound.
- **Stance windows** override the direction and scale the risk over dated
  windows, so a judgment written as a rule over point-in-time data can be
  tested the same way. A model judging past markets is not a test: it knows
  what came after.
- **Markets together** (`coins` instead of `coin`, 2 to 8): each market's
  own backtest as above under `markets`, and under `portfolio` the same
  rules traded on one account, bar by bar along the markets' shared
  timeline (a market with no bar at a time sits it out), the cash shared.
  Each time runs in two steps, so nothing decided at an open sees the bar
  it opens: first every market's open (its signal's close, its entry, in
  the markets' order), then every market's bar. An entry is sized as the
  gate sizes it: from the account's value (the cash and the other markets'
  unrealized results) less what the other markets hold (their positions,
  and a limit of theirs resting through the bar, as the gate counts a
  resting order), at prices known at that open (their open of the same
  time, else their newest close); a limit the bar trades through fills in
  the bar step, so an entry at the same open does not see it. The
  portfolio's walk-forward chooses each market's rules on its own past
  bars, by that market's own result, and trades the choices together on
  the next unseen window; `chosen` and `chosen_fingerprint` are per
  market. Its `out_of_sample` drawdown and `monte_carlo` are what a
  strategy on those markets is set a breaker from, since a single market's
  figures say nothing about the two held at once. The portfolio's Monte
  Carlo draws the trades one after another whether or not they overlapped
  (each trade keeps its own path: the equity before it, moved by that trade
  alone), so it spreads the trades' results, not the account's bar-by-bar
  curve; the observed drawdown is the account's. `bars_held` counts times
  with any position, and `buy_hold_pct` is the markets' mean. One rule set
  and one stance for all the markets: a per-market variant is the
  walk-forward's choice, or separate requests.
- **`fingerprint`** hashes the rules with their interval. A strategy runs a
  variant only under the fingerprint its backtest reported.

## Strategies

A strategy is the Assistant's way to trade unattended
([decision](decisions/hyperliquid-strategies.md)): a spec the user decided, a
mandate on its card, and a cron gate that wakes the Assistant only when the
rules call for an action. Its files live in
`<assistant home>/hl-strategies/<name>/`: `spec.json` and `stance.json`
written by the Assistant, `state.json` by the gate alone. The strategy skill
owns the procedure; this section owns what the code holds to.

- **The spec** (`hermes-hyperliquid-strategy/1`) names one Hermes account,
  a network, up to 8 main-dex perps, an interval, up to 6 variants each with
  the fingerprint of the backtest that validated it, the default stance (one
  for the strategy, which `default.markets` overrides per market: variant,
  direction or size), the advisor's bounds, `limits` (`exposure_pct`,
  `max_leverage`) and the mandate's id, bounds and end. A variant whose rules
  no longer match its fingerprint makes the spec invalid. A variant also
  records its walk-forward `out_of_sample` (at least its maximum drawdown and
  trades, one or more); without it the variant's markets open nothing, while
  their closes and stops go on. A variant whose rules enter with a plain
  limit (`entry_order: limit`) opens nothing either: the gate places only
  `limit_then_market`. `breaker` (`max_drawdown_pct`, 1 to 90, and
  `reset`) sets the breaker below; a spec without one, or with one that does
  not read, opens nothing either, and still closes and protects.
- **The gate** (`hl_gate.py`, a cron `script` with an agent; the scheduler
  runs its wrapper from the copy `install.sh` keeps in the profile's
  `scripts/`, so the wrapper takes the runtime home from its own parent and
  finds the engine in the repository through the home's `plugins` tree) reads each
  active spec's account, open orders and newest completed candles through
  `/info`, and lists, under the account and its address (the run's reads
  take the address: it has no other way to it), intents: the exact `hyperliquid` quote arguments, each
  with its effect and reason. A position the rules or the stance in force
  exclude gets a close on every run; one without a reduce-only stop loss on
  its closing side for all of it (a take profit does not count) gets one,
  once per bar; under a trailing rule, one whose stop sits looser than the
  trail after a newly completed bar gets the tighter stop first and then the
  cancel of the one it replaces (the cancel names the stop intent in `after`,
  and is sent only once that was), so it is never without one; on a newly
  completed bar an entry gets its leverage set first when the
  market's is above the bound, then a market order with its stop, sized from
  the risk per trade and capped by the limits and the mandate (with headroom
  for the worst price the order is valued at). Without a mandate in force no
  entry is listed, only noted; for a variant with no `out_of_sample`
  recorded, or while the breaker is missing or tripped, none is listed
  either, and the gate says so once rather than per bar; a bar whose entry
  needed a read that failed, the breaker's included, is read again on the
  next run. It remembers the positions it saw, so one
  the venue closed on its own (a stop that fired, a liquidation) is noticed
  once and the run reports the trade's result, and the account's value at
  its first read, which every report compares the value now with. Its last
  line is `{"wakeAgent": false}` when nothing is to be done or said, so no
  model runs; a notice is said once. It never signs, reads a key or posts to
  `/exchange`.
- **Limit entries** (`entry_order: limit_then_market`) are listed as a
  good-till-cancel limit at the backtest's price with the stop attached,
  under a client id (`cloid`) derived from the strategy, the market and the
  signal's bar, valued so its size is the market entry's. A post-only order
  would be rejected whenever the market is already past the price, so one
  the market has reached fills at once as a taker, as the backtest takes it.
  `state.json` follows each until the venue shows it over, reading it by
  that id on every run (`orderStatus`), and the gate cancels only orders
  whose id it derives itself. While a limit may still fill, or its state or
  a lookup of it cannot be read, its market opens nothing new and its bar
  is read again, so an entry never doubles one that might still fill; a fill
  the account read did not show yet holds the market's next entry for a run
  too. The venue places a stop sent with a limit only once all of it fills,
  and cancels it with a partly filled one, so a position on the limit's
  side with no stop on the venue gets a stop for the whole position at the
  entry's stop on every run until one shows, even while the limit's state
  cannot be read and after it is over. A limit still resting is
  canceled, on every run until the venue shows it over, once its bar has
  closed or it is withdrawn: entries held (no mandate, the breaker, a
  variant without its `out_of_sample`), or the stance in force no longer
  allowing its side. Over with nothing filled after its bar closed, the next
  run lists the market entry the backtest takes from that close, from the
  newest close (its stop and size, the canceled limit no longer counted as
  exposure), unless that close no longer holds the side: a quarter of an
  hour after the bar's close rather than at its open, since only then can a
  fill between the gate's read and the cancel be seen. A part filled is the
  entry, and the rest is not bought. A fill is said once, and one whose
  position is already gone (its stop fired) asks the run to report the
  trade. An entry listed beside a close of the market's other side names
  that close in `after`. When `state.json` is missing or unreadable, or its
  record of the limits has a shape the gate never writes, the gate looks up
  the ids it would have given the newest two bars' limits, on every run
  until each lookup could be read, and cancels any still resting, with the
  rules' stop for what of it filled; a market the spec no longer names gets
  its limits, known or still to be looked up, canceled too, and having no
  rules there, the gate tells the user once when what filled has no stop.
  An answer of a
  shape the venue does not give, or a fault while following a limit, is an
  unread limit: its market opens nothing, and the gate goes on. A breaker
  whose fills cannot be read holds the
  market entry after a limit, not the resting limit. A strategy turned
  inactive is not read at all: pausing one cancels its resting limit by
  hand (the strategy skill).
- **The breaker** ([decision](decisions/hyperliquid-breaker.md)) measures
  the strategy's own result, never the account's value: each run the gate
  reads its markets' fills (realized result less USDC fees) and funding from
  where the last run stopped up to the venue's time of its account read, adds
  the change in their positions' unrealized result at that read, and moves an
  index by that sum as a share of the account's value at the last run.
  Deposits, withdrawals and other markets leave it where it is, and later
  results count against the account's new size. The first run only sets the
  baseline. Its drawdown is the index's fall below its high; at
  `max_drawdown_pct` it trips, and from then on no entry or leverage change
  is listed while closes, stops and trailed stops go on. It stays tripped
  until `reset` holds a time later than the trip and not in the future,
  which starts the index and its high again. A memory the gate cannot read
  (an unreadable `state.json`, or a breaker of a shape it never writes)
  starts tripped with the drawdown unknown, never fresh. A fills or funding
  read that fails, or that more rows than five pages hold, moves nothing and
  holds that run's entries. Every other report carries `breaker` (the
  drawdown, the limit, since when it counts, the trip).
- **Execution costs**: from the same fills the breaker reads, the gate
  prices each order of the strategy's markets against what it expected:
  an entry or a signal's close against the bar's close it was listed at
  (where the backtest fills it, at the next open; a reversal keeps both, and
  one order that closes and reverses is the entry), a stop against its
  trigger. A stop seen on the venue matches only its own order's fills; a
  stop listed but not yet seen matches an order whose fill sits at or past
  it on its side, the tightest such one. Slippage is in basis points of
  that reference, as the backtest's `slippage_bps` is, positive when it
  cost; maker share is counted fill by fill. An order matching nothing
  listed (a trade by hand, a take profit, a liquidation) counts its fees
  and maker share only. Each expectation is used once, the oldest first;
  across runs whose fills could not be read they and the stops are kept,
  so each order is priced against the bar it was listed on. An order
  priced once keeps its kind and reference for a day, so fills arriving
  after a read join it and it counts once. Running totals per kind live in `state.json`; a report carries them
  as `execution` (since when; per kind orders, slippage, fees, maker share)
  and the orders priced this run as `fills_measured`. Neither wakes the
  Assistant on its own. A memory of a shape the gate never writes, or a
  fault while measuring, starts the measure again rather than stopping the
  gate: it never changes which intents are listed. It is a measure, not a
  ledger: attempts are taken to fill in the order they were listed, at most
  six are kept per market and kind, and an order whose direction changes
  only after a read keeps the kind it was first given.
- **The run** is the Assistant's cron turn with only `hyperliquid_access`
  and `skills`: it quotes and submits the intents as listed and may only skip
  an increase or lower it. The trader and the mandate decide every submit as
  they would anywhere else; nothing in the strategy path approves anything.
  The job is created from the topic the user asked in, with no `deliver`
  and `attach_to_session: true`: its reports land in that topic and join its
  conversation, so a reply there has them in context; the run itself is a
  fresh session. Never Inbox, which starts no work.
- **A stance** (`hermes-hyperliquid-stance/1`) is an advisor's choice per
  market of a direction, a variant and a size multiplier (at most the spec's
  `max_size`, at most 2), for at most `max_age_days` (14 at most), with a
  basis whose every item is dated no later than its issue. A turn between
  long and short sooner than `min_days_between_flips` after the last one
  makes the market flat until then. An invalid or expired stance falls back
  to the market's default with a note. A stance never widens a limit: the spec's
  limits and the mandate bound every order.
- **What the files cannot stop.** The spec and the stance are files the
  Assistant writes; nothing signs them, and the breaker's memory is the
  gate's `state.json`. The boundary is the mandate the user approved on its
  card, which the trader checks against the account at submit, and the run's
  toolsets, which leave out the file and terminal tools: a run can neither
  reset the breaker nor clear its trip.

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
4. To run strategies, the Assistant's machine-local cron job with
   `script: hl-strategy-gate.sh` and only the `hyperliquid_access` and
   `skills` toolsets; the strategy skill's "Running it" has the call.
