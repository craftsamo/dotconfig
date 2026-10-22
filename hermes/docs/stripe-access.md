# Stripe access

Stripe for the Assistant, Researcher and Marketer: balance, payments,
customers, subscriptions, invoices, products, prices, payment links, refunds,
coupons and promotion codes, in live or test mode, through the user's own API
keys. Every profile with the tool reads. Read it when changing the plugin, its
keys or what it may call. Common rules: [access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                    | Home                                                                             | Reader                          |
| -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------- |
| Engine: validation, request building from a fixed table, key state, result shapes, amounts, bypass guard | `plugins/stripe-access/sta.py`                                                   | all                             |
| The only process holding a key; the endpoints it may call (`ROUTES`), the pinned API version             | `plugins/stripe-access/bridge.py`                                                | all                             |
| `stripe` tool and the `pre_tool_call` hook (toolset `stripe_access`), the actions each profile gets      | `plugins/stripe-access/__init__.py`                                              | Assistant, Researcher, Marketer |
| How a profile reads Stripe: modes, accounts, amounts, search, recovery                                   | the `stripe-access:stripe` plugin skill (`plugins/stripe-access/skills/stripe/`) | Assistant, Researcher, Marketer |

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

| Profile    | Actions    | Inbound A2A |
| ---------- | ---------- | ----------- |
| Assistant  | every read | refused     |
| Researcher | every read | reads       |
| Marketer   | every read | reads       |

The action list a profile gets (`PROFILES`) is fixed when the plugin registers
and checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). An inbound request runs
only what `A2A` lists for the profile, and only when the turn's bound profile
home is that profile's, failing closed otherwise.

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
   with read access to what the profiles should see; a secret key works too but
   grants everything. Store it with
   `secret set STRIPE_KEY_<LABEL>_<LIVE|TEST> -p hermes --scope stripe-access -D TOKEN --no-env`
   and paste the key at the hidden prompt. `--no-env` keeps it out of
   `secret env` as a second guard beside the scope.
2. Enable the plugin and add `stripe_access` to the profile's `toolsets` and
   `platform_toolsets` (`a2a` only for Researcher and Marketer), then restart
   the gateway.
3. `status` shows each stored key; `account` with its mode confirms Stripe
   accepts it.
