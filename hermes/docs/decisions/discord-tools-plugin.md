# Discord runs on an upstream package, guarded here

Status: in force
Owner doc: docs/discord-tools.md

## Decision

The Assistant reaches the user's Discord account through the third-party
package craft-agent/discord-tools, pinned to a release commit, instead of a
dotconfig plugin of its own. The person's OpenCode loads the same release
from npm, and both share one token, one sync service and one mirror.

- **Its card is the package's, not `card.py`.** The package draws the card
  from what each write tool says the call will do: facts first, the text last,
  fitted to the surface. It pins what the card showed into the call and fails
  the call as stale when the chat, a file, a message or a role changed. That
  is the guarantee `card.py` and a digest check give our own plugins, so its
  shape is accepted as it is.
- **A standing answer covers the tool and its target.** "Always" or "session"
  on a send lets later sends to that chat run unasked, unlike the
  `approval_tier.py` default, which repeats only the exact request. Saved
  answers are listed and revocable; the user answers "once" to a write they
  want asked again. Role changes are the exception the package keeps: each is
  asked, whatever was answered before.
- **No Discord send mandates, no grants.** No scheduled job writes to Discord
  as the user, so the `grants` toolset stays off. Writes need a person who can
  answer the card; a standing answer never allows a write where nobody can
  answer.
- **The guard is ours.** `plugins/guards/discord-tools-guard` refuses writes
  where no person can answer and every call from an inbound A2A request,
  blocks the ways around the tools, runs the unpacked guard and draws the
  progress lines. It names the reads explicitly: `discord_read_mark` is a
  write named like a read, so a suffix cannot decide what is safe. A block
  from any plugin wins over the package's approve. The package's handler does
  not refuse by itself, so the pin `requires` the guard and the profile
  validator refuses a config that enables the package without it.
- **The package itself refuses writes while the guard is not loaded.**
  Enabled is not loaded: a guard that fails to load would leave the package
  running unguarded. The package's `require_plugins` setting names the guard,
  and while Hermes has not loaded it every write is refused before it is
  approved. The pin's `requires_setting` makes the validator refuse a config
  that does not name the guard there.
- **The token sits on disk.** The package keeps it in the label's `token`
  file, owner-only under a mode-0700 state directory, where the old plugin read
  it from the Keychain at each start. That storage is accepted: the sync
  service cannot inherit a token from the gateway's environment, and a token
  variable in a secret layer would reach the Assistant's whole process. The
  guard refuses terminal and file-tool access to the state root and to the
  Discord app's data.
- **The old mirror is not imported.** The package has no importer, and the
  sync and `backfill` rebuild what the Assistant reads. The old state stays on
  disk until the person removes it.
- **The Assistant keeps what the old plugin could do.** Edits and deletes of
  the user's own messages, reactions, pins and a server's roles stay on, each
  behind its card; creating threads and forum posts stays off.
- **User-account automation is the person's risk.** Discord's terms forbid
  automating a user account, and the package's README warns the account can be
  closed for it, reads included. The person accepted that, as with the old
  plugin; it is not a claim that the terms permit it.

## Why

One implementation serves every harness the person uses, with one account
and one history. The package owns its tools, card and sync service; this
repository keeps only the guard for how the Assistant runs here.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- The package's skills are its own; this repository adds only the Chat
  reference that says when the Assistant uses Discord.
- WhatsApp keeps its send mandates.
