# GitHub runs on an upstream package, guarded here

Status: in force
Owner doc: docs/github-tools.md

## Decision

The Assistant reaches GitHub through the third-party package
craft-agent/github-tools, pinned to a release commit, instead of a dotconfig
plugin of its own. The person's OpenCode loads the same release from npm.

- **Its card is the package's.** The package draws a card per write from what
  the tool says the call will change, and pins what it showed into the call;
  the call fails as stale when the target changed. That is the guarantee
  `card.py` and a digest check give our own plugins, so its shape is accepted
  as it is.
- **A standing answer covers the tool and its target.** "Always" or "session"
  on a write lets later calls of that tool on that repository or board run
  unasked, unlike the `approval_tier.py` default, which repeats only the exact
  request. The package keeps that grain on purpose: every harness it serves
  remembers an answer per tool and target, and saved answers are listed and
  revocable. The user answers "once" to a write they want asked again.
- **No mandates.** The package stays neutral across harnesses, so it knows no
  mandate. A card per write, with a "session" answer for a job's routine
  updates, replaces them. The bound mandates gave by tier is now the user's
  choice of answer plus the guard's refusals.
- **The guard is ours.** `plugins/guards/github-tools-guard` refuses writes
  where no person can answer and every call from an inbound A2A request,
  blocks the terminal's `gh` writes and the ways around the tools, and draws
  the progress lines. A block from any plugin wins over the package's
  approve, so the guard holds whatever the package does, as long as it is
  loaded: the package's handler does not refuse by itself, so the pin
  `requires` the guard and the profile validator refuses a config that
  enables the package without it.
- **Runs deliver PRs, and the Assistant writes the record.** An OpenCode run
  reads GitHub; a write run may open its PRs, link its stack and set their
  labels, assignees, reviewers and milestone on the caller's `once`. The caller
  cannot approve an Issue or board write, or a PR edit that carries anything
  more. The Assistant writes the record and mirrors the run's progress on its
  own cards.
- **Its skills arrive whole.** The package registers every skill it ships;
  the Assistant's conventions are its own technics, which point to them.

## Why

One implementation serves every harness the person uses, and its card was
built for this. A write that needs a person's answer is simpler to reason
about than a write whose bounds were fixed in advance.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- Widening what a run may write, or approving one for the caller, reopens
  GitHub writes with no card.
- Mandates for Hyperliquid, WhatsApp, Cloudflare and gcloud are unchanged.
