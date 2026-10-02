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

- **Changes ask first**: Sheets `update` / `append` / `clear` / `create` /
  `add_sheet`, Gmail `send`, Drive `upload`, and every gcloud command that is
  not a read. The action must be spelled exactly; the gate and the engine
  share one check, so no variant is read differently by each.
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
  and contexts without a human all block. The card shows the target, range,
  values, recipients, body or the full gcloud command.
- The allowlist key covers the exact arguments, so "always" only repeats that
  identical call.
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
