# A card's reach is a tier, decided in one table

Status: in force
Owner doc: docs/access-common.md "Approval gate"

## Decision

What an answer on an approval card covers is decided in one place,
`plugins/_shared/approval_tier.py`, from a table of plugin → action → rule. A
rule has one of four tiers:

- **each** (the default for every action not in the table): the allowlist key
  hashes the exact request, so "session" or "always" repeats only that request.
- **standing**: the key binds a target (a spreadsheet, a video, an account, a
  channel) and not the request, so one answer covers the later calls to that
  target.
- **mandate**: no card inside bounds the user set on a card of its own
  ([GitHub](github-mandates.md), [Hyperliquid](hyperliquid-mandates.md)). The
  mandates keep their own code; the table only names the tier.
- **free**: no card. Empty on purpose.

A standing key applies only when the card's own level is one the rule lists:
✅ unless the rule says otherwise, never 🚨. The level is read on each call, so
the same action on a card that reaches others keeps its exact key. Two rules
that predate the tiers (Sheets edits, YouTube detail edits) also list ⚠️; the
snapshot test names them and nothing else may.

The table is code, and `scripts/tests/test_approval_tiers.py` pins it. A
standing rule has to name what it binds (its scope), and a call with no such
target, or one the plugin marks ineligible (a destructive edit), gets the exact
key.

## Why

- A card for every draft or note to oneself trains the user to approve
  without reading, the same cost that led to mandates. "Session" or "always"
  on an exact key cannot express "my own Note to Self"; a key bound to the
  account can.
- Gating on the card's level makes a table mistake safe: listing a
  dangerous action as standing does nothing for the cards that are dangerous.
- One table and one pinning test make loosening a card a visible, reviewed
  edit, where a hand-built key in a plugin is invisible.
- The free tier stays empty because a card-free write also runs where no one
  can answer (cron, single-query). The wallet and Hyperliquid paths that skip
  a card for the user's own wallets decide that in their own code.

## Do not

- Build a broad key by hand in a plugin, or give a standing key to a card at a
  level the rule does not list.
- Bind a standing key to an action alone: it needs a target, or one answer
  covers every chat or account.
- Check an executed write against the card's allowlist key. A standing key names
  only the target, so each plugin keeps a digest of what the card showed and
  compares that at the write.
- Compute a card's level twice, once for the card and once for the key: both read
  one function, so they cannot disagree about how risky a call is. A call whose
  effect depends on state outside the arguments (a draft that is already
  scheduled, a Saved Messages row of another account) reads that state in it.
- Let anything but a change to the table and its pinning test loosen a tier. No
  config setting widens it: a profile can edit its own config.
- Add a free rule without deciding how it behaves where no person can answer.
