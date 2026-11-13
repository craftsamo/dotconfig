# Telegram tools

The Assistant's access to the user's own Telegram account: reading chats and
messages, keeping selected supergroups and channels synced, saving received
files, and sending text and workspace files after the user answers the
approval card. It runs on the third-party package
[craft-agent/telegram-tools](https://github.com/craft-agent/telegram-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin
of our own: [decision](decisions/telegram-tools-plugin.md). Common rules:
[access-common.md](access-common.md). It is not the Assistant's Telegram bot
(the gateway's Telegram platform); nothing here changes how people talk to
Hermes through that bot. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                          | Home                                                                                                   | Reader             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------ |
| Tools, approval card, skills, sync service, mirror                             | the package, installed at `~/.hermes/plugins/telegram-tools`                                           | Assistant, launchd |
| The pinned release                                                             | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people             |
| Refusal where no person can answer, bypass and unpacked guards, progress lines | `plugins/guards/telegram-tools-guard`                                                                  | Assistant          |
| Settings (toolsets, download and send folders, card language)                  | `plugins.entries.telegram-tools.settings` in the Assistant's config                                    | Assistant          |
| How the tools are used                                                         | the package's skills, `telegram-tools:<toolset>` (`account`, `chats`, `sync`, `sends`, `files`)        | Assistant          |
| When the Assistant uses it in Chat                                             | the Chat reference `telegram.md`                                                                       | Assistant          |
| OpenCode                                                                       | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode           |

One implementation serves both harnesses: the Hermes plugin spawns Node on
the package's built `dist/cli.js`, and the OpenCode plugin uses the same
account state. A label such as `default` holds one account under
`~/.local/state/telegram-tools/<label>/`: `session.sqlite` holds the session
and auth key, `app.json` the app settings, `mirror.sqlite` the mirror,
`sync.sock` the sync socket, and `incoming/`, `outbox/` and `kept/` the files.
The state directory is mode 0700 and the session is owner-only. The sync
service (`io.github.craft-agent.telegram-tools`) keeps the mirror for both
harnesses. Both pin the same release: a test holds `external-plugins.json`
and `opencode.jsonc` to one version.

## Toolsets

The Assistant has `account`, `chats`, `sync`, `sends` and `files`. The
`actions` toolset (edit, delete, react, pin and mark read) stays off. OpenCode
keeps the upstream defaults: `account`, `chats`, `sync` and `sends`.
`files` saves into `~/Workspaces/.inbox/telegram` and sends only from
`~/Workspaces` (the working directory) and the folders `send_dirs` names, so
a received file can be sent on. Archives are unpacked into
`<name>.unpacked/` beside them, the folder name the shared unpacked guard
keys on.

`channels` and `keep_disappearing` are on for this deployment, by the person's
decision. The package's README cautions that Telegram API terms §3.3 cover
sponsored messages and §1.4 disappearing messages; the person accepted those
risks ([decision](decisions/telegram-tools-plugin.md)). Re-run `service install`
after changing either setting so the sync service uses the new values.

Chats the Assistant must neither see nor reach are listed in the private
config's `exclude_chats` setting (each id quoted), never here: every tool
leaves them out of lists and searches and refuses a call naming one before it
is approved. OpenCode sets none; the person sees every chat there.

`require_plugins` names `telegram-tools-guard`: while Hermes has not loaded
the guard, the package refuses every write before it is approved, so a guard
that fails to load stops the writes rather than leaving them unguarded. The
profile validator refuses a config that enables the package without naming
the guard there ([decision](decisions/telegram-tools-plugin.md)).

Keep every `TELEGRAM_TOOLS_*` environment variable unset. The Hermes adapter
emits no flag for a `false` or empty setting, so an environment variable would
override the config rather than being cancelled by it.

## Approval

Every write is held by the package's own `pre_tool_call` card: a headline,
then the facts (account, chat and its kind, quoted messages and files), then
the text, fitted to the surface the turn runs on. What the card showed is
pinned into the call, and the call fails as `stale` if the chat, a file or the
text changed since. An "always" or "session" answer covers the tool and its
chat, not the exact request: a write the user wants asked again is answered
"once". There are no Telegram send mandates; writes need a person who can
answer the card.

The guard (`telegram-tools-guard`) adds, for every `telegram_*` tool:

- **No card where no person can answer.** Every tool not explicitly named as
  a read is refused under YOLO, `approvals.mode: off`, cron, a single query
  and the unattended platforms (`plugins/_shared/human_gate.py`).
  `telegram_chat_mark_read` is a write despite its `_read` ending; a new tool
  is held too. A block from any plugin beats an approve, so the package's
  card is never drawn there.
- **No inbound A2A.** Every `telegram_*` call, reads included, is refused for
  an inbound A2A request.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run the package's CLI or name its state, plugin directory, launch
  agents, logs, a `TELEGRAM_TOOLS_` variable or the old plugin's state;
  paths are also matched by their real path
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)).
- **Never run what was received**: the shared `unpacked_guard`.
- **Progress lines** that name the operation only, never a message, a search
  or a path.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/telegram-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. The runtime clones the release
commit (which carries the built `dist/`), verifies it and records the pin in
`~/.hermes/plugins/.install-metadata.json`; `--force` accepts the security
scan's caution on the bundled `dist/cli.js`. Never install it by hand at
another commit or link it from a checkout.

The package's command line is the installed copy,
`node ~/.hermes/plugins/telegram-tools/dist/cli.js` (written
`telegram-tools-cli` below); the sync service records that path, and a re-pin
replaces the directory in place. Its account commands are `login` and
`logout`; `service install`, `service status` and `service uninstall` manage
the sync service.

A new release: change `version` and `commit` in `external-plugins.json` and
the npm version in `opencode.jsonc` together, run
`scripts/external-plugins.py install`, then
`telegram-tools-cli service install --account default --channels --keep-disappearing`,
restart the gateway and `opencode service restart`.

## Setup

1. Install the plugin (above) and its Node runtime.
2. `telegram-tools-cli login --account default`, scan the QR code in Telegram,
   then `telegram-tools-cli service install --account default --channels --keep-disappearing`.
3. Enable `telegram-tools` and `telegram-tools-guard` in the Assistant's
   private `plugins.enabled` (the profile validator refuses the first without
   the second, and without the guard in `require_plugins`), with
   `telegram-tools-account`, `-chats`, `-sync`, `-sends` and `-files` in
   `toolsets` and the `cli`, `telegram` and `discord` lists of
   `platform_toolsets`, never `a2a`.
4. Restart the gateway; `telegram-tools-cli service status --account default`
   checks the service, and the Assistant's `telegram_account_read` the account.
