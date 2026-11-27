# Google runs on an upstream package, guarded here

Status: in force
Owner doc: docs/google-tools.md

## Decision

The Assistant reaches the user's Google account through the third-party package
craft-agent/google-tools, pinned to a release commit, instead of the retired
dotconfig plugin google-access. The person's OpenCode loads the same release from npm.

- **Its card is the package's, not `card.py`.** The package draws the card
  from what each write says the call will do and pins what it showed into the
  call, the guarantee `card.py` and a digest check gave our own plugins, so its
  shape is accepted as it is.
- **A standing answer covers the tool on the same target.** "Session" or
  "always" lets later calls of that tool on the same tab, recipient or folder
  run unasked; a call whose target cannot be told asks once, and a Gmail send
  asks every time. The per-spreadsheet standing rule and the My Drive upload
  rule of the old plugin no longer apply.
- **No mandates, no grants.** The gcloud mandates are retired (none was ever
  made), and no scheduled job writes to Google, so the `grants` toolset stays
  off. A write needs a person who can answer the card.
- **Cloud Run only; the general `gcloud` tool is retired.** Cloud Run goes
  through `google_run_*`; other Google Cloud work is the user's own or an
  OpenCode engineering task.
- **The guard is ours.** `plugins/guards/google-tools-guard` refuses writes
  where no person can answer and for an inbound A2A request, blocks the ways
  around the tools and draws the progress lines. It names the reads explicitly,
  so a tool the package adds later counts as a write. The pin `requires` the
  guard, and the package's `require_plugins` setting names it.
- **The sensitive-file checks are the guard's.** The package encrypts an upload
  only under `encrypt_dirs` and never a mail attachment, while the old plugin
  judged sensitivity from the Workspaces layout itself. So the guard refuses an
  upload from a sensitive area `encrypt_dirs` and `age_recipients` do not cover,
  and any attachment from one.
- **The credential sits in the package's state directory,** shared with
  OpenCode, not in the Keychain and not in the gateway's environment. The user
  runs login and remove.
- **Hermes never decrypts.** The package holds no secret key; the user opens a
  file with `age -d` and the identity they keep.

## Why

One implementation serves every harness the person uses, with more of Google
than the old plugin covered (drafts, labels, trash, Drive copy and move,
comments, Cloud Run). The package owns its tools, engine, card and skills;
this repository keeps only the guard and the settings.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- Drive writes reach only files the tools made or opened, and nothing changes
  sharing.
- The OAuth client must stay "In production", or refresh tokens die after
  7 days.

## Do not

- Turn on `grants` without a decision of its own.
- Widen `upload_dirs` beyond `~/Workspaces`.
- Leave a sensitive area outside `encrypt_dirs`.
- Name a read by a `_read` suffix in the guard, or let a new tool through until
  it is named.
