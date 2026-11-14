# Cloudflare runs on an upstream package, guarded here

Status: in force
Owner doc: docs/cloudflare-tools.md

## Decision

The Assistant, Researcher and Marketer reach the user's Cloudflare accounts
through the third-party package craft-agent/cloudflare-tools, pinned to a
release commit, instead of a dotconfig plugin of its own. The person's
OpenCode loads the same release from npm.

- **Its card is the package's, not `card.py`.** The package draws the card
  from what each write tool says the call will do, fitted to the surface, and
  pins what the card showed into the call. That is the guarantee `card.py`
  and a digest check give our own plugins, so its shape is accepted as it is.
- **A standing answer covers the tool and its targets, for every write.**
  "Always" or "session" lets later calls of that tool on the same zone,
  record or Worker run unasked, deletes and a purge of a whole zone included;
  the old plugin gave every 🚨 change a fresh key. The user answers "once" to
  a write they want asked again.
- **No zone mandates, no grants.** No mandate was ever made, and no scheduled
  job writes to Cloudflare, so the `grants` toolset stays off. Writes need a
  person who can answer the card; a standing answer never allows a write where
  nobody can answer.
- **The guard is ours.** `plugins/guards/cloudflare-tools-guard` refuses
  writes where no person can answer and every write of an inbound A2A request,
  blocks the ways around the tools and draws the progress lines. It names the
  reads explicitly, so a tool the package adds later counts as a write. A block
  from any plugin wins over the package's approve. The pin `requires` the
  guard, and the package's `require_plugins` setting names it, so the package
  refuses every write while the guard is not loaded; the profile validator
  refuses a config without either.
- **Researcher and Marketer run it read-only.** `read_only` registers no
  write tool and no write skill there, as their old action lists kept them to
  reads.
- **The tokens sit in the gateway's process environment.** The package's
  Hermes plugin starts its command line with a copy of `os.environ`, never the
  calling profile's secret scope, so the gateway launcher puts the pairs of
  the `cloudflare-tools` Keychain scope there. Every profile the gateway
  serves then holds them, and the terminal tool passes them to its commands;
  the old plugin kept them `--no-env` and read them only in its bridge. The
  guard blocks the obvious reads (the variable names, commands that print
  the environment) in the three profiles that use the tools; other profiles
  have no such guard, and a CLI session has no token at all. Accepted as the
  smallest change; the package reading the profile's secret scope, as
  Hermes' plugin contract asks, is filed upstream with the starter it comes
  from, and lifts this once a release does.

## Why

One implementation serves every harness the person uses, with more of
Cloudflare than the old plugin covered (rules, Queues, Hyperdrive, Vectorize,
Turnstile, Access, Registrar). The package owns its tools, card and skills;
this repository keeps only the guard and the token's way into the gateway.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- The package's skills are its own; nothing here repeats how the tools are
  used.
- Changing a token needs a gateway restart.
- The webhook tunnel's connector token is not the tools' and stays where
  [ops/services.md](../ops/services.md) "Webhook tunnel" keeps it.

## Do not

- Put the tokens in a layer `profile-secrets.sh` emits (the package never
  reads a profile's secret scope, so they would only widen who holds them), or
  store them `--no-env` (the launcher would get none).
- Name a read by a `_read` suffix in the guard, or let a new tool through
  until it is named.
- Turn on `grants` without a decision of its own.
