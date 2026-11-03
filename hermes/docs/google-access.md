# Google access

The Assistant's access to the user's own Google account — Sheets, Gmail and
Drive — and to the `gcloud` CLI, with every change held for the user's
approval (a gcloud command inside a [project mandate](#gcloud-mandates) the user
approved on a card of its own excepted). Read it when changing the plugin's
engine, its approval rules or its account setup. Common rules: [access-common.md](access-common.md). Part of the
Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                    | Home                                                                             | Reader    |
| ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------- |
| Engine, approval rule, bypass guard, setup CLI                                                                                           | `plugins/google-access/access.py`                                                | all       |
| `google_sheets`, `google_gmail`, `google_drive`, `gcloud`, `gcloud_mandate` tools and the `pre_tool_call` hook (toolset `google_access`) | `plugins/google-access/__init__.py`                                              | Assistant |
| gcloud mandates: terms, card, fit checks, the hourly count and making or ending one                                                      | `plugins/google-access/gcloud_mandate.py`                                        | Assistant |
| Setup launcher                                                                                                                           | `../bin/gaccess` (runs on `hermes-python`)                                       | people    |
| How the Assistant works a sheet: reads, guarded writes, approvals, formatting, checking the look, recovery, sheet design                 | the `google-access:sheets` plugin skill (`plugins/google-access/skills/sheets/`) | Assistant |
| When the Assistant uses the tools in Chat, and Gmail, Drive and gcloud                                                                   | the Assistant's private Chat reference `google.md`                               | Assistant |

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
| gcloud mandates      | the same directory: `mandates/`, `head.json`, `uses.jsonl`, `mandates.jsonl`     | MAC'd terms, head and ledger ([gcloud mandates](#gcloud-mandates)); the MAC key is Keychain item `GCLOUD_MANDATE_KEY_<PROFILE>`     |
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
without case or Unicode normalization, as macOS folders do, so `personal/` is
the `Personal` area.

- The upload opens the file first (never through a link at its name), judges
  it by where the open file really is, and sends only what it reads through
  that file, so a link or folder swapped in after the approval cannot send a
  sensitive file in the clear. A plain file with other hard links is refused:
  another of its names may lie in a sensitive area.

- The encrypted copy is made in a private temporary folder and removed once
  sent. Its Drive name ends in `.age` (a given `name` gets it too) and its
  content type is `application/octet-stream`, so neither says what the file
  is; the name itself is not hidden.
- No caller can turn encryption off. When no key is set up or `age` is
  missing, the upload is refused before its card.
- An upload reads only the public keys. The secret key is one Keychain item
  for every profile, of a kind the web3 wallet never reads, and stored
  `--no-env`, so `secret env` never puts it into an environment.
- `download` with `decrypt_to` brings a `.age` file back: the folder must
  exist inside a Group of a sensitive area, judged by the folder actually
  opened. The encrypted copy stays in a private temporary folder, the secret
  key is read from the Keychain only then and reaches age on its stdin, and
  the file is written without `.age`, owner-only and never over another.
  Nothing clear passes through the download folder; a `.age` file downloaded
  without `decrypt_to` lands there still encrypted.
- Any of the keys also opens a file by hand: `age -d -i <key file>
<name>.age`. The secret key `gaccess encryption init` shows once is the copy
  to keep outside this Mac; `add-recipient` adds another public key, such as a
  backup key kept elsewhere, for uploads from then on.
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
  a read (one that fits a [gcloud mandate](#gcloud-mandates) runs with no card).
  The gate and the engine share one check, so no variant is read differently by
  each.
- **A gcloud read** is a command path that resolves, in the installed SDK's own
  command tree (`data/cli/gcloud_completions.py`), to a command — not a group —
  whose last word is on a reviewed list of verb names (`GCLOUD_READ_VERBS`:
  `list`, `describe`, `get`, `read`, `search`, `ls`, `cat`, `test-iam-permissions`
  and each `get-*` / `describe-*` name checked against the SDK, such as
  `get-iam-policy` or `describe-from-family`) or starts with `list-`. A new SDK
  name that is not on the list asks until it is reviewed and added, so
  `get-password` or `get-signed-url` never runs unasked. Known commands that hand
  out a credential, key material, a signed URL or a MACsec configuration, write
  local state (a kubeconfig, an SSH key) or start a Cloud Shell are kept out
  even where a listed name covers them (`GCLOUD_SENSITIVE`:
  `authorization-code`, `print-*-token`, `get-credentials`, `get-auth-string`,
  `get-key-string`, `get-backup-index-download-url`, `get-mount-command`,
  `get-screenshot`, `get-yaml`, `get-public-key`, `get-public-cert`,
  `get-certificate-chain`, `get-ca-certs`, `macsec`), and `get-version` is not
  listed (under `compute hosts` and `compute reservations …` it starts a
  long-running operation). A read still prints what the resource holds, so the
  list is no promise that its output is free of secrets. Any other word
  (`access`, `tail`, `export`, `generate-*`, …) asks, and so does a read given a
  flag that writes a local file (`GCLOUD_WRITE_FLAGS`: `--output-file`,
  `--destination`, `--rbac-output-file`, `--ssh-key-file`,
  `--force-key-file-overwrite`), whatever its word. A path that
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
- **Drive uploads into My Drive are approved per profile.** `upload` into My Drive
  (with no parent folder) shares one allowlist key per profile, so "session" or
  "always" on the first card covers later uploads into My Drive for that profile.
  An upload into a folder (`parent`), an upload from a sensitive area (which goes
  up age-encrypted), or a call without a profile keeps a key per exact call.
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

## gcloud mandates

A mandate is the user's standing approval for a few non-read gcloud commands in
one project, made on a card of its own ([decision](decisions/gcloud-mandates.md)).
The `gcloud_mandate` tool (the Assistant's) makes, lists and revokes them:

- `create` takes `project` (the one project id), `commands` (one to five command
  paths, each an array of words as the `gcloud` tool's `command`; the exact leaf
  path of the SDK's tree, a release track being part of it), `flags` (up to 20
  long flags a covered call may use, e.g. `--image`; none when omitted),
  `per_hour` (covered commands an hour, 1 to 10; each call counts one), `days`
  (1 to 7) and `purpose` (one line, at most 200 characters). Every path and
  flag is checked against the installed SDK's tree when the card is drawn, so
  an unknown path, a group, a read, a path named twice, a path that is never
  covered, a flag no named command declares (a `--no-` form counts when the
  tree declares the switch), a flag named twice, a flag of a never-covered
  family and a missing tree all refuse before any card. The hook refuses for an
  inbound A2A request and where nobody can answer a card, and shows a card at
  🚨: the project, each command, the flags on one `Flags` line (`none` when
  there are none), the hourly bound, the end and the purpose, then what is
  never covered (dropped first when the chat's card is short; a card that
  cannot show every command and flag is refused). Its rule key is fresh,
  so no stored answer and no mandate approves another. The handler makes one
  only from the hook's record of that very call, after planning the paths again
  and finding the same terms as the card.
- `list` shows the mandates in force; `revoke` (`mandate` = its id) ends one at
  once. Neither asks.

A command fits a mandate when the check below finds every part of it accounted
for, and fails closed otherwise (the call then asks on its card as before). Its
call names the mandate's project and its path (as the tree names it, release
track included) is one of the mandate's. Its arguments are read against the
tree: a flag the tree does not list for the command, `--` (the end of flags), a
short flag such as `-q`, a flag missing its value and a switch written with a
value (`--async=true`) are not covered. Every
flag, written `--flag=value` or `--flag value`, must be one the mandate lists
(a `--no-` form only if that exact form is listed). Every flag value must be a
plain token (`FLAG_VALUE`: letters, digits and `. _ , : = @ / -`, starting with
a letter or digit, up to 300 characters) that holds none of `gs://`, `://`,
`projects/`, `organizations/`, `folders/` or `..`. The value of a flag whose
last word is `image` (or last two `image-url`) must start exactly with
`gcr.io/<project>/`, `<us|eu|asia>.gcr.io/<project>/` or
`<region>-docker.pkg.dev/<project>/` for the mandate's project (case aside; no
port, no trailing dot), so `docker.io`, `ghcr.io`, a bare `nginx` and another
project's image ask; a `--pack` value must hold an `image=` and every `image=`
and `builder=` in it must be such a path; any other value that starts like a
Google registry must be one too (`IMAGE_REGISTRY`, `REGISTRY_HOST`). Every
positional must be a plain lowercase resource id (`POSITIONAL`: up to 63 of
letters, digits, `.`, `_`, `-`). And the call is none of what is never covered:

- a path whose last word starts with `delete`, `remove`, `destroy`, `purge`,
  `reset`, `cancel`, `disable`, `undelete`, `rm`, `restore`, `stop`, `suspend`,
  `undeploy`, `abandon`, `revoke` or `replace` (`NEVER_ENDINGS`);
- a path holding, as a word or a dash-delimited part of one (`iam` is also
  `set-iam-policy`), `iam`, `service-account(s)`, `keys`, `secrets`, `kms`,
  `billing`, `organizations`, `folders`, `projects`, `resource-manager`,
  `auth`, `config`, `ssh`, `scp`, `iap`, `tunnel`, `proxy`, `port-forward`,
  `connect`, `access-approval`, `org-policies`, `identity`, `pam`,
  `access-context-manager`, `firewall-rules`, `access-config`, `metadata`,
  `password`, `scc`, `builds` or `storage` (`NEVER_WORDS`), or a
  `GCLOUD_SENSITIVE` word;
- a flag of `NEVER_FLAG_WORDS` (judged once a leading `no-`, `clear-`, `set-`,
  `update-`, `add-` or `remove-` is stripped): service-account(s), ingress,
  egress, network(s), vpc, subnet, subnetwork, iap, invoker, iam, member,
  role(s), acl, pap, public, authorized-networks, kms, key(s), secret(s),
  breakglass, binary-authorization, security-level, scopes, metadata, ssl,
  assign-ip, address, source-ranges, audiences, cloudsql, workload-pool,
  legacy-authorization, identity, organization, folder, billing-project,
  impersonate, account, configuration, delete, unauthenticated, bucket,
  volume(s), project(s), namespace, password; a flag ending in `-file`, `-dir`, `-directory` or `-path`;
  `--source`; or a `GCLOUD_WRITE_FLAGS` flag. These can never be listed, and
  are checked again on the call whatever a stored mandate lists.

A call without a project, or one whose path the tree cannot confirm, is never
covered. The hour has room for one more command, counted per mandate.
A command that runs on a mandate runs in a fresh, empty, private (0700)
temporary directory that is removed afterwards, so a plain name or an implicit
`.` resolves to nothing and a deploy from local source does not work under a
mandate (deploy an image). A command that asked on its card keeps the
process's working directory.

For a command that fits, the hook builds no card: it records the mandate's id
beside the digest of the command it would run, returns no approval directive
and skips the refusal for a run with nobody to answer. The handler peeks at that
record for the same reason; a call without a record is refused like any write
that skipped its gate. The engine takes the record, plans the call again and
requires the same digest, then `mandate.use` reads the mandate again, checks
the call still fits and counts it (one ledger row) before the subprocess
starts, under the store's lock: a mandate revoked or ended since the hook, a
call that no longer fits or an hour without room reads `not done: it no longer
fits the gcloud mandate (…)` with nothing run. The count stands whatever
becomes of the command. A command that asked on its card is recorded the same
way (without a mandate id), so a non-read command runs only as its card showed
and only after one: a handler call with no record, or with different arguments,
is refused.

State lives in the profile home under `google-access/`, beside the files above:
one MAC'd JSON per mandate (`mandates/`), a MAC'd head naming those in force
(only the head decides), a MAC'd opening row per mandate and then a MAC'd row
per counted command (`uses.jsonl`, MAC'd as `gcloud-use`), and a history file
kept for the record. The Keychain is skipped only while no `head.json` exists,
that is until the first mandate has been made. The MAC key is a random key in the
Keychain (`GCLOUD_MANDATE_KEY_<PROFILE>`, project `hermes`, scope
`google-access`, the scope of the OAuth token, which no profile receives), made
with the first mandate and read at every check, never cached: without a
readable key, or with a replaced one, nothing is in force and every command
asks. The MACs stop an edited or forged mandate, head or row, and a mandate
whose opening row is missing, or a ledger that is deleted, emptied, replaced or
not a plain file of this user, counts as used up. Neither an older head copied
back nor use rows removed from an intact ledger is detected; the guard on the
state and the key ([below](#ways-around-the-tools)) and the 7-day ceiling the
store enforces bound that. The store and the ledger
(`plugins/_shared/mandate_store.py`, `plugins/_shared/mandate_ledger.py`) are
shared with the other mandates; the terms, card and fit checks are
`gcloud_mandate.py`'s, and `access.py` hands it the validated call
(`GcloudCall`).

## Where a write may run

Every call that would get a card is refused first wherever no person can
answer it ([approval gate](access-common.md#approval-gate)), except a gcloud
command that fits a [gcloud mandate](#gcloud-mandates). For Sheets, Gmail and
Drive the check builds the card without any Google request, only to learn
whether the call changes something; a gcloud command is planned (no request
either) and looked up against the mandates in force. Reads and read-only gcloud
commands are unaffected.

## Ways around the tools

The same hook blocks terminal commands that run `gcloud`, `gsutil`, `bq` or
`gaccess`, and terminal or file-tool calls whose command, working directory or
path names the upstream Workspace scripts, `CLOUDSDK_*`, `~/.config/gcloud`,
this plugin's state directory (only the plugin source under `plugins/`
excepted), its Keychain items or scope, the text of an age secret key
(`AGE-SECRET-KEY-`), or a whole-Keychain read (`dump-keychain`,
`secret export`). The gcloud mandates' state (`google-access/` with `mandates`,
`head.json` or `uses.jsonl`) and the Keychain item of their MAC key
(`GCLOUD_MANDATE_KEY`) are also matched on the real path an argument resolves to
and without regard to case, so a link, a `..` or another letter case does not
hide them. Patterns: `CLIS` (read by command
position, with `_CLI` for a line that cannot be read that way), `_PATHS`,
`_MANDATE_STATE` and `_MANDATE_KEY` in `plugins/google-access/access.py`. A project's own tooling (`nps setup.google`,
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
