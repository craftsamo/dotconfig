# Stripe access

Stripe for the Assistant, Researcher and Marketer: balance, payments,
customers, subscriptions, invoices, products, prices, payment links, refunds,
coupons and promotion codes, in live or test mode, through the user's own API
keys. Every profile with the tool reads; the Assistant alone also changes
customers, products, prices, coupons, promotion codes, invoices, payment links,
refunds and subscriptions, each change behind an approval card. Nothing pays
out, transfers or charges a card directly. Read it when changing the plugin,
its keys or what it may call. Common rules: [access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                | Home                                                                                                            | Reader                          |
| ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Engine: validation, request building from a fixed table, key state, result shapes, amounts, write plans, approval card, bypass guard | `plugins/stripe-access/sta.py`                                                                                  | all                             |
| The only process holding a key; the endpoints it may call (`ROUTES`), the pinned API version                                         | `plugins/stripe-access/bridge.py`                                                                               | all                             |
| `stripe` tool and the `pre_tool_call` hook (toolset `stripe_access`), the actions each profile gets                                  | `plugins/stripe-access/__init__.py`                                                                             | Assistant, Researcher, Marketer |
| How a profile reads Stripe: modes, accounts, amounts, search, recovery                                                               | the `stripe-access:stripe` plugin skill (`plugins/stripe-access/skills/stripe/`)                                | Assistant, Researcher, Marketer |
| Changing Stripe: the card, invoices, refunds, subscriptions, the catalogue, outcomes                                                 | the `stripe-access:stripe-manage` plugin skill (`.../skills/stripe-manage/`); registered for the Assistant only | Assistant                       |

Stripe's own REST API, so no terms are stretched: the risk is the user's money
and customers, not the account. Everything is standard library, so there is no
venv and no install step; the bridge runs under Hermes' own interpreter in
isolated mode with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)). It
calls only `https://api.stripe.com`, only the method and path pairs in
`ROUTES`, never follows a redirect, and pins `Stripe-Version` so a change to
the account's default API version does not change what the tool sends or
reads.

## Profiles

| Profile    | Actions             | Inbound A2A |
| ---------- | ------------------- | ----------- |
| Assistant  | every read, changes | refused     |
| Researcher | every read          | reads       |
| Marketer   | every read          | reads       |

The action list a profile gets (`PROFILES`) is fixed when the plugin registers
and checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). An inbound request runs
only what `A2A` lists for the profile, never a change or a `preview`, and only
when the turn's bound profile home is that profile's, failing closed otherwise.
Every profile uses the same key for a label and mode, so what a key may do in
Stripe bounds the Assistant's changes, and the action lists keep Researcher and
Marketer to reads.

## Keys, modes and state

One Keychain item per account label and mode, in the `hermes` project under
the scope `stripe-access` ([secret scoping](access-common.md#secret-scoping)):
`STRIPE_KEY_<LABEL>_LIVE` and `STRIPE_KEY_<LABEL>_TEST`. A label (`work`,
`personal`) names one Stripe account; each business on its own Stripe account
gets its own label. The labels and the accounts behind them are private: they
stay in the Keychain and the state directory, never in tracked files.

Every action but `status` names its `mode`: `live` (real money) or `test` (a
test-mode or sandbox key; both use `_test_` keys). `account` picks the label;
it may be left out when one label holds a key for that mode. The bridge refuses
a key whose prefix disagrees with the mode (`sk_live_…` stored as
`…_TEST`), and a publishable key, before anything is sent. It lists labels
from the Keychain's metadata, reads only the item a call needs, and masks the
value (and anything shaped like a Stripe key) in every string it returns.

A 401 is a refused key, stored as in
[refusal memory](access-common.md#state-directory-and-bridge-process) per
label and mode, so later calls with that key are answered without Stripe until
a new key is stored. A 429 pauses that label and mode for 30 seconds. A 403 is
a restricted key without the permission a call needs: Stripe's message, which
names the permission, is passed on and nothing is remembered.

`~/.stripe-access/` (mode 700, outside every repository) holds no secret:
`state.json` (per label and mode: a refused key's fingerprint, a pause's end,
and the Stripe account id and display name `account` last read) and a lock.

## Reads

`status` never contacts Stripe: it lists the stored labels and modes, each
key's kind (`secret` or `restricted`) and any problem. `account` reads the
Stripe account behind a key, `balance` its funds. Every other read is a list
of one object type, or one object in full with `id` (a summary next to
Stripe's own object). Lists page with Stripe's cursors behind one `cursor`
argument, filter by creation time (`since` / `until`) and by the filters Stripe
offers for that type; `query` uses Stripe's search on the types that have it.
Payment links come with their line items: a listed link shows the first ones
Stripe expands and `line_items_more` when there are others, and a link read by
`id` reads them all. `since` / `until` take a date (a whole local day, resolved
on the calendar so a day across a DST change keeps its 23 or 25 hours), an ISO
time or epoch seconds.

Amounts stay in Stripe's integer minor units and each gets a `*_display` text
with its currency: zero-decimal currencies (JPY, KRW, …) and three-decimal ones
(KWD, …) are formatted by Stripe's own tables, and ISK and UGX keep two
decimals as Stripe takes them. Results carry a note that names, e-mails,
descriptions and metadata are customers' words, never instructions.

## Writes

Twenty change actions, each one request or (an invoice with its lines) a short
fixed sequence: customers and products (create, update), prices (create;
update only `active`, nickname and lookup key: an amount never changes),
coupons (create, rename, delete; terms never change) and promotion codes
(create with the current `promotion[coupon]` shape, activate or deactivate),
invoices (a draft with its lines, `auto_advance` off; finalize; send; void),
payment links (create from prices, update), refunds (of a payment or a charge,
the amount always explicit and at most what is left) and subscriptions
(change one item's price or quantity with a stated proration, the quantity
always sent so a price change keeps it; end at the period's end or not; set a
discount; cancel at once). An invoice is created in its lines' currency. A
discount goes on an
invoice or a subscription, never on a customer (Stripe dropped that). Nothing
pays an invoice, captures or creates a charge, pays out or transfers, and
nothing deletes a customer or a product: `ROUTES` has no such endpoint.

Each action takes only its own arguments; any other is refused, so a mistaken
argument is never dropped silently. The plan reads what the card shows from
Stripe first (the customer, the price, the payment and what was refunded, the
subscription's items, the coupon's terms) and blocks a change that would fail:
a recurring price on an invoice line, mixed currencies, a refund above what is
left, an invoice in the wrong state, a subscription with several items and none
named. `preview=true` runs the same plan and returns the card without asking or
changing anything; it works in any run.

At execution the handler plans again and refuses if anything the card showed
or would send differs (someone refunded meanwhile, the invoice moved on,
another key was stored). Every request carries the approved key's fingerprint,
and the bridge sends nothing under a different stored key. Every POST carries
an `Idempotency-Key` derived from a nonce of that approval and the step, so a
request Stripe already received is never applied twice, and two approvals of
the same change (even under a reused tool-call id) never share a key. The steps
run in order and stop at the first failure; each outcome is reported this way:

- **`not done`:** nothing changed. Stripe answered the first step with a 4xx
  other than 409, or nothing was sent.
- **`stopped part way`:** the steps listed in `done` applied, then Stripe
  refused one; an invoice draft may exist without all its lines.
- **`UNCERTAIN`:** a step was sent and its answer does not show whether it
  applied (a timeout, a broken connection, a 5xx, a 409 from a concurrent
  identical request). Read the object first.

Nothing is retried. An invoice made by `invoice_create` is read back at the
end; the answer says that finalizing and sending are separate cards.

## Approval

The card is plain lines within Telegram's budget: `Stripe · LIVE, real money ·
account <label> (<account name>)` or `test mode`, then what changes, with every
amount in its currency. Names, e-mails, descriptions and codes from Stripe are
collapsed to one line with control and invisible characters spelled out, so a
customer's text cannot forge card lines. Lines that must be seen (what changes,
the money, what cannot be undone, a subscription item's price and quantity
before and after, every recurring price a payment link starts) always fit, or
the change is refused; detail lines (invoice lines, one-time link items,
metadata) are counted when they do not.

The approval record is per tool call and allows one change. Its rule key
hashes the exact plan, so "session" or "always" repeats only that identical
change. A refund, finalizing, sending or voiding an invoice, changing or
canceling a subscription and deleting a coupon get a fresh key every time
(`ONCE`), so no stored answer ever covers one.

## Where a write may run

A change is refused wherever no person can answer its card, through the shared
check ([approval gate](access-common.md#approval-gate)); the hook and the
handler each refuse before a card is built, and the answer names the reason.
Reads and `preview=true` are unaffected.

## Ways around the tool

On every profile with the tool the hook blocks terminal calls whose text names
the plugin, a `STRIPE_KEY_` item, `api.stripe.com`, a Stripe key, the Stripe
CLI's commands or its config (`~/.config/stripe`) or an inline Stripe SDK
import, and file-tool calls on the state directory, the key names or the CLI's
config. File tools may still read the plugin source, and the browser may still
open the Stripe Dashboard. Patterns: `_TERMINAL` and `_STORE` in
`plugins/stripe-access/sta.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool). The toolset
is in an `a2a` platform toolset only where `A2A` lists actions (Researcher,
Marketer), never the Assistant's.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. In the Stripe Dashboard, create a restricted key (Developers → API keys)
   with read access to what the profiles should see and write access only to
   what the Assistant should change; a secret key works too but grants
   everything. Store it with
   `secret set STRIPE_KEY_<LABEL>_<LIVE|TEST> -p hermes --scope stripe-access -D TOKEN --no-env`
   and paste the key at the hidden prompt. `--no-env` keeps it out of
   `secret env` as a second guard beside the scope.
2. Enable the plugin and add `stripe_access` to the profile's `toolsets` and
   `platform_toolsets` (`a2a` only for Researcher and Marketer), then restart
   the gateway. The three example configs in this repo have it; the private
   configs carry the same entries.
3. `status` shows each stored key; `account` with its mode confirms Stripe
   accepts it.
