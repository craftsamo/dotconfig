# Discord tools

The Assistant's access to the user's own Discord account: reading servers,
channels, DMs and threads, searching, the inbox of mentions and saved
messages, people and server info, keeping chosen servers and channels synced,
counting and exporting history, saving received files, sending text and
workspace files, editing and deleting the user's own messages, reactions,
pins and a server's roles, each write after the user answers the approval
card. It runs on the third-party package
[craft-agent/discord-tools](https://github.com/craft-agent/discord-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin
of our own: [decision](decisions/discord-tools-plugin.md). Common rules:
[access-common.md](access-common.md). It is not the Assistant's Discord bot
(the gateway's Discord platform); nothing here changes how people talk to
Hermes through that bot. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

The package automates a user account, which Discord's terms forbid; the
package's README warns the account can be closed for it, reads included. The
person accepted that risk ([decision](decisions/discord-tools-plugin.md)).

## Shape

| Piece                                                                          | Home                                                                                                   | Reader             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------ |
| Tools, approval card, skills, sync service, mirror                             | the package, installed at `~/.hermes/plugins/discord-tools`                                            | Assistant, launchd |
| The pinned release                                                             | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people             |
| Refusal where no person can answer, bypass and unpacked guards, progress lines | `plugins/guards/discord-tools-guard`                                                                   | Assistant          |
| Settings (toolsets, download and send folders, card language)                  | `plugins.entries.discord-tools.settings` in the Assistant's config                                     | Assistant          |
| How the tools are used                                                         | the package's skills, `discord-tools:<toolset>`                                                        | Assistant          |
| When the Assistant uses it in Chat                                             | the Chat reference `discord.md`                                                                        | Assistant          |
| OpenCode                                                                       | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode           |

One implementation serves both harnesses: the Hermes plugin spawns Node on
the package's built `dist/cli.js`, and the OpenCode plugin uses the same
account state. A label such as `default` holds one account under
`~/.local/state/discord-tools/<label>/`: `token` holds the user token,
`mirror.sqlite` the mirror, `service.json` the sync service's record, and
`incoming/`, `outgoing/` and `transfers/` the files on their way. The state
directory is mode 0700 and the token file 0600. The sync service
(`io.github.craft-agent.discord-tools`) runs every five minutes and keeps the
mirror for both harnesses: DMs and group DMs always, servers and channels
only as the sync list names them, threads and forum posts never (they are
read live). It sends nothing of its own: no presence, typing or read marks.
Both harnesses pin the same release: a test holds `external-plugins.json`
and `opencode.jsonc` to one version.

## Toolsets

The Assistant has `account`, `sync`, `chats`, `search`, `inbox`, `people`,
`sends`, `history`, `files`, `actions` and `roles`: everything the retired
plugin could do. `threads` (creating threads and forum posts, joining and
leaving) and `grants` stay off. OpenCode keeps the upstream defaults:
`account`, `sync`, `chats`, `search`, `inbox`, `people` and `sends`.
`files` saves into `~/Workspaces/.inbox/discord/<channel>-<message>/`,
`history` exports into `~/Workspaces/.inbox/discord/exports/`, and sends go
only from `~/Workspaces`, so a received file can be sent on. Archives are
unpacked into `<name>.unpacked/` beside them, the folder name the shared
unpacked guard keys on.

`require_plugins` names `discord-tools-guard`: while Hermes has not loaded
the guard, the package refuses every write before it is approved, so a guard
that fails to load stops the writes rather than leaving them unguarded. The
profile validator refuses a config that enables the package without naming
the guard there ([decision](decisions/discord-tools-plugin.md)).

Keep every `DISCORD_TOOLS_*` environment variable unset, the token variable
`DISCORD_TOOLS_TOKEN_<LABEL>` included. The Hermes adapter emits no flag for a
`false` or empty setting, so a variable would override the config rather than
being cancelled by it, and a token variable in a layer `profile-secrets.sh`
emits would reach the Assistant's whole process.

## Approval

Every write is held by the package's own `pre_tool_call` card: a headline,
then the facts (account, chat, the message or role it touches, files), then
the text, fitted to the surface the turn runs on. What the card showed is
pinned into the call, and the call fails as `stale` if the chat, a file, a
message or a role changed since. An "always" or "session" answer covers the
tool and its target, not the exact request: a write the user wants asked
again is answered "once". Role changes are administrative: the package asks
for each one, whatever was answered before. There are no Discord send
mandates and no grants; writes need a person who can answer the card.

The guard (`discord-tools-guard`) adds, for every `discord_*` tool:

- **No card where no person can answer.** Every tool not explicitly named as
  a read is refused under YOLO, `approvals.mode: off`, cron, a single query
  and the unattended platforms (`plugins/_shared/human_gate.py`).
  `discord_read_mark` is a write; a new tool is held too. A block from any
  plugin beats an approve, so the package's card is never drawn there.
- **No inbound A2A.** Every `discord_*` call, reads included, is refused for
  an inbound A2A request.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run the package's CLI or name its state, plugin directory, launch
  agents, logs, a `DISCORD_TOOLS_` variable, the Discord app's data (it holds
  the account's token) or the retired plugin's state and token; paths are
  also matched by their real path
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)). The
  download folder and the app's `discord://` links, which screen-listen opens,
  stay allowed.
- **Never run what was received**: the shared `unpacked_guard`.
- **Progress lines** that name the operation only, never a message, a search
  or a path.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/discord-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. The runtime clones the release
commit (which carries the built `dist/`), verifies it and records the pin in
`~/.hermes/plugins/.install-metadata.json`; `--force` accepts the security
scan's caution on the bundled `dist/cli.js`. Never install it by hand at
another commit or link it from a checkout.

The package's command line is the installed copy,
`node ~/.hermes/plugins/discord-tools/dist/cli.js` (written
`discord-tools-cli` below); the sync service records that path, and a re-pin
replaces the directory in place. Its account commands are `login` and
`remove`; `service install`, `service status` and `service uninstall` manage
the sync service.

A new release: change `version` and `commit` in `external-plugins.json` and
the npm version in `opencode.jsonc` together, run
`scripts/external-plugins.py install`, then
`discord-tools-cli service install --account default`, restart the gateway
and `opencode service restart`.

## Setup

1. Install the plugin (above) and its Node runtime.
2. Pipe the user token into `discord-tools-cli login --account default` from
   the Keychain item the retired plugin used (`DISCORD_USER_TOKEN`, project
   `hermes`, scope `discord-user`), never as an argument; the package checks
   it with Discord and keeps it in its token file. Then
   `discord-tools-cli service install --account default`.
3. Add the servers and channels to follow with `discord_sync_add` (in the
   Assistant or OpenCode); DMs need no entry. History older than the first
   sync comes back with `discord_chat_read` method `backfill`: the retired
   plugin's mirror is not imported.
4. Enable `discord-tools` and `discord-tools-guard` in the Assistant's
   private `plugins.enabled` (the profile validator refuses the first without
   the second, and without the guard in `require_plugins`), with
   `discord-tools-account`, `-sync`, `-chats`, `-search`, `-inbox`,
   `-people`, `-sends`, `-history`, `-files`, `-actions` and `-roles` in
   `toolsets` and the `cli`, `telegram` and `discord` lists of
   `platform_toolsets`, never `a2a`.
5. Restart the gateway; `discord-tools-cli service status --account default`
   checks the service, and the Assistant's `discord_account_read` the account.

When Discord rejects the token (after a password change, say), the service
pauses the label: log in again with a new token, then run `service install`
again.
