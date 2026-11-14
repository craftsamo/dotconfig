# WhatsApp tools

The Assistant's access to the user's own WhatsApp accounts: reading chats and
messages, searching, counting activity, finding contacts and checking whether a
number is on WhatsApp, backfilling older history into the mirror, saving
received files, sending text and workspace files, archiving, muting, pinning and
marking chats read, and reacting to, editing and deleting the user's own
messages, each write after the user answers the approval card. It runs on the
third-party package
[craft-agent/whatsapp-tools](https://github.com/craft-agent/whatsapp-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin of
our own: [decision](decisions/whatsapp-tools-plugin.md). Common rules:
[access-common.md](access-common.md). It is not the gateway's WhatsApp
platform, which would make WhatsApp a channel to Hermes; nothing here lets
people talk to Hermes over WhatsApp. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

The package joins each account as a linked device, the way WhatsApp Web does,
through [`wacli`](https://github.com/openclaw/wacli) (0.26 or later,
`brew install openclaw/tap/wacli`), an unofficial whatsmeow client. WhatsApp
may limit or ban an account it finds using one; the person accepted that risk
([decision](decisions/whatsapp-tools-plugin.md)).

## Shape

| Piece                                                                          | Home                                                                                                   | Reader             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------ |
| Tools, approval card, skills, sync service, mirror                             | the package, installed at `~/.hermes/plugins/whatsapp-tools`                                           | Assistant, launchd |
| The pinned release                                                             | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people             |
| Refusal where no person can answer, bypass and unpacked guards, progress lines | `plugins/guards/whatsapp-tools-guard`                                                                  | Assistant          |
| Settings (toolsets, download and send folders, required guard, card language)  | `plugins.entries.whatsapp-tools.settings` in the Assistant's config                                    | Assistant          |
| How the tools are used                                                         | the package's skills, `whatsapp-tools:<toolset>`                                                       | Assistant          |
| When the Assistant uses it in Chat                                             | the Chat reference `whatsapp.md`                                                                       | Assistant          |
| OpenCode                                                                       | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode           |

One implementation serves both harnesses: the Hermes plugin spawns Node on the
package's built `dist/cli.js`, and the OpenCode plugin uses the same account
state. The package never uses `~/.wacli`; each account pairs its own linked
device (a phone takes at most four). A label such as
`default` or `work` holds one account under
`~/.local/state/whatsapp-tools/<label>/` (mode 0700): `wacli/` (session keys,
mirror and media), `service.sock`, `outbox/`, `service.lock` and `service.json`;
grants live under `~/.local/state/whatsapp-tools/grants` (unused while `grants`
stays off). One sync service per label
(`io.github.craft-agent.whatsapp-tools.<label>`, launcher in
`~/Library/Application Support/io.github.craft-agent.whatsapp-tools/whatsapp-tools-sync-<label>`,
log `~/Library/Logs/io.github.craft-agent.whatsapp-tools/<label>.log`) keeps the
mirror for both harnesses. Every write and a number check
(`whatsapp_contact_read` method `check`) go through it; reads work without it.
Both harnesses pin the same release: a test holds `external-plugins.json` and
`opencode.jsonc` to one version.

## Toolsets

The Assistant has `account`, `chats`, `contacts`, `history`, `sends`, `files`
and `actions` ([decision](decisions/whatsapp-tools-plugin.md)): reads
(`whatsapp_account_read`, `whatsapp_chat_read` with `list`, `view`, `search` and
`around`, and `whatsapp_contact_read` with `search` and `check`), mirror
backfill (`whatsapp_history_backfill`), files (`whatsapp_file_save`,
`whatsapp_file_send`), sends (`whatsapp_message_send`) and actions
(`whatsapp_chat_archive`, `whatsapp_chat_mark`, `whatsapp_chat_mute`,
`whatsapp_chat_pin`, `whatsapp_message_delete`, `whatsapp_message_edit`,
`whatsapp_message_react`). `grants` (`whatsapp_grant_read`,
`whatsapp_grant_create`, `whatsapp_grant_revoke`) stays off and `unattended`
unset: the package has no send mandates and no grant is made, so writes need a
person who can answer the card. OpenCode keeps the
upstream defaults: `account`, `chats`, `contacts`, `history` and `sends`.

`files` saves into `~/Workspaces/.inbox/whatsapp/<label>/<chat>/<message id>/`
(`download_dir` is `~/Workspaces/.inbox/whatsapp`) and sends only from
`~/Workspaces` (the working directory) and the folders `send_dirs` names, so a
received file can be sent on. Archives are unpacked into `<name>.unpacked/`
beside them, the folder name the shared unpacked guard keys on. Hermes gives
calls 150 s, and 330 s to `whatsapp_history_backfill`, `whatsapp_file_save` and
`whatsapp_file_send`; a file send takes at most 280 s, under the Assistant's
960 s tool deadline.

Chats the Assistant must neither see nor reach are listed in the private
config's `exclude_chats` setting (quoted JIDs), never here: every tool hides
them from lists and searches and refuses a call naming one before it is
approved. OpenCode sets none; the person sees every chat there.

`require_plugins` names `whatsapp-tools-guard`: while Hermes has not loaded the
guard, the package refuses every write before it is approved, so a guard that
fails to load stops the writes rather than leaving them unguarded. The profile
validator refuses a config that enables the package without naming the guard
there ([decision](decisions/whatsapp-tools-plugin.md)).

Keep every `WHATSAPP_TOOLS_*` environment variable unset. The Hermes adapter
emits no flag for a `false` or empty setting, so an environment variable would
override the config rather than being cancelled by it.

## Approval

Every write is held by the package's own `pre_tool_call` card, which pins what
it showed into the call and fails the call as `stale` if what it showed changed
since. An "always" or "session" answer covers the tool and its chat, not the
exact request: a write the user wants asked again is answered "once". There are
no send mandates and no grants; writes need a person who can answer the card.

The guard (`whatsapp-tools-guard`) adds, for every `whatsapp_*` tool:

- **No card where no person can answer.** Every tool not explicitly named as a
  read (`whatsapp_account_read`, `whatsapp_chat_read`, `whatsapp_contact_read`,
  `whatsapp_grant_read`) is refused under YOLO, `approvals.mode: off`, cron, a
  single query and the unattended platforms (`plugins/_shared/human_gate.py`).
  A new tool fails closed as a write. A block from any plugin beats an approve,
  so the package's card is never drawn there.
- **No inbound A2A.** Every `whatsapp_*` call, reads included, is refused for
  an inbound A2A request.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run `whatsapp-tools-cli`, `whatsapp-tools` or `wacli`, or name the
  package's state, plugin directory, launch agents, launchers, logs, a
  `WHATSAPP_TOOLS_` or `WACLI_` variable, `~/.wacli` or WhatsApp Desktop's
  data; paths are also matched by their real path and against the terminal's
  working directory
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)). The
  download folder (`~/Workspaces/.inbox/whatsapp`), `whatsapp://` links and
  `open -b net.whatsapp.WhatsApp` stay allowed.
- **Never run what was received**: the shared `unpacked_guard`.
- **Progress lines** that name the operation only, never a message, a search or
  a path.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/whatsapp-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. The runtime clones the release
commit (which carries the built `dist/`), verifies it and records the pin in
`~/.hermes/plugins/.install-metadata.json`; `--force` accepts the security scan's
caution on the bundled `dist/cli.js`. Never install it by hand at another
commit or link it from a checkout.

The package's command line is the installed copy,
`node ~/.hermes/plugins/whatsapp-tools/dist/cli.js` (written `whatsapp-tools-cli`
below); the sync service records that path and the Node binary, and a re-pin
replaces the directory in place. Its commands are
`pair [--account <label>] [--phone <n>] [--full-history [--history-days <n>]]`,
`sync`, `service install|uninstall|status [--account <label>]` and
`remove --account <label>`.

A new release, or after updating Node: change `version` and `commit` in
`external-plugins.json` and the npm version in `opencode.jsonc` together, run
`scripts/external-plugins.py install`, then re-run
`whatsapp-tools-cli service install --account <label>` for each paired label,
restart the gateway and `opencode service restart`.

## Setup

1. Install the plugin (`scripts/external-plugins.py install`), `wacli` (>= 0.26,
   `brew install openclaw/tap/wacli`) and its Node runtime; check that the phone
   has a free linked-device slot (four at most; the package never uses
   `~/.wacli`).
2. Pair each account label: `whatsapp-tools-cli pair --account <label>` (by QR,
   or add `--phone <n>` for a pairing code and
   `--full-history [--history-days <n>]` when older history is needed), then
   `whatsapp-tools-cli service install --account <label>`.
3. Enable `whatsapp-tools` and `whatsapp-tools-guard` in the Assistant's private
   `plugins.enabled` (the profile validator refuses the first without the
   second, and without the guard in `require_plugins`), with
   `whatsapp-tools-account`, `-chats`, `-contacts`, `-history`, `-sends`,
   `-files` and `-actions` in `toolsets` and the `cli`, `telegram` and `discord`
   lists of `platform_toolsets`, never `a2a`.
4. Restart the gateway; `whatsapp-tools-cli service status --account <label>`
   checks the service, and the Assistant's `whatsapp_account_read` the account.
