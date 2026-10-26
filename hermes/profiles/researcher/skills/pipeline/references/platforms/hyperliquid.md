# Hyperliquid

Hyperliquid's perp and spot venue, mainnet and testnet, read through the
`hyperliquid` tool. It reads only: nothing is signed or sent, and any account
can be read by its address. The venue's own app and explorer show the same
state; cite the tool's read, with the explorer link it returns for an account
as its locator. The tool's actions and mechanics are
`skill_view(name="hyperliquid-access:read")`; this file holds how the
evidence is weighed.

## What the venue proves

The kernel's source evaluation and on-chain rules apply. In addition:

- **A read is a moment.** Prices, funding, open interest, the book and an
  account's positions hold at the time the read returns (`time`, or the read's
  own time when none is given). Cite the network and that time; a value
  without them is not reproducible. Mainnet and testnet are separate venues:
  a testnet figure is never evidence about mainnet.
- **An account is an address, not a person.** Positions, fills and orders of
  an address are Observation; who controls it is not in the venue. A label
  from the web or an explorer is a source to cite, not a finding.
- **Annualized funding is arithmetic.** `funding_apr_pct` multiplies the
  current hourly rate by a year: a snapshot to state as such, never a yield
  forecast. Use `funding` over a window for what was actually paid.
- **`review` findings are Inference.** Fee drag, concentration and losses
  against the trend come from fills alone, which hold no intent, order
  placement or slippage; confirm them in `fills`, `orders`, `candles` and
  `funding` for the same window before stating them, and judge decisions
  apart from outcomes.
- **A `backtest` is a simulation, and only its unseen windows count.** Its
  figures follow from its own fill model (the next bar's open, slippage, the
  taker fee, funding, a stop inside a bar) over past bars; the whole-window
  `result` is in-sample, and choosing rules on it fits the past. What a rule
  set would have earned is `walk_forward.out_of_sample`, with each fold's
  chosen rules. State the window, the `sources` (older Binance spot candles
  are prices only, and `unread` says how much funding was assumed), the
  costs and the `fingerprint`; never a forecast.
- **A `monte_carlo` spread is Inference about order, not new data.** It
  redraws the same trades in random order as independent draws, so it says
  how deep a drawdown those trades could have reached in another order, not
  what unseen markets will do; losses that cluster in one regime are spread
  out by the draws. Report `observed` beside `p50` / `p95`, and the spread of
  `out_of_sample` over that of the in-sample `result`.
- **Third-party listings.** Builder perp dexs (`dex:COIN`) and spot tokens
  are deployed by third parties; names arrive as `{"untrusted": …}` when they
  are more than a short ticker. A name like a famous asset is the deployer's
  claim, never identity.

## Patterns

1. **How a market is positioned.** `markets` with `coin` for mark, oracle,
   open interest, funding and max leverage; `funding` over the window in
   question for its history; `book` for the depth that a large order would
   meet now.
2. **How an account trades.** `state` for positions, leverage and liquidation
   prices; `fills` for what it did, `orders` for what it intends; `review` to
   find the coin or window that matters first.
3. **A reproducible window.** Give `end_time` with `hours`: the same request
   then reads the same candles and funding. `export` returns them as one
   dataset with its `schema` and `window`; it carries no fill or slippage
   model, so a backtest built on it states its own.
4. **A rule's track record.** `backtest` with `end_time`, the costs stated and
   `walk_forward` over a small grid; `long_history` for the years before the
   venue's own candles. A judgment the brief wants tested (a macro reading, a
   positioning extreme) is first written as a rule over data dated before
   each decision, then passed as `stance` windows; judging past markets with
   hindsight is not a test.

## Limits

- Only an account's newest 10000 fills and an interval's newest 5000 candles
  exist; `orders` with `history` is recent orders only. `unread` names what a
  read did not cover: carry it into the evidence as uncovered ground.
- `book` is one snapshot, not a time series; the public endpoint is
  rate-limited, so bound sweeps over many accounts or coins like any other
  gathering.
- An empty result over a window is not "none ever".
