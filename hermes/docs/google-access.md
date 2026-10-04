# Google access

The Assistant's access to the user's own Google account — Sheets, Gmail and
Drive — and to the `gcloud` CLI, with every change held for the user's
approval. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece | Home | Reader |
|---|---|---|
| Engine, approval rule, bypass guard, setup CLI | `plugins/google-access/access.py` | all |
| `google_sheets`, `google_gmail`, `google_drive`, `gcloud` tools and the `pre_tool_call` hook (toolset `google_access`) | `plugins/google-access/__init__.py` | Assistant |
| Setup launcher | `../bin/gaccess` (runs on `hermes-python`) | people |

The engine uses the Google client libraries of Hermes' own runtime (the
`google` extra `setup.sh` installs) and the `gcloud` binary on `PATH`. The
upstream `google-workspace` skill is disabled for the Assistant: it asks for
every Workspace scope at once and keeps one unscoped token.

## Account, scopes and state

One Google account per profile. State lives in
`~/.hermes/profiles/<profile>/google-access/`, outside every repository:

| State | Content |
|---|---|
| `token.json` (0600) | OAuth token for `spreadsheets`, `gmail.readonly`, `gmail.send`, `drive.readonly`, `drive.file` |
| `gcloud/` | Hermes' own gcloud configuration (`CLOUDSDK_CONFIG`) |

Drive downloads go to `google_access.download_dir` from the profile's
`config.yaml` (the Assistant uses `~/Workspaces/.inbox/google`), else
`~/.hermes/profiles/<profile>/google-downloads/` — never inside the state
directory, which the guard below keeps out of reach.

The scopes are the whole capability: Gmail can be searched, read and sent
from, never relabelled or deleted; Drive can be searched and downloaded, and
receives uploads, but no existing file is changed, shared or deleted
(`drive.file` only covers files this tool created, so an upload's `parent`
must be such a folder or it fails). gcloud runs with its own login, so Hermes
never reads or switches the user's `~/.config/gcloud`; there is no default
project and every project-scoped call names one.

## Approval

The hook decides before a tool runs; the rule is `approval_request` in
`access.py`.

- **Changes ask first**: Sheets `update` / `batch_update` / `append` /
  `clear` / `create` / `add_sheet` / `layout`, Gmail `send`, Drive `upload`, and every
  gcloud command that is not a read. The action must be spelled exactly; the
  gate and the engine share one check, so no variant is read differently by
  each.
- **A gcloud read** is a command path that resolves, in the installed SDK's
  own command tree (`data/cli/gcloud_completions.py`), to a command — not a
  group — named by a read verb (`list`, `list-*`, `describe`, `get`,
  `get-iam-policy`, `read`, `ls`, `cat`, …), and that hands out no credential
  (`authorization-code`, `print-*-token`, `get-credentials` ask). A path that
  does not resolve is rejected, so a positional cannot pose as the command
  (`compute instances create list`); without the tree every command asks.
- The request goes through Hermes' own gate (`request_tool_approval`), the
  same as dangerous shell commands: `/approve` or `/deny` on Telegram, a prompt
  in the CLI. Silence, denial, a gate error, cron (`approvals.cron_mode: deny`)
  and contexts without a human all block. The card shows recipients and body,
  the upload, or the full gcloud command.
- **Spreadsheet edits are approved per spreadsheet.** `update`,
  `batch_update`, `append`, `add_sheet` and `layout` share one allowlist key per
  spreadsheet id, so "session" on the first card lets the rest of that
  spreadsheet's edits run for the session and "always" for good; another
  spreadsheet asks again. The spreadsheet's version history undoes them.
  `clear` and `create` keep a key per exact call, like every other change:
  "always" there only repeats that identical call. So does a `layout` call
  holding any op that deletes or moves data (`delete`, `move`, `merge`,
  `table_delete`, `conditional_delete`; `LAYOUT_DESTRUCTIVE`), so a grant
  for formatting never covers dropping rows.
- **Spreadsheet cards** are plain English, one fact per line —
  `SpreadSheet: <title>`, `Sheet: <tab>`, a blank line, then each cell as
  `K3257 > <column header>: <value>`, row 1 being the header. A whole tab whose
  name cannot be confirmed, or a named range, shows positions relative to the
  range (`R1C2`) instead of guessing addresses. The card fits 480 escaped
  UTF-16 units, Telegram's budget for a reason; the title gives way first and
  the remaining cells are counted. The title and header lookup waits at most
  three seconds (the hook runs before Hermes checks a grant, so it must not
  hold up approved edits), is cached for ten minutes (a failure for one), and
  falls back to ids and column letters. Telegram has no tables, and Hermes
  owns the rest of the card. Many rows go in one `batch_update` (up to 500
  ranges) so one card covers them.
- **Layout** is one `spreadsheets.batchUpdate` per call, so its ops land
  together or not at all. Ops come from a fixed vocabulary (`LAYOUT_OPS`:
  formatting, borders, sizes, inserting/deleting/moving rows and columns,
  merges, freezing, native tables, conditional formatting, input rules), never
  raw API requests, so the gate can word and classify every one. As
  `batch_update` takes scattered cells in one call, an op that applies the
  same change to scattered places takes `ranges` instead of `range` (at most
  `BATCH_LIMIT` ranges per call); `insert` and `move` keep one range, since
  each shifts what the next position would mean, and a multi-range `delete`
  runs bottom-up so its row numbers are the ones read before the call. Its card
  reads `SpreadSheet:`, `Sheet:` when every op is on one tab, the checks,
  then one line per op (`Width of columns B-D: 140px`, `Delete rows 4-5 with
  their contents`), counting the rest as `(+N more changes)`. Tabs resolve
  to sheet ids by name (a bare word is a tab, never a named range); tables by
  name or id. `table_update` keeps the columns it does not name, and
  `table_delete` removes the table with its contents (the API has no
  unconvert). `info` lists each tab's frozen counts, merges, tables and
  numbered conditional rules, which the update and delete ops refer to.
- **Row guards.** Writes by row number can land on the wrong row when another
  writer inserts, deletes or sorts rows. `update`, `batch_update`, `clear` and
  `layout` take `expect` — up to 200 single cells with the value each must display
  (typically the row's id column). Right before writing, after the approval,
  the engine reads them in one call and writes nothing unless every one still
  matches as displayed text (surrounding whitespace ignored, booleans as
  `TRUE`/`FALSE`, numbers as shown, so `2535` does not match `2,535`); a
  failed read also writes nothing, and the error names up to five mismatches.
  The card shows them as `Check: A2534 = …`, keeping the tab when it is not
  the one written.
  `expect` on any other action is refused. Sheets has no conditional write,
  so a change in the moment between the read and the write is not caught;
  `expect` is optional, and the tool description asks for it on every write
  by row number.
- "Always" persists as `plugin_rule:<key>` in the profile's `command_allowlist`;
  remove the entry there to revoke it.
- Calls the tool would reject anyway are blocked without asking: gcloud
  `auth` (except `auth list`), `config` (except reads), `init`, `components`,
  and the flags `--account`, `--configuration`, `--project` (use the parameter),
  `--flags-file`, `--impersonate-service-account`, `--log-http`; a Drive upload
  of a credential file.
- Inbound A2A requests never reach the account.

## Ways around the tools

The same hook blocks terminal commands that run `gcloud`, `gsutil`, `bq` or
`gaccess`, and terminal or file-tool calls whose command, working directory
or path names the upstream Workspace scripts, `CLOUDSDK_*`,
`~/.config/gcloud` or this plugin's state directory (only the plugin source
under `plugins/` excepted). It is a pattern match on the call's text, not a
sandbox: it stops ordinary use, not a determined script.

Token refreshes are serialized by a lock file beside the token and written
through a unique temporary file; downloads create their file name
exclusively, never overwriting and never writing through a symlink at that
name.

## Setup

Once per account, in a terminal:

1. A Google Cloud project with the Gmail, Google Sheets and Google Drive APIs
   enabled; an OAuth consent screen (External, published to **In production**:
   in Testing, refresh tokens expire after 7 days; the unverified-app warning
   is expected for personal use); a **Desktop app** OAuth client, downloaded
   as JSON.
2. `gaccess auth ~/Downloads/client_secret_….json` — consent in the browser;
   reports scopes left unchecked. The client JSON is not kept (the token
   carries the client id).
3. `gaccess gcloud-login` — `gcloud auth login` into the profile's
   configuration.
4. `gaccess check`. Enabling the plugin or changing its code needs a gateway
   restart.

`gaccess revoke` revokes and deletes the Google token. `--profile NAME` sets
up another profile, which also needs the plugin's `PROFILES` and its own
`plugins.enabled` and `platform_toolsets` entries.
