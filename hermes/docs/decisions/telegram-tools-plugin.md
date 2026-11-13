# Telegram runs on an upstream package, guarded here

Status: in force
Owner doc: docs/telegram-tools.md

## Decision

The Assistant reaches the user's Telegram account through the third-party
package craft-agent/telegram-tools, pinned to a release commit, instead of a
dotconfig plugin of its own. The person's OpenCode loads the same release
from npm, and both share one session, one sync service and one mirror.

- **Its card is the package's, not `card.py`.** The package draws the card
  from what each write tool says the call will do: facts first, the text last,
  fitted to the surface. It pins what the card showed into the call and fails
  the call as stale when the chat, a file or the text changed. That is the
  guarantee `card.py` and a digest check give our own plugins, so its shape is
  accepted as it is.
- **A standing answer covers the tool and its chat.** "Always" or "session"
  on a send lets later sends to that chat run unasked, unlike the
  `approval_tier.py` default, which repeats only the exact request. Saved
  answers are listed and revocable; the user answers "once" to a write they
  want asked again.
- **No Telegram send mandates.** No scheduled job sends to Telegram as the
  user. Writes need a person who can answer the card; a standing answer never
  allows a write where nobody can answer.
- **The guard is ours.** `plugins/guards/telegram-tools-guard` refuses writes
  where no person can answer and every call from an inbound A2A request,
  blocks the ways around the tools, runs the unpacked guard and draws the
  progress lines. It names the reads explicitly: `telegram_chat_mark_read`
  is a write ending in `_read`, so a suffix cannot decide what is safe. A
  block from any plugin wins over the package's approve. The package's
  handler does not refuse by itself, so the pin `requires` the guard and the
  profile validator refuses a config that enables the package without it.
- **The package itself refuses writes while the guard is not loaded.**
  Enabled is not loaded: a guard that fails to load would leave the package
  running unguarded, where the old plugin's own handler still refused. The
  package's `require_plugins` setting names the guard, and while Hermes has
  not loaded it every write is refused before it is approved
  ([craft-agent/telegram-tools#112](https://github.com/craft-agent/telegram-tools/issues/112)).
  The pin's `requires_setting` makes the validator refuse a config that does
  not name the guard there.
- **Excluded chats stay excluded, by the package.** The old plugin's
  `exclude_chats` hid those chats and refused every call naming them, and the
  Assistant relies on it. The package's own `exclude_chats` setting does the
  same ([craft-agent/telegram-tools#111](https://github.com/craft-agent/telegram-tools/issues/111)),
  rather than a check in the guard, which could refuse calls naming a chat but
  not keep it out of lists and search results. The list stays in the private
  config.
- **The auth key sits on disk.** The package keeps it in `session.sqlite`,
  owner-only under a mode-0700 state directory, where the old plugin kept it
  only in the Keychain. That storage is accepted; the guard refuses terminal
  and file-tool access to the state root.
- **Channels and disappearing-message retention are on.** This is the
  person's decision, taken knowing the package README's caution about
  Telegram API terms §3.3 (sponsored messages) and §1.4 (disappearing
  messages), not a claim that the terms permit it.
- **No actions for the Assistant.** Edit, delete, react, pin and mark read
  stay off.

## Why

One implementation serves every harness the person uses, with one account
and one history. The package owns its tools, card and sync service; this
repository keeps only the guard for how the Assistant runs here.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- The package's skills are its own; this repository adds only the Chat
  reference that says when the Assistant uses Telegram.
- WhatsApp keeps its send mandates.
