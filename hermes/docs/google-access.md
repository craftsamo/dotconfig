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
| How the Assistant works a sheet: reads, guarded writes, approvals, formatting, checking the look, recovery, sheet design | the `google-sheets` technic (`profiles/assistant/skills/technic/google-sheets/`) | Assistant |
| When the Assistant uses the tools in Chat, and Gmail, Drive and gcloud | the Assistant's private Chat reference `google.md` | Assistant |

The engine uses the Google client libraries of Hermes' own runtime (the
`google` extra `setup.sh` installs) and the `gcloud` binary on `PATH`. The
upstream `google-workspace` skill is disabled for the Assistant: it asks for
every Workspace scope at once and keeps one unscoped token.

## Account, scopes and state

One Google account per profile, kept outside every repository:

| State | Home | Content |
|---|---|---|
| OAuth token | Keychain item `GOOGLE_OAUTH_<PROFILE>` (project `hermes`, scope `google-access`) | refresh token, client id and secret, granted scopes: `spreadsheets`, `gmail.readonly`, `gmail.send`, `drive.readonly`, `drive.file` |
| `gcloud/` | `~/.hermes/profiles/<profile>/google-access/` | Hermes' own gcloud configuration (`CLOUDSDK_CONFIG`) |
| `token.generation` | the same directory | no secret: a random mark rewritten each time the token is stored |

The token sits in a Keychain scope no Hermes profile receives (the
arrangement the YouTube and X credentials use), so it never enters a
profile's secret layer, the gateway's environment or a CLI session; the
engine reads it with the `secret` CLI when a profile's first call needs it
and keeps access tokens only in memory. Values reach the CLI through stdin,
never argv. A `token.json` an earlier version left in the state directory is
moved into the Keychain on first use (stored, read back, then deleted; kept
if the Keychain refuses), but only while no generation mark exists: once the
Keychain has held the token, an item that reads as missing is reported as
unreadable instead of being replaced by an old file. gcloud's own login
stays a file: `credentials.db` belongs to gcloud.

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
  `clear` / `create` / `add_sheet` / `layout` / `data` / `chart` / `pivot` / `protect` /
  `comment`, Gmail `send`, Drive `upload`, and every
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
  `batch_update`, `append`, `add_sheet`, `layout`, `chart` and `pivot` share one allowlist key per
  spreadsheet id, so "session" on the first card lets the rest of that
  spreadsheet's edits run for the session and "always" for good; another
  spreadsheet asks again. The spreadsheet's version history undoes them.
  `clear` and `create` keep a key per exact call, like every other change:
  "always" there only repeats that identical call. So does every `data`,
  `protect` and `comment` call, a `layout` call changing
  `spreadsheet_settings` (the locale and time zone re-read every date and
  number in the file), and a `layout` call
  holding any op that deletes, moves or replaces data, or picks a rule or
  view by its number or name to replace or drop it (`delete`, `move`,
  `merge`, `table_delete`, `sheet_delete`, `conditional_update`,
  `conditional_delete`, `filter_view_delete`; `LAYOUT_DESTRUCTIVE`), removes notes or replaces a
  filter view's criteria (`_destructive`), and a `chart` or `pivot` call that
  deletes one (`OBJECT_DESTRUCTIVE`) or writes a pivot table at a cell, which
  overwrites what it fills, so a grant for formatting never covers dropping
  rows.
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
  formatting, borders, sizes, hiding and grouping, inserting/deleting/moving
  rows and columns, merges, freezing, tab properties (gridlines included) and
  copies, the spreadsheet's locale and time zone, notes, rich
  text, native tables, conditional formatting, input rules, filters and filter
  views), never
  raw API requests, so the gate can word and classify every one. As
  `batch_update` takes scattered cells in one call, an op that applies the
  same change to scattered places takes `ranges` instead of `range` (at most
  `BATCH_LIMIT` ranges per call); `insert` and `move` keep one range, since
  each shifts what the next position would mean, and a multi-range `delete`
  runs bottom-up so its row numbers are the ones read before the call. Its card
  reads `SpreadSheet:`, `Sheet:` when every op is on one tab, the checks,
  then one line per op (`Width of columns B-D: 140px`,
  `Delete rows 4-5 with their contents`), counting the rest as `(+N more changes)`. Tabs resolve
  to sheet ids by name (a bare word is a tab, never a named range); tables by
  name or id. `table_update` keeps the columns it does not name, and
  `table_delete` removes the table with its contents (the API has no
  unconvert). Later ops in a call see earlier ones: a renamed tab, table or
  view goes by its new name, a copied tab by its title (the engine picks the
  copy's sheet id), and tab positions are where a tab ends up, translated to
  the API's before-the-move index. `rich_text` rewrites one cell's text with
  its partial styling, so without `value` it refuses a cell that holds a
  formula, number or date rather than turn it into text, and after an
  insert, delete or move (or another `rich_text` on that cell) in the same
  call, whose text read before the call may no longer be the cell's. `info` lists each
  tab's frozen counts, merges, tables, numbered conditional rules, groups,
  filter and filter views, which the update and delete ops refer to;
  `get_format` reads closed blocks of up to `FORMAT_CELL_LIMIT` cells back in
  the format op's own words, without approval.
- **Data** is the op action for changes that move or rewrite contents
  (`DATA_OPS`: sort, find and replace, copy, cut, removing duplicate rows,
  trimming spaces, splitting text into columns, autofill). It shares
  layout's machinery (`OP_SETS`: a vocabulary, a normalizer, a request
  builder; `_Tabs` for tab names) but every call asks. Its card names the
  area each op overwrites, sized from the source (a copy's destination is
  the source's size, transposed when asked; no tab on `to` means the
  source's tab), keeps `header` rows of sort and dedupe out of the range,
  and shows find, replacement and delimiter text with tabs, newlines and
  repeated spaces visible. `split_text` cannot know how many columns it
  fills, so its card says the columns to the right are overwritten. The
  result counts replaced matches, removed duplicates and trimmed cells.
- **Charts and pivot tables** are the `chart` and `pivot` op actions. A
  chart is drawn from one range (labels column, then one series per
  column), floats over the tab rather than writing cells, and is found by
  title or id; `chart_update` keeps a chart's sources unless given a new
  range, and later ops see earlier moves and resizes. A pivot table goes on
  a new tab unless `at` names a cell; an unqualified `at` means the data's
  tab. Pivot tables have no id in the API, so `pivot_delete` names the
  anchor cell and the engine checks a pivot table starts there before
  writing; `get_format` reports anchors and `info` lists charts.
- **Protected ranges** are the `protect` op action. Every call asks, and
  its card names each editor in full, never clipped: a call whose card
  would exceed the budget, or whose address Hermes' approval prompt would
  mask as a secret (`redact_sensitive_text`), is refused rather than shown
  partly. Google adds the requesting user as an editor and the file's owner
  always keeps access, so the card says "editable only by you, the file's
  owner, …". Turning a warning-only protection into a blocking one needs an
  editor list, since without one Google opens it to every file editor, and
  naming editors ends warning-only. Google refuses the whole call for an
  address it does not accept. Protections are found by id or label (the
  API's description); `info` lists them with their editors.
- **Comments** are the `comment` op action: add a comment on one cell
  (optionally assigned), reply, resolve or reopen, edit your own post, delete
  a thread you started. Every call asks, because a comment reaches other
  people (an assignee or a `+address` / `@address` mention is emailed) and
  version history keeps no comments; the card names whoever is emailed, and a
  card Hermes would mask is refused. Comment changes can fail on their own
  while the call succeeds, so the result is `ok: false` unless
  `commentUpdateState` reads `ALL_SAVED`. The read action `comments` lists
  threads with their cell (`commentsViewMode` goes on the request URI, as the
  client library's bundled API description predates comments).
- **Table appends.** `append` with `table` (a native table's name or id)
  sends `appendCells` with the `tableId`, so rows fill the table's free rows
  and the table grows before its footer; a plain range append would land
  after the footer or outside the table. `appendCells` has no UI typing:
  numbers and booleans keep their type, `=…` is a formula unless `raw`, and
  other text, dates included, stays text. It shares the per-spreadsheet key.
- **Snapshots** are a read (no approval): `snapshot` exports a tab, or a
  closed block of it, through the `docs.google.com/…/export?format=pdf` URL
  with the profile's token (the parameters Google's own Apps Script samples
  use, not a documented API) and renders the first pages to PNG with
  ImageMagick (`sips` draws page 1 without it). The files go to the download
  folder's `sheet-snapshots/`, so the look can be checked with vision instead
  of a browser.
- **Row guards.** Writes by row number can land on the wrong row when another
  writer inserts, deletes or sorts rows. `update`, `batch_update`, `clear`,
  `layout` and `data` take `expect` — up to 200 single cells with the value each must display
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
`~/.config/gcloud`, this plugin's state directory (only the plugin source
under `plugins/` excepted), its Keychain item or scope, or a whole-Keychain
read (`dump-keychain`, `secret export`). It is a pattern match on the call's text, not a
sandbox: it stops ordinary use, not a determined script.

Token refreshes run one at a time, the HTTP transport's own (on expiry or
a 401) included, and a refresh token Google rotates is stored only over the one
it was refreshed from. Keychain read-modify-writes are serialized by a lock
file in the state directory, and an item that exists but cannot be read
(a locked keychain) stops them instead of being replaced. Every store is
read back before it counts. A process holding credentials from an older
generation mark, or a cached token Google refuses or that lacks a scope,
reads the Keychain again, so a new `gaccess auth` or `revoke` reaches the
running gateway without a restart. `revoke` fails unless the item is
confirmed gone.
Downloads create their file name
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
   reports scopes left unchecked and stores the token in the Keychain. The
   client JSON is not kept (the stored token carries the client id and
   secret).
3. `gaccess gcloud-login` — `gcloud auth login` into the profile's
   configuration.
4. `gaccess check`. Enabling the plugin or changing its code needs a gateway
   restart.

`gaccess revoke` revokes the Google token and removes it from the Keychain. `--profile NAME` sets
up another profile, which also needs the plugin's `PROFILES` and its own
`plugins.enabled` and `platform_toolsets` entries.
