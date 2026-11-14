# WhatsApp runs on an upstream package, guarded here

Status: in force
Owner doc: docs/whatsapp-tools.md

## Decision

The Assistant reaches the user's WhatsApp accounts through the third-party
package craft-agent/whatsapp-tools, pinned to a release commit, instead of a
dotconfig plugin of its own. The person's OpenCode loads the same release from
npm, and both share one linked device per label, one sync service and one
mirror.

- **Its card is the package's, not `card.py`.** The package draws the card from
  what each write tool says the call will do: facts first, the text last, fitted
  to the surface. It pins what the card showed into the call and fails the call
  as stale when what it showed changed. That is the guarantee `card.py` and a
  digest check give our own plugins, so its shape is accepted as it is.
- **A standing answer covers the tool and its chat.** "Always" or "session" on a
  write lets later calls of that tool on that chat run unasked, unlike the
  `approval_tier.py` default, which repeats only the exact request. Saved
  answers are listed and revocable; the user answers "once" to a write they want
  asked again.
- **No WhatsApp send mandates, and no grants.** Mandates of the old
  `whatsapp-access` plugin are not carried over, and the `grants`
  toolset stays off with `unattended` unset. Writes need a person who can answer
  the card; a standing answer never allows a write where nobody can answer.
- **The guard is ours.** `plugins/guards/whatsapp-tools-guard` refuses writes
  where no person can answer and every call from an inbound A2A request, blocks
  the ways around the tools (the package's CLI, `wacli` itself, `~/.wacli`, the
  package's state, logs and launch agents, WhatsApp Desktop's data, and the old
  plugin's state, mandates and launcher until it is removed), runs the unpacked
  guard and draws the progress lines. It names the reads explicitly
  (`whatsapp_account_read`, `whatsapp_chat_read`, `whatsapp_contact_read`,
  `whatsapp_grant_read`), so a new tool fails closed as a write. A block from
  any plugin wins over the package's approve. The package's handler does not
  refuse by itself, so the pin `requires` the guard and the profile validator
  refuses a config that enables the package without it.
- **The package itself refuses writes while the guard is not loaded.** Enabled
  is not loaded: a guard that fails to load would leave the package running
  unguarded. The package's `require_plugins` setting names the guard, and while
  Hermes has not loaded it every write is refused before it is approved. The
  pin's `requires_setting` makes the validator refuse a config that does not
  name the guard there.
- **Excluded chats stay excluded, by the package.** The private config's
  `exclude_chats` (quoted JIDs) hides those chats from every tool and refuses
  calls naming them before approval, rather than a guard check that could not
  hide them from lists and searches.
- **Keys sit on disk in the state directory.** The package keeps `wacli`'s
  session keys, mirror and media under `~/.local/state/whatsapp-tools/<label>/`
  (mode 0700), just as the old plugin kept them on disk under `~/.wacli`, so no
  Keychain layout changes; the guard refuses terminal and file-tool access to
  the state root, `~/.wacli` and WhatsApp Desktop's data.
- **Moving needs a new pairing.** The package never uses `~/.wacli`, so moving
  means pairing a new linked device (a phone takes at most four); the old plugin
  stays installed until cutover, then its sync agents are retired and the old
  device unlinked before the old plugin is removed in a later change.
- **Actions are on for the Assistant.** `actions` (archive, mark read, mute,
  pin, delete, edit, react) is enabled alongside `account`, `chats`,
  `contacts`, `history`, `sends` and `files` by the person's decision, each
  behind its card.
- **Unofficial-client automation is the person's risk.** `wacli` is an
  unofficial whatsmeow linked-device client, and WhatsApp may limit or ban
  accounts using unofficial clients. The person accepted that, as with the old
  plugin.

## Why

One implementation serves every harness the person uses, with one linked device
per label and one mirror. The package owns its tools, card and sync service;
this repository keeps only the guard for how the Assistant runs here.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- The package's skills are its own; this repository adds only the Chat reference
  that says when the Assistant uses WhatsApp.
- When `whatsapp-access` is removed in a later change, its send mandates and
  `plugins/messaging/_shared/send_mandate.py` are retired with it.
