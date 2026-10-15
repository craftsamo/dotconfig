# Unattended Hyperliquid trading runs rules, and an advisor only chooses among them

Status: in force
Owner doc: docs/hyperliquid.md "Strategies"

## Decision

The Assistant trades on its own only through a strategy: rules a backtest
validated, recorded by fingerprint in a spec the user decided, run by a cron
gate that decides from public reads with the same code the backtest used, and
bounded by a mandate the user approved on its card. On a run the model only
executes the gate's quotes, and may skip an increase or make it smaller. An
advisor's judgment enters as a stance: per market a direction, a validated
variant and a size multiplier inside the spec's bounds, dated and expiring.

## Why

- A rule run on completed bars is the same in a backtest and in cron, so its
  record can be checked before money follows it; a model deciding each trade
  cannot be tested on the past (it knows what came after) and costs a model
  turn every tick.
- The gate answers `{"wakeAgent": false}` when nothing is due, so watching is
  free and a model runs only to act.
- A model that can only remove risk from what the rules list cannot be
  talked into adding any: text it reads, including an advisor's basis, is
  never a quote.
- Choosing among validated variants and scaling size lets an advisor lean
  into a view without writing new rules, while every order still fits the
  mandate.

## Do not

- Let a run make, widen or renew a mandate, or quote anything the gate did
  not list.
- Run a variant whose rules differ from the backtest its fingerprint names.
- Let a stance raise a limit or choose outside the spec's advisor bounds.
- Give the gate a key, a signing path or the venue's `/exchange` endpoint.
- Give the cron run the file or terminal tools.
