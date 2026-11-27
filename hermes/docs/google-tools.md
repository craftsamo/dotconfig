# Google tools

The Assistant's access to the user's own Google account: spreadsheets, Gmail,
Drive files and their comments, and Cloud Run services and jobs, through an
OAuth client the user created. Reads run unasked; every change waits for the
user's answer on an approval card. It runs on the third-party package
[craft-agent/google-tools](https://github.com/craft-agent/google-tools), the
same release the person's OpenCode loads, and a dotconfig guard adds what this
setup requires of every access plugin. Why the package and what was given up
for it: [decision](decisions/google-tools-plugin.md). Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                   | Home                                                                                                   | Reader    |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------- |
| Tools, approval card, skills                                                            | the package, installed at `~/.hermes/plugins/google-tools`                                             | Assistant |
| The pinned release                                                                      | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people    |
| Refusal where no person can answer, sensitive-file checks, bypass guard, progress lines | `plugins/guards/google-tools-guard`                                                                    | Assistant |
| Settings (toolsets, folders, encryption, guard)                                         | `plugins.entries.google-tools.settings` in the Assistant's config                                      | Assistant |
| How the tools are used                                                                  | the package's skills, `google-tools:<toolset>`                                                         | Assistant |
| When the Assistant uses Google in Chat                                                  | the Assistant's private Chat reference `google.md`                                                     | Assistant |
| Apps Script in the browser                                                              | the Assistant's technic `sheets-apps-script`                                                           | Assistant |
| OpenCode                                                                                | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode  |

One implementation serves both harnesses: the Hermes plugin spawns Node on the
package's built `dist/cli.js`, which calls Google's APIs itself. Only the
Assistant has the tools; no other profile holds a Google account.

## Toolsets

`account`, `sheets`, `gmail`, `drive`, `comments` and `run` (Cloud Run) are on.
`grants` stays off: no job writes to Google unattended. The toolsets sit in
the Assistant's `cli`, `telegram` and `discord` lists, never `a2a`. What each
tool does, and the scopes each toolset asks for, is the package's README. Two
limits to know here: Drive writes reach only files the tools created or opened
(`drive.file`) and never change sharing, and Cloud Run is the only Google
Cloud work the Assistant does, through `google_run_*`.

Keep every `GOOGLE_TOOLS_*` environment variable unset: the Hermes adapter
emits no flag for a `false` or empty setting, so a variable would override the
config rather than being cancelled by it.

## Account and state

The user logs in with their own Desktop OAuth client (the package ships none).
The client's project must have the Cloud Run Admin API enabled, and its
publishing status must be **In production**: a client left in Testing gets
refresh tokens that die after 7 days. Login, adding a toolset to a label and
removal are the user's own commands (never the Assistant's; the guard blocks
the CLI).

The refresh token lives in the package's state directory,
`~/.local/state/google-tools/accounts/<label>/credentials.json` (mode 600),
shared by Hermes and OpenCode. It is not in the Keychain and not in the
gateway's process environment: the package reads its own file, so no profile's
secret scope or process env carries it. The guard keeps the terminal and file
tools out of that directory.

## Settings

In `plugins.entries.google-tools.settings` of the Assistant (the example is
`profiles/assistant/config.example.yaml`):

| Setting           | Value                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| `toolsets`        | the six above                                                         |
| `download_dir`    | `~/Workspaces/.inbox/google`                                          |
| `upload_dirs`     | `~/Workspaces`, the only place files are sent from                    |
| `encrypt_dirs`    | the sensitive areas, set in the private config (empty in the example) |
| `age_recipients`  | the age public keys, private config (empty in the example)            |
| `require_plugins` | `google-tools-guard`                                                  |
| `language`        | `ja`                                                                  |

`plugins.enabled` and `platform_toolsets` are in the private config. While
Hermes has not loaded the guard, the package refuses every write before it is
approved; the profile validator refuses a config that enables the package
without the guard or without naming it in `require_plugins`.

The package reads its settings once, when the gateway loads it, so a change
takes effect only after a gateway restart. The guard judges a sensitive upload
by `encrypt_dirs` and `age_recipients` as they were at that load too, and
refuses one the current config covers but the loaded one does not, asking for
the restart.

## Approval and standing answers

Every write is held by the package's own `pre_tool_call` card, drawn from what
the call will do and fitted to the surface; what the card showed is pinned into
the call. A "session" or "always" answer covers that tool on the same target (a
tab, a recipient, a folder); a call whose target the package cannot tell asks
once, and a Gmail send asks every time. There are no grants: a write needs a
person who can answer the card. `plugins/_shared/approval_tier.py` holds no
rule for these tools.

## Sensitive files and encryption

The package encrypts an upload with age only when the file lies under
`encrypt_dirs`, to the keys in `age_recipients`, named `.age`; it never
encrypts a mail attachment and never decrypts. Hermes holds no secret key and
never decrypts: the user runs `age -d` with the identity they keep. Which
Workspaces areas are sensitive is the layout's
([workspace-layout.md](workspace-layout.md)); `encrypt_dirs` must list them.
The guard refuses a `google_drive_upload` of a file in a sensitive area unless
`encrypt_dirs` covers it and `age_recipients` names a key, and any Gmail
attachment from a sensitive area. Files are judged by real path, case and
Unicode form folded; a layout or configuration that cannot be read refuses the
call. Other ways out (a terminal `cp`, a file the Assistant reads and pastes)
are not covered ([decision](decisions/drive-upload-encryption.md)).

## Guard

`google-tools-guard` adds, for every `google_*` tool:

- **No card where no person can answer.** Every tool not named as a read
  (`google_account_read`, `google_sheets_read`, `google_gmail_read`,
  `google_drive_read`, `google_comments_read`, `google_run_read`,
  `google_grant_read`) is refused under YOLO, `approvals.mode: off`, cron, a
  single query and the unattended platforms (`plugins/_shared/human_gate.py`),
  and for an inbound A2A request. A new tool fails closed as a write.
- **The sensitive-file checks** above.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run `google-tools-cli`, `gcloud`, `gsutil` or `bq` directly (a
  project's own scripts still run in their repository), name the package's
  state or install, a `GOOGLE_TOOLS_*` variable, an OAuth token's shape, a
  Keychain read, the user's own gcloud login, the age identity, or the
  runtime's upstream Google Workspace scripts and their token files; paths are
  matched by real path and by the terminal's working directory
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)).
- **Progress lines** that name the operation only.

## What the retired google-access plugin had that is gone

The in-house plugin it replaced is removed. Gone:

- The general `gcloud` tool and the gcloud mandates. Cloud Run goes through
  `google_run_*`; other Google Cloud work is the user's own or an OpenCode
  engineering task.
- `decrypt_to`. Hermes never decrypts.
- Drive writes beyond `drive.file`, and any sharing change.
- Apps Script through the tool: it stays a browser exception, now the technic
  `sheets-apps-script`.

New: Gmail drafts, labels and trash; Drive copy, move, rename, trash and
folders; comments as their own toolset; Cloud Run.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) installs the
commit `external-plugins.json` pins; `status` compares the installed commit
with the pin. Never install it by hand at another commit or link it from a
checkout.

A new release: change `version` and `commit` in `external-plugins.json` and the
npm version in `opencode.jsonc` together (a test keeps them equal), run
`scripts/external-plugins.py install`, restart the gateway and
`opencode service restart`.

## Setup

1. In the user's Google Cloud project, enable the Sheets, Gmail, Drive and
   Cloud Run Admin APIs; set the consent screen to **In production**; create
   a Desktop client and download its JSON.
2. Install the plugin (above) and its Node runtime.
3. Enable `google-tools` and `google-tools-guard` in the private
   `plugins.enabled` of the Assistant, with the `google-tools-*` toolsets in
   `toolsets` and the platform lists above; set `encrypt_dirs` and
   `age_recipients` in its private config.
4. The user logs in:
   `node ~/.hermes/plugins/google-tools/dist/cli.js login --account <label> --toolsets account,sheets,gmail,drive,comments,run --client <desktop-client.json>`.
5. Restart the gateway (`launchd/gateway-launchctl.sh restart`);
   `google_account_read` lists the label.

OpenCode reads the same state, so the one login serves both.
