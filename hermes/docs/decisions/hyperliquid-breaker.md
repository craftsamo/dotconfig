# A Hyperliquid strategy holds its entries at a drawdown, and only the user resumes it

Status: in force
Owner doc: docs/hyperliquid.md "Strategies"

## Decision

Every strategy spec sets a breaker: a drawdown, in percent of the strategy's
own result, at which the gate stops listing entries and leverage changes.
The result is an index the gate moves each run by what the strategy's
markets earned (fills less fees, funding, the change in unrealized result)
as a share of the account's value then. A tripped breaker holds entries
until the user resumes it, written as a reset later than the trip; closes,
stops and trailed stops never wait on it. A spec without a breaker opens
nothing.

## Why

- A mandate bounds an order, the exposure, the leverage, the rate and the
  time, but not a losing streak: a strategy can keep trading inside it while
  its losses run past anything its backtest showed. The breaker is the bound
  for that, set from the tested drawdown (its walk-forward result and the
  Monte Carlo's spread) rather than from feel.
- Measuring the strategy's own markets keeps deposits, withdrawals and a
  trade the user makes elsewhere out of it, and a share of the account's
  value keeps the measure in step with sizes, which follow that value.
- Holding only entries keeps positions under their stops and trend exits; a
  forced close at the trip would sell the low the rules expect to recover
  from.
- Resuming is a judgment about whether the strategy still works, so it stays
  the user's: an automatic restart would put the same rules back into the
  market that just broke them.

## Do not

- Let a run, a stance or an advisor reset the breaker or clear a trip.
- Measure the breaker from the account's value alone, count a window of
  fills or funding the gate did not read whole, or end that window anywhere
  but the account read it is set against.
- Start a breaker fresh when its memory could not be read: a lost trip
  would resume entries no one approved.
- Hold closes, stops or trailed stops on the breaker.
- Run entries for a spec without a breaker.
