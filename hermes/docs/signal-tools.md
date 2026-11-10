# Signal tools

The Assistant's access to the user's own Signal account: reading chats and
messages, checking a number, saving files someone sent, and sending text and
workspace files after the user answers the approval card. It runs on the
third-party package [craft-agent/signal-tools](https://github.com/craft-agent/signal-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin
of our own: [decision](decisions/signal-tools-plugin.md). Common rules:
[access-common.md](access-common.md). It is not the Signal messaging platform
(`gateway/platforms/signal.py`); nothing here lets people talk to Hermes over
Signal. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                          | Home                                                                                                   | Reader             |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------ |
| Tools, approval card, skills, sync service, mirror                             | the package, installed at `~/.hermes/plugins/signal-tools`                                             | Assistant, launchd |
| The pinned release                                                             | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people             |
| Refusal where no person can answer, bypass and unpacked guards, progress lines | `plugins/guards/signal-tools-guard`                                                                    | Assistant          |
| Settings (toolsets, download and send folders, card language)                  | `plugins.entries.signal-tools.settings` in the Assistant's config                                      | Assistant          |
| How the tools are used                                                         | the package's skills, `signal-tools:<toolset>` (`account`, `chats`, `contacts`, `sends`, `files`)      | Assistant          |
| When the Assistant uses it in Chat                                             | the Chat reference `signal.md`                                                                         | Assistant          |
| OpenCode                                                                       | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode           |

The package joins the account as a linked device through
[signal-cli](https://github.com/AsamK/signal-cli) (Homebrew), the standing of
Signal Desktop as an unofficial client
([risk acceptance](access-common.md#risk-acceptance)). One label, `default`,
holds one account; its state is `~/.local/state/signal-tools/default/`
(signal-cli's keys and files, the mirror `mirror.sqlite`, the daemon socket).
One sync service per label receives and keeps the mirror
(`io.github.craft-agent.signal-tools.default`); every read tool reads the
mirror only. Hermes and OpenCode share the device, the service and the mirror,
so both pin the same release: a test holds `external-plugins.json` and
`opencode.jsonc` to one version.

## Toolsets

The Assistant has `account`, `chats`, `contacts`, `sends` and `files`. The
`actions` toolset (edit, delete for everyone, react) stays off: those change
what others have already read. `files` saves into `~/Workspaces/.inbox/signal`
and sends only from `~/Workspaces` (the working directory) and the folders
`send_dirs` names, so a received file can be sent on. Archives are unpacked
into `<name>.unpacked/` beside them, the folder name the shared unpacked guard
keys on.

## Approval

Every write is held by the package's own `pre_tool_call` card: a headline,
then the facts (account, chat and its kind, members, the quoted message,
files with size and SHA-256), then the text, fitted to the surface the turn
runs on. What the card showed is pinned into the call, and the call fails as
`stale` if the chat, a file or the text changed since. An "always" or
"session" answer covers the tool and its chat, not the exact request: a write
the user wants asked again is answered "once". There are no send mandates for
Signal; a send always has a card.

The guard (`signal-tools-guard`) adds, for every `signal_*` tool:

- **No card where no person can answer.** A write (every `signal_*` tool but
  the three reads, so a tool added later is held too) is refused under YOLO,
  `approvals.mode: off`, cron, a single query and the unattended platforms
  (`plugins/_shared/human_gate.py`). A block from any plugin beats an approve,
  so the package's card is never drawn there.
- **No inbound A2A.** Every `signal_*` call, reads included, is refused for an
  inbound A2A request.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run `signal-cli`, `signal-tools-cli` or `signal-tools`, or name the
  state, the plugin's directory, the launch agents, their logs, a
  `SIGNAL_TOOLS_` variable, Signal Desktop's data or the old plugin's state;
  paths are also matched by their real path
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)).
- **Never run what was received**: the shared `unpacked_guard`.
- **Progress lines** that name the operation only (`send`, `search`), never a
  message, a search or a path.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/signal-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. The runtime clones the release
commit (which carries the built `dist/`), verifies it and records the pin in
`~/.hermes/plugins/.install-metadata.json`; `--force` accepts the security
scan's caution on the bundled `dist/cli.js`. Never install it by hand at
another commit or link it from a checkout.

The package's command line is the installed copy,
`node ~/.hermes/plugins/signal-tools/dist/cli.js` (written `signal-tools-cli`
below); the sync service records that path, and a re-pin replaces the
directory in place.

A new release: change `version` and `commit` in `external-plugins.json` and the
npm version in `opencode.jsonc` together, run `install`, then
`signal-tools-cli service install --account default`, restart the gateway and
`opencode service restart`.

## Setup

1. `brew install signal-cli` and Node 24 or later; the phone needs a free
   linked-device slot.
2. Install the plugin (above) and enable `signal-tools` and
   `signal-tools-guard` in the Assistant's `plugins.enabled` (the profile
   validator refuses the first without the second), with the toolsets in
   `toolsets` and the `cli`, `telegram` and `discord` lists of
   `platform_toolsets`, never `a2a` (`signal-tools-account`, `-chats`,
   `-contacts`, `-sends`, `-files`).
3. `signal-tools-cli link --account default`, scan the code on the phone,
   then `signal-tools-cli service install --account default`.
4. Restart the gateway.

Moving from the old `signal-access` plugin keeps its device and history:
stop its agent (`signal-access-launchctl.sh uninstall`), run
`scripts/signal-history-import.py` from the live checkout (it copies
signal-cli's data and the mirror into the `default` label; `--dry-run`
first), then install the service as in step 3 without linking. The old state
stays as it was, but it is a backup only until the new service receives or
sends anything: after that, going back means linking the device again, never
starting the old agent on its stale copy.
