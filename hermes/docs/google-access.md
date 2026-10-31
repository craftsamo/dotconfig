# Google access

The Assistant's access to the user's own Google account — Sheets, Gmail and
Drive — and to the `gcloud` CLI, with every change held for the user's
approval. Read it when changing the plugin's engine, its approval rules or its
account setup. Common rules: [access-common.md](access-common.md). Part of the
Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                    | Home                                                                             | Reader    |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | --------- |
| Engine, approval rule, bypass guard, setup CLI                                                                           | `plugins/google-access/access.py`                                                | all       |
| `google_sheets`, `google_gmail`, `google_drive`, `gcloud` tools and the `pre_tool_call` hook (toolset `google_access`)   | `plugins/google-access/__init__.py`                                              | Assistant |
| Setup launcher                                                                                                           | `../bin/gaccess` (runs on `hermes-python`)                                       | people    |
| How the Assistant works a sheet: reads, guarded writes, approvals, formatting, checking the look, recovery, sheet design | the `google-access:sheets` plugin skill (`plugins/google-access/skills/sheets/`) | Assistant |
| When the Assistant uses the tools in Chat, and Gmail, Drive and gcloud                                                   | the Assistant's private Chat reference `google.md`                               | Assistant |

The engine uses the Google client libraries of Hermes' own runtime (the
`google` extra `setup.sh` installs) and the `gcloud` binary on `PATH`. The
upstream `google-workspace` skill is disabled for the Assistant: it asks for
every Workspace scope at once and keeps one unscoped token.

## Account, scopes and state

One Google account per profile, kept outside every repository:

| State                | Home                                                                             | Content                                                                                                                             |
| -------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| OAuth token          | Keychain item `GOOGLE_OAUTH_<PROFILE>` (project `hermes`, scope `google-access`) | refresh token, client id and secret, granted scopes: `spreadsheets`, `gmail.readonly`, `gmail.send`, `drive.readonly`, `drive.file` |
| `gcloud/`            | `~/.hermes/profiles/<profile>/google-access/`                                    | Hermes' own gcloud configuration (`CLOUDSDK_CONFIG`)                                                                                |
| `token.generation`   | the same directory                                                               | no secret: a random mark rewritten each time the token is stored                                                                    |
| age secret key       | Keychain item `GOOGLE_ACCESS_AGE_IDENTITY` (same project and scope)              | the key sensitive files are encrypted to on Drive; one for every profile, kind `AGE IDENTITY`, stored `--no-env`                    |
| `age-recipients.txt` | `~/.hermes/plugin-data/google-access/`                                           | no secret: the public keys those files are encrypted to                                                                             |

The token sits in a Keychain scope no Hermes profile receives
([secret scoping](access-common.md#secret-scoping)); the engine reads it with
the `secret` CLI when a profile's first call needs it and keeps access tokens
only in memory. Values reach the CLI through stdin, never argv. Once the
Keychain has held the token (a generation mark exists), an item that reads as
missing is reported as unreadable, never replaced by an old file. gcloud's own
login stays a file: `credentials.db` belongs to gcloud.

Token handling is serialized and read back. Refreshes run one at a time, and a
refresh token Google rotates is stored only over the one it was refreshed from.
Keychain read-modify-writes are serialized by a lock file, and an item that
exists but cannot be read (a locked keychain) stops them instead of being
replaced. Every store is read back before it counts. A process holding
credentials from an older generation mark, or a cached token Google refuses or
that lacks a scope, reads the Keychain again, so a new `gaccess auth` or
`revoke` reaches the running gateway without a restart. `revoke` fails unless
the item is confirmed gone.

Drive downloads and saved Gmail attachments go to `google_access.download_dir`,
never inside the state directory, which the guard below keeps out of reach.
Downloads create their file name exclusively, never overwriting and never
writing through a symlink at that name. An attachment is named by the part
`get` lists it under, never by Gmail's attachment id, which changes on every
fetch.

The scopes are the whole capability: Gmail can be searched, read (attachments
saved too) and sent from, never relabelled or deleted; Drive can be searched
and downloaded, and receives uploads, but no existing file is changed, shared or deleted (`drive.file` only
covers files this tool created, so an upload's `parent` must be such a folder
or it fails). gcloud runs with its own login, so Hermes never reads or switches
the user's `~/.config/gcloud`; there is no default project and every
project-scoped call names one.

## Sensitive files

A Drive upload takes only a file under the root of the
[Workspaces layout](workspace-layout.md), resolved through links: outside it
nothing says whether the file is sensitive, and a layout that cannot be read
uploads nothing. A file in an area the layout marks `sensitive` goes up
encrypted with [age](https://age-encryption.org) to every public key in
`age-recipients.txt`; the plugin keeps no list of area names. Area names match
without case, as macOS folders do, so `personal/` is the `Personal` area.

- The encrypted copy is made in a private temporary folder and removed once
  sent. Its Drive name ends in `.age` (a given `name` gets it too) and its
  content type is `application/octet-stream`, so neither says what the file
  is; the name itself is not hidden.
- No caller can turn encryption off. When no key is set up or `age` is
  missing, the upload is refused before its card.
- An upload reads only the public keys. The secret key is one Keychain item
  for every profile, of a kind the web3 wallet never reads, and stored
  `--no-env`, so `secret env` never puts it into an environment.
- Any of the keys opens a file: `age -d -i <key file> <name>.age`. The secret
  key `gaccess encryption init` shows once is the copy to keep outside this
  Mac; `add-recipient` adds another public key, such as a backup key kept
  elsewhere, for uploads from then on.
- Other ways out are not covered: a `gcloud storage cp` of a sensitive file
  still goes up as it is, on its own card.

Why age, the Keychain and these names: [decision](decisions/drive-upload-encryption.md).

## Approval

The hook decides before a tool runs; the rule is `approval_request` in
`access.py`. The request goes through Hermes' own gate
([approval gate](access-common.md#approval-gate)). Gmail, Drive and gcloud
cards have the [shared shape](access-common.md#card-shape): `Gmail · Send an
email` with ⚠️ (delivered at once, it cannot be unsent), the recipients, the
subject and the body under its own heading, cut with the rest counted;
`Google Drive · Upload a file` with ✅ into My Drive or ⚠️ into a folder that
may be shared, and for a sensitive file the `.age` name and an `Encrypted`
line with the number of keys; `gcloud · Run a command` with 🚨 and the full command, which is
never cut — a command too long for the card is refused. A card whose facts do
not fit (too many recipients) is refused too.

- **Changes ask first**: Sheets `update` / `batch_update` / `append` / `clear` /
  `create` / `add_sheet` / `layout` / `data` / `chart` / `pivot` / `protect` /
  `comment`, Gmail `send`, Drive `upload`, and every gcloud command that is not
  a read. The gate and the engine share one check, so no variant is read
  differently by each.
- **A gcloud read** is a command path that resolves, in the installed SDK's own
  command tree (`data/cli/gcloud_completions.py`), to a command — not a group —
  named by a read verb, and that hands out no credential
  (`authorization-code`, `print-*-token`, `get-credentials` ask). A path that
  does not resolve is rejected, so a positional cannot pose as the command
  (`compute instances create list`); without the tree every command asks.
- **Spreadsheet edits are approved per spreadsheet.** `update`, `batch_update`,
  `append`, `add_sheet`, `layout`, `chart` and `pivot` share one allowlist key
  per spreadsheet id, so "session" on the first card lets the rest of that
  spreadsheet's edits run for the session and "always" for good; another
  spreadsheet asks again. The spreadsheet's version history undoes them.
  `clear` and `create` keep a key per exact call, like every other change. So
  does every `data`, `protect` and `comment` call, a `layout` call changing
  `spreadsheet_settings` (the locale and time zone re-read every date and number
  in the file), a `layout` call holding any op that deletes, moves or replaces
  data, or picks a rule or view by its number or name to replace or drop it
  (`LAYOUT_DESTRUCTIVE`, `_destructive`), and a `chart` or `pivot` call that
  deletes one (`OBJECT_DESTRUCTIVE`) or writes a pivot table at a cell, which
  overwrites what it fills — so a grant for formatting never covers dropping
  rows.
- **Spreadsheet cards** keep a shape of their own, one fact per line: the
  spreadsheet title, the tab, then each cell as
  `K3257 > <column header>: <value>`. A whole tab whose name cannot be
  confirmed, or a named range, shows positions relative to the range instead
  of guessing addresses. The card fits Telegram's budget;
  the title gives way first and the remaining cells are counted. The title and
  header lookup waits only briefly (the hook runs before Hermes checks a grant,
  so it must not hold up approved edits) and falls back to ids and column
  letters. Many rows go in one `batch_update` so one card covers them.
- **Layout** is one `spreadsheets.batchUpdate` per call, so its ops land
  together or not at all. Ops come from a fixed vocabulary (`LAYOUT_OPS`),
  never raw API requests, so the gate can word and classify every one. Its card
  reads one line per op, counting the rest as `(+N more changes)`.
  `get_format` reads closed blocks back without approval.
- **Data** is the op action for changes that move or rewrite contents
  (`DATA_OPS`). It shares layout's machinery but every call asks, and its card
  names the area each op overwrites.
- **Protected ranges** (`protect`) always ask, and the card names each editor in
  full, never clipped: a call whose card would exceed the budget, or whose
  address Hermes' approval prompt would mask as a secret
  (`redact_sensitive_text`), is refused rather than shown partly. Turning a
  warning-only protection into a blocking one needs an editor list, since
  without one Google opens it to every file editor.
- **Comments** (`comment`) always ask, because a comment reaches other people
  (an assignee or a mention is emailed) and version history keeps no comments;
  the card names whoever is emailed, and a card Hermes would mask is refused.
  The result is `ok: false` unless `commentUpdateState` reads `ALL_SAVED`.
- **Snapshots** are a read (no approval): `snapshot` exports a tab, or a closed
  block of it, through the `docs.google.com/…/export?format=pdf` URL with the
  profile's token (not a documented API) and renders the first pages to PNG in
  the download folder, so the look can be checked with vision instead of a
  browser.
- **Row guards.** Writes by row number can land on the wrong row when another
  writer inserts, deletes or sorts rows. `update`, `batch_update`, `clear`,
  `layout` and `data` take `expect` — single cells with the value each must
  display. Right before writing, after the approval, the engine reads them in
  one call and writes nothing unless every one still matches as displayed text
  (so `2535` does not match `2,535`); a failed read also writes nothing.
  Sheets has no conditional write, so a change in the moment between the read
  and the write is not caught; `expect` is optional, and the tool description
  asks for it on every write by row number.
- "Always" persists as `plugin_rule:<key>` in the profile's `command_allowlist`;
  remove the entry there to revoke it.
- Calls the tool would reject anyway are blocked without asking: gcloud `auth`
  (except `auth list`), `config` (except reads), `init`, `components`, and the
  flags `--account`, `--configuration`, `--project` (use the parameter),
  `--flags-file`, `--impersonate-service-account`, `--log-http`; a Drive upload
  of a credential file, of a file outside the Workspaces root, or of a
  sensitive file with no key set up.

## Where a write may run

Every call that would get a card is refused first wherever no person can
answer it ([approval gate](access-common.md#approval-gate)). The check builds
the card without any Google request, only to learn whether the call changes
something, so reads and read-only gcloud commands are unaffected.

## Ways around the tools

The same hook blocks terminal commands that run `gcloud`, `gsutil`, `bq` or
`gaccess`, and terminal or file-tool calls whose command, working directory or
path names the upstream Workspace scripts, `CLOUDSDK_*`, `~/.config/gcloud`,
this plugin's state directory (only the plugin source under `plugins/`
excepted), its Keychain items or scope, the text of an age secret key
(`AGE-SECRET-KEY-`), or a whole-Keychain read (`dump-keychain`,
`secret export`). Patterns: `CLIS` (read by command
position, with `_CLI` for a line that cannot be read that way) and `_PATHS` in
`plugins/google-access/access.py`. A project's own tooling (`nps setup.google`,
a deploy script) may still run, and the gcloud it calls uses the user's own
`~/.config/gcloud` login, not this tool's
([project tooling](access-common.md#bypass-guard-ways-around-the-tool)). Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).
Once per account, in a terminal:

1. A Google Cloud project with the Gmail, Google Sheets and Google Drive APIs
   enabled; an OAuth consent screen (External, published to **In production**:
   in Testing, refresh tokens expire after 7 days; the unverified-app warning is
   expected for personal use); a **Desktop app** OAuth client, downloaded as
   JSON.
2. `gaccess auth ~/Downloads/client_secret_….json` — consent in the browser;
   reports scopes left unchecked and stores the token in the Keychain. The
   client JSON is not kept (the stored token carries the client id and secret).
3. `gaccess gcloud-login` — `gcloud auth login` into the profile's
   configuration.
4. `gaccess encryption init` — makes the age key for
   [sensitive files](#sensitive-files) (once per machine, not per profile):
   the secret key goes into the Keychain and is shown once; keep that copy
   outside this Mac (a password manager). A second run changes nothing but a
   lost public key. Optionally `gaccess encryption add-recipient age1… --label
…` adds another public key.
5. `gaccess check`.

`gaccess encryption restore` puts a kept secret key back into the Keychain (a
new Mac, a lost Keychain), never over another one: files already uploaded can
only be opened with the key they were encrypted to.
`gaccess revoke` revokes the Google token and removes it from the Keychain.
`--profile NAME` sets up another profile, which also needs the plugin's
`PROFILES` and its own `plugins.enabled` and `platform_toolsets` entries.
