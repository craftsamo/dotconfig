# Signal runs on an upstream package, guarded here

Status: in force
Owner doc: docs/signal-tools.md

## Decision

The Assistant reaches the user's Signal account through the third-party
package craft-agent/signal-tools, pinned to a release commit, instead of a
dotconfig plugin of its own. The person's OpenCode loads the same release from
npm, and both share one linked device, one sync service and one mirror.

- **Its card is the package's, not `card.py`.** The package draws the card
  from what each write tool says the call will do: facts first, the text last,
  fitted to the surface. It pins what the card showed into the call and fails
  the call as stale when the chat, a file or the text changed. That is the
  guarantee `card.py` and a digest check give our own plugins, so its shape is
  accepted as it is.
- **A standing answer covers the tool and its chat.** "Always" or "session"
  on a send lets later sends to that chat run unasked, unlike the
  `approval_tier.py` default, which repeats only the exact request. The
  package keeps that grain on purpose: every harness it serves remembers an
  answer per tool or target, and saved answers are listed and revocable. The
  user answers "once" to a write they want asked again.
- **No send mandates for Signal.** No job sends to Signal on a schedule, so
  a send always has a card, and nothing sends where no person can answer.
- **The guard is ours.** `plugins/guards/signal-tools-guard` refuses writes
  where no person can answer and every call from an inbound A2A request,
  blocks the ways around the tools, runs the unpacked guard and draws the
  progress lines. A block from any plugin wins over the package's approve,
  so the guard holds whatever the package does, as long as it is loaded: the
  package's handler does not refuse by itself, so the pin `requires` the
  guard and the profile validator refuses a config that enables the package
  without it. What depends on how this setup runs (YOLO used for reads, peers
  that cannot answer a card, the runtime's private preview table) stays here
  and out of the package.

## Why

One implementation serves every harness the person uses, with one account and
one history, and its card was built for this: the gaps found in it (a card
that described nothing, unpinned text past the cut, sessions sharing a pin)
were fixed upstream rather than worked around here.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- The package's skills are its own; this repository adds only the Chat
  reference that says when the Assistant uses Signal.
- Mandates for Telegram and WhatsApp are unchanged.
