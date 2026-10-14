# Hyperliquid trades without a card only inside a mandate

Status: in force
Owner doc: docs/hyperliquid.md "Mandates"

## Decision

An order that can add exposure runs without its approval card only inside a
mandate the user approved on a card of its own: one Hermes account on one
network, named perp markets, a value per order, a total held in those
markets (positions and resting orders together), a highest leverage, orders
an hour, and an end at most 30 days out. The trader checks the fit against the
account read at submit, under the wallet lock. Reduce actions never need one;
spot, margin taken out, withdrawals, sends and new mandates are never covered.

## Why

- The user wants automated trading to work unattended (cron), which a card
  per order rules out, while a profile-wide limit with no card would let a
  prompt injection trade freely up to that limit.
- One card for bounds keeps the user's consent explicit and bounded in
  markets, size, leverage, rate and time, and a revoke ends it at once.
- Bounds are checked against the venue as it stands, not a running total
  Hermes keeps, so fills, liquidations and trades from other clients are all
  counted.

## Do not

- Let a mandate approve another mandate, or widen one without its card.
- Cover spot or withdrawals with a mandate: their loss is not bounded by
  position value.
- Count exposure from Hermes' own ledger instead of the account read at
  submit, or value an order below the market's price now.
- Decide what is in force from the event log: only the MAC'd head does.
- Remove the 30-day ceiling: a forgotten mandate should lapse on its own.
