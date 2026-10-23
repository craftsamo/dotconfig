---
name: stripe-manage
description: "Use before changing anything in the user's Stripe: customers, products, prices, coupons, promotion codes, invoices (draft, finalize, send, void), payment links, refunds or subscriptions."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [stripe, invoices, refunds, subscriptions, coupons, payment-links, billing]
---

# Changing Stripe through the `stripe` tool

Reading is in `stripe-access:stripe`; load it too. This skill owns how a
change is prepared, approved and checked.

## Contract

- **Every change is one card.** Each write action shows Hermes' approval card
  (account, `Via` the organization and account id when the account is reached
  through an organization key, LIVE or test, and what changes, read fresh
  from Stripe) and runs only if the user approves it. Refunds, finalizing, sending and voiding an
  invoice, changing or canceling a subscription and deleting a coupon ask
  every time, even after "always".
- **Agree first, then card.** Settle the customer, amounts, currency, dates
  and wording with the user in chat, then make the call. `preview=true`
  returns the exact card without asking or changing anything; use it when the
  user wants to see it first or when you are unsure.
- **Live is real money.** Use `mode: test` only when the user is trying
  something out. Never switch mode to get around a refusal.
- **Denied means stop.** Never retry a denied or expired card unchanged.
- **No person, no change.** Where nobody can answer a card (cron, another
  agent's session, a single query) every change is refused. Prepare it with
  `preview=true` and hand the exact call back to whoever can ask the user.
- **Amounts are minor units.** JPY 3,000 is `3000`; USD 30.00 is `3000`. Read
  the `*_display` text on the card back to the user if in doubt.

## Outcomes

| Answer | Meaning | Next |
|---|---|---|
| `ok` with `done` and `result` | applied | report `result` (its `*_display` amounts) |
| `not done: …` | nothing changed | fix the cause or tell the user |
| `stopped part way: …` | the steps listed in `done` applied, the rest did not | read the object, tell the user what exists now |
| `UNCERTAIN: …` | sent, outcome unknown | read the object first; never repeat the call blindly |
| "what the card showed changed" | Stripe, the stored key or the account it reaches changed after the card | read again, then ask anew |

## Invoices

1. `invoice_create`: `customer`, `items` (each `{price, quantity}` with a
   one-time price, or `{amount, currency, description}` where `amount` is the
   line's total), optional `coupon` or `promotion_code`, `description`.
   `collection_method` defaults to `send_invoice`, due `days_until_due` (30)
   after finalizing. It makes a **draft**: nothing is sent or charged.
2. Read it (`invoices`, `id`) and check the total with the user.
3. `invoice_finalize`: it gets a number and becomes payable; no more edits.
4. `invoice_send`: e-mails it to the customer's address (test mode e-mails
   nothing). A paid invoice can be sent again as a receipt.

A wrong draft is fixed in the Stripe Dashboard or left as a draft; a wrong
open invoice is voided (`invoice_void`, final) and made again.

## Refunds

Read the payment first (`payments`, `id`): what was paid and refunded so far.
`refund_create` with `payment` (pi_…) or `charge`; `amount` defaults to all
that is left, so give it for a partial refund. `reason` is one of
`requested_by_customer`, `duplicate`, `fraudulent`. A refund cannot be undone.

## Subscriptions

- Change of plan or seats: `subscription_update` with `price` (a recurring
  price) and/or `quantity`; `item` (si_…) when it has several items.
  `proration`: `create_prorations` (default, the difference lands on the next
  invoice), `always_invoice` (invoiced now) or `none`. Say which to the user.
- End at the period's end: `subscription_update` `cancel_at_period_end: true`
  (undo with `false` before it ends). Prefer this when the user says "cancel".
- End now: `subscription_cancel`, only when the user asks for it now; it
  cannot be resumed. `invoice_now` / `prorate` only if the user wants them.
- A discount on a subscription: `coupon` or `promotion_code`; it replaces the
  ones it has.

## Catalogue, coupons and links

- A price's amount never changes: `price_create` a new one, then
  `price_update` `active: false` on the old one. Subscriptions and payment
  links keep the price they use.
- A coupon's terms never change (only `name` and metadata). For new terms,
  `coupon_create` a new one; stop the old one with `coupon_delete` (applied
  discounts stay) or by deactivating its codes.
- `promotion_code_create` gives customers a code for a coupon (optionally only
  one `customer`, `first_time`, a `minimum_amount`, a limit or an end date);
  `promotion_code_update` `active: false` stops it.
- `payment_link_create` makes a public checkout link from prices; anyone with
  it can pay. `payment_link_update` `active: false` stops it.

## Errors

"refused this key access" means the restricted key lacks the write permission
named in the message (or an organization key may not act on that account);
the user fixes it in the Stripe Dashboard. A setup
problem (no key, wrong mode) is the user's to fix: relay it, never work around
it.
