# X runs on an upstream package, guarded here

Status: in force
Owner doc: docs/x-tools.md

## Decision

The Assistant, Marketer and Searcher read X through the third-party package
craft-agent/x-tools, pinned to a release commit, instead of the dotconfig
plugin x-access. The person's OpenCode loads the same release from npm.

- **Reads go to FxTwitter first.** The package reads FxTwitter's public API and
  falls back to the reading account only where that cannot answer, so most
  reads spend none of the sub-account's caps and less of its risk.
- **The caps are the package's and shared.** One count serves every profile
  and OpenCode. Searcher keeps its smaller share by setting lower caps against
  that shared count rather than a count of its own, so it stops first.
- **The cookies sit in the package's state file.** The package reads a cookie
  file (mode 0600) or an `X_TOOLS_COOKIES_*` variable, never a profile's secret
  scope. A variable would put them in the gateway's process environment for
  every profile, so the person writes the file with `x-tools-cli login` from
  the Keychain item, which stays the original. The old plugin kept them only
  in the Keychain and read them per call; a copy on disk under the user's
  state directory is accepted, with the guard keeping the terminal and file
  tools out of it.
- **Its card is the package's, not `card.py`.** Its one write the profiles
  hold, a media save to the local disk, is held by the package's card, which
  pins what it showed into the call.
- **No grants.** No scheduled job saves media, so the `grants` toolset stays
  off and a save needs a person who can answer the card.
- **The guard is ours.** `plugins/guards/x-tools-guard` refuses the package's
  writes where no person can answer and to an inbound A2A request, blocks the
  ways around the tools and draws the progress lines. It names the reads
  explicitly, so a tool the package adds later counts as a write; Hermes' own
  `x_search` is named as foreign and left alone. The pin `requires` the guard,
  and the package's `require_plugins` setting names it.
- **Marketer and Searcher run it read-only.** `read_only` registers no write
  tool and no write skill there.
- **What the package lacks is dropped or moved, not rebuilt.** The six-hourly
  ledger of the user's own counts and saved FxTwitter replies are retired;
  the browser draft procedures became Assistant technics and the ranking
  watch a script of this repository, since neither needed the old tool.

## Why

One implementation serves every harness the person uses, with more of X than
the old plugin read (quotes, conversations, timelines, followers, lists,
communities, trends). The package owns its tools, engine, card and skills;
this repository keeps only the guard, the settings and the two procedures
that were never about reading.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal. A release that
  pins another twscrape needs `x-tools-cli engine install` again.
- New cookies need `x-tools-cli login` after the Keychain item changes.
- Marketer compares the user's posts by public counts read at a similar age,
  with no history kept between reads.

## Do not

- Put the cookies in an environment variable or a layer `profile-secrets.sh`
  emits.
- Name a read by a `_read` suffix in the guard, or let a new x-tools tool
  through until it is named.
- Deny `x_*` as a pattern anywhere: it takes `x_search` with it.
- Turn on `grants` without a decision of its own.
