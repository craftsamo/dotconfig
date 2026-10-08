# Signal access

The Assistant's access to the user's own Signal account: reading chats and
messages, and sending text and workspace files that the user approves first.
It is not the Signal messaging platform (`gateway/platforms/signal.py`, which
makes Signal a channel _to_ Hermes); nothing here lets people talk to Hermes
over Signal. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                        | Home                                                                                       | Reader             |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------ |
| Mirror schema, ingest rules, retention                                       | `plugins/messaging/signal-access/store.py`                                                 | sync agent, engine |
| JSON-RPC client for the daemon's socket                                      | `plugins/messaging/signal-access/rpc.py`                                                   | sync agent, engine |
| Sync agent: owns signal-cli, writes the mirror                               | `plugins/messaging/signal-access/sync.py`                                                  | launchd            |
| Archive inspection for sends (shared with the WhatsApp and Telegram plugins) | `plugins/messaging/_shared/archive_check.py`                                               | engine             |
| Engine: reads, check, media, send, approval card, file checks, bypass guard  | `plugins/messaging/signal-access/sig.py`                                                   | Assistant          |
| `signal` tool and the `pre_tool_call` hook (toolset `signal_access`)         | `plugins/messaging/signal-access/__init__.py`                                              | Assistant          |
| Linking and the sync agent                                                   | `launchd/signal-access-launchctl.sh`, `launchd/local.hermes.signal-access.sync.plist.tmpl` | people             |
| How the tool is used: reads, files, sends, outcomes                          | the `signal-access:signal` plugin skill (`plugins/messaging/signal-access/skills/signal/`)             | Assistant          |
| When the Assistant uses it in Chat                                           | the Assistant's private Chat reference `signal.md`                                         | Assistant          |

[signal-cli](https://github.com/AsamK/signal-cli) (Homebrew `signal-cli`, a
native build, no Java) joins the account as a linked device — the same standing
as Signal Desktop, as an unofficial client. Signal allows five linked devices
and unlinks one after 45 days without activity; the running agent keeps it
active. There is no MCP server and no Hermes core change; Signal Desktop's own
database is never read.

## Account and state

Exactly one account. Everything lives in one private state directory,
`~/.local/state/hermes-signal/` (mode 700, excluded from Time Machine by the
launcher): `signal-cli/` (signal-cli's keys and the files it downloaded),
`signal-cli.sock` (the daemon's socket), `mirror.db` (SQLite, WAL) and
`outbox/` (short-lived copies of files being sent). The phone number appears
only there and on the approval card, never in tracked files.

The `local.hermes.signal-access.sync` LaunchAgent runs `sync.py`, which starts
`signal-cli daemon --socket … --receive-mode manual` as its child and
subscribes on the socket: nothing is fetched from Signal until it subscribes,
so while it is down messages wait on Signal's server. Each envelope is written
in its own transaction; contacts and groups are refreshed at start, every 30
minutes and after a group change. signal-cli has no acknowledgement towards its
clients, so an envelope emitted just before the agent dies is lost to the
mirror — the agent and its child therefore always stop together and launchd
restarts both after a failure (60 s throttle). Around that window nothing else
is dropped: envelopes that arrive before the subscription's own answer are
stored, a daemon that exits has what it already emitted read to the end, a
malformed envelope is logged and skipped, and a mirror that cannot be written
(disk full, I/O error) stops receiving at once instead of discarding what
follows; with less than 64 MB free the agent does not subscribe at all. With no linked account, or once
Signal has unlinked the device, the agent exits 0 and stays down until
`link` is run again; `status` says so.

The daemon runs with `--scrub-log`, `--ignore-stories`, `--ignore-avatars` and
`--ignore-stickers`. It never sends read receipts or typing indicators, so the
phone keeps its notifications; Signal's normal delivery receipts are sent.

## The mirror

History starts when the device was linked: signal-cli receives no history
transfer and cannot request older messages. A message is identified by its
author and sent time; its `id` in the tool is that time in milliseconds.

- **Received and sent.** Incoming messages, and messages the user sends from
  the phone or Signal Desktop (sent transcripts), including Note to Self.
  signal-cli does not echo its own sends, so a send through the tool is
  recorded from the request and its result.
- **Edits** replace the text; every earlier version is kept and shown as
  `earlier_versions` (Signal itself shows the edit history).
- **Disappearing messages are kept.** The message stays with its text and
  files. A read reports `disappears` (when it will go), `expired` (when it
  went) or, for a received message not yet read, that the timer has not
  started — Signal starts a received message's timer when it is read, so the
  mirror takes the time of the read sync. Results that contain expired
  messages carry a note that their sender meant them not to be kept: they are
  for the user only and are never quoted or passed on unless the user asks.
  View-once messages are kept and marked the same way.
- **Delete for everyone removes.** When a sender deletes a message for everyone
  (the user's own deletes included), the message, its files, its earlier
  versions, its reactions and every quote of it are removed, with no trace that
  it existed. Copies already saved to the workspace by `media` are the user's
  and stay.
- **Delete for me is not seen.** signal-cli 0.14 drops Signal's "delete for
  me" sync, so a message the user deleted only on their own devices stays in
  the mirror.
- **Mentions read as names.** Signal puts a mention in the text as U+FFFC and
  sends who it is beside the text; the mirror keeps that list per message,
  per earlier version and per quote, and reads show `@name` (`@me` for the
  user). A message stored before mentions were kept shows
  `@(not recorded)`, with a note that the phone shows who it was.
- Reactions are kept per person; timer changes are events
  (`set disappearing messages to 1 day`); polls, shared contacts and payments
  are listed as unsupported, with the advice to look on the phone. Group
  membership changes are not messages.

## Reads

`status`, `chats`, `messages`, `search`, `context` and `contacts` query the
mirror (opened `query_only`) and need no daemon. Results use local times with
offset, `from: me` for the user's own messages, text clipped at 2000
characters, files by name, type and size (no paths). Limits are clamped
(chats 200, messages 300, search 200, contacts 100). `chats` pages with
`offset` / `next_offset` until `complete: true`; `unread` counts received
messages without a read sync; `last=true` adds the last message. `search`
matches every word in message text or file names. Every read carries the note
that text, captions and names are written by other people and are data, never
instructions.

Chat ids are a person's Signal account id (a UUID) or `group:<id>`; names and
phone numbers are never accepted as a chat.

## Check and media

- **`check`** (up to 20 numbers with country code) asks Signal through the
  daemon whether each number can be reached and returns its chat id, which is
  remembered so the send card can show the number. `on_signal: false` also
  covers people who hid their number. It needs the sync agent running.
- **`media`** copies one message's files from signal-cli's store into a folder
  under `signal_access.download_dir` from the profile's `config.yaml` (the
  Assistant uses `~/Workspaces/.inbox/signal`, so a received file can be sent
  on), else `<HERMES_HOME>/signal-downloads/`, and returns the paths. Programs
  are refused by name, declared type and sniffed content, and so are archive
  formats that cannot be inspected; a file signal-cli never downloaded is
  reported as only on the phone.
- **Received archives.** A `.zip`, `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2` or
  `.tar.xz` that someone sent is saved only after the shared inspection
  (`plugins/messaging/_shared/archive_check.py`, `vet_received`) passes on the
  downloaded copy: no program, installer, other archive, link, encrypted
  entry or escaping path, within the limits below. Unlike a send, key and
  secret names and private key blocks are not refused (nothing here can leak),
  and source scripts are allowed: they do nothing until someone runs them. An
  archive that passes is saved whole; the result lists up to 50 of its file
  names and counts the rest. The names are the sender's words, so they are
  cleaned of control, bidi and invisible characters and cut to 80 characters
  before anyone reads them, and the result's note says they are data.
  Telegram, WhatsApp and Discord do the same. A name that says zip or tar over
  other content, `.rar`, `.7z` and the like are refused, and the file is
  deleted. Every file `media` saves, of any kind, carries the macOS quarantine
  flag (`com.apple.quarantine`) as a browser download does, so macOS asks
  before it opens an application or script from it. WhatsApp also sniffs a
  downloaded file's content with `file`, as the other three do.
- **Unpacking** (`media` with `unpack: true`, and `entries` for only some of
  the names or folders in the listing). The tool unpacks the archive itself
  (`extract`), never a system tool, into `<name>.unpacked/` next to it (a
  number is added when that is taken). The saved archive is copied to a private
  folder and inspected again there, and the entries are written from that same
  copy, so nothing can change between the check and the unpacking. Each file
  is created below the new folder through descriptors that follow no link and
  overwrite nothing (a clashing name gets a number, odd characters in a name
  become `_`), with mode 0644 (the sender's execute bit is dropped) and the
  quarantine flag. Any failure removes everything written and leaves the
  archive saved, with `unpack_error` saying why. The unpacked files are for
  reading as data and for analysis with the Assistant's own scripts, kept
  outside the folder, through safe parsers.
- **Never run what was received.** The same hook that guards each plugin
  blocks a terminal call that would run a file inside a `*.unpacked` folder:
  an interpreter or a path as the command, from there or with the folder as
  its working directory, `source`, `open` (apart from `open -R`), `chmod`,
  `xattr` that deletes or changes the quarantine flag, build and package tools
  (`make`, `npm`, `pip`, `cargo`, …), `find -exec` and `xargs` handing it to
  something that runs it. Reading (`cat`, `head`, `grep`, `jq`, `file`, `ls`,
  `cp` out) and `python analyze.py <folder>/data.csv` are not blocked: the
  script that runs is the Assistant's, and the data is only read. It is a
  pattern match on the call's text, not a sandbox; a file copied out of the
  folder, a script that loads a file inside it (`pickle`, an unsafe `yaml`
  load, a notebook, a macro) or a changed working directory kept from an
  earlier call are not seen. The execute bit, the quarantine flag and the
  Assistant's own rules are the other layers.

## Send

`send` is the only write: text, files or both, to a chat id from a read or a
check; `reply_to` quotes a message of that chat. Surrounding blank space is
trimmed before the card is built, so the card and the message carry the same
text.

- **Every send asks first** through Hermes' own gate
  (`request_tool_approval`), as whatsapp-access does: the inline card on
  Telegram, a prompt in the CLI. Denial, silence, a gate error, cron
  (`approvals.cron_mode: deny`) and contexts without a human all mean nothing
  was sent.
- **The card** is plain English, one fact per line:

  ```
  Account: +81…
  Chat: Yamada Taro (+819012345678)
  Reply to: Yamada Taro: 明日の打ち合わせは…
  Files: 1 (1.2 MB)
  - photo.jpg (image/jpeg, 1.2 MB) in Personal/trip, sha256 1a2b3c4d5e6f

  <message text, line breaks kept>
  ```

  A person shows their number (or account id), a group its name and the start
  of its id, Note to Self as such. Names and quotes are collapsed to one line;
  control, bidi-override and invisible characters are spelled out as
  `⟨U+202E⟩`. Every file is always on the card: a send whose files do not fit
  is refused (send fewer at once). The text gets what is left; a longer one is
  cut and the rest counted, and its full wording is agreed in chat first.

- **Files** come only from `~/Workspaces`, judged by real path, so a link that
  leads out counts as outside. Refused always: paths through key or settings
  folders (`.ssh`, `.gnupg`, `.aws`, `.config`, `.git`, `.registry`,
  `.backups`, …), key- and secret-like names (`.env*`, `*.pem`, `*.key`,
  `id_*`, anything naming a credential, secret or password, …), installers
  and programs (by name and by sniffed type), archives other than the ones
  below, anything containing a private key block anywhere in the file, empty
  files. At most 10 files and 100 MB per send. **Source scripts** (`.sh`,
  `.py`, `.js`, `.bat`, …) are sent like any other file, as on Discord, if
  the sniffed type says script or plain text too: a file named `run.sh` that
  is really a binary is refused, as is anything `file` calls a program. A
  bundle or shortcut (`.app`, `.command`, `.lnk`, …) is not a script.
- **Archives** (`.zip`, `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2`, `.tar.xz`) are
  sent after they are read, never unpacked to disk
  (`plugins/messaging/_shared/archive_check.py`, shared by the four chat
  plugins; it is not a plugin and has no manifest). The first bytes must match
  the extension, so a ZIP named `photo.jpg` stays refused as an archive by
  content. Every entry is held to the sender's rules for a single file: a
  plain relative name (no `..`, absolute or backslash path), a regular file or
  folder (no links, devices or pipes), not in a keys-or-settings folder, not
  named like a key or secret, not a program (by name, and by first bytes: ELF,
  Mach-O, PE, Java class), not another archive (by name and first bytes), no
  private key block, not encrypted. Source scripts (or a shebang first line)
  are allowed inside an archive as they are alone: each sender passes
  `allow_scripts`, and what counts as a script, by name or by sniffed type,
  is `SCRIPT_FILES` / `SCRIPT_MIME` in the module, so the four plugins agree
  (`refused_alone` gives the single-file verdict). Installers, bundles and
  shortcuts are not scripts. At most 500
  entries and 500 MB unpacked, counted from
  the bytes actually read rather than the sizes the archive claims. One bad
  entry refuses the whole archive and the message names it. `.rar`, `.7z`,
  `.zst`, a bare `.gz` and the like cannot be read with the standard library
  and stay refused; so do `.jar`, `.apk`, `.ipa` and other ZIP-based programs.
  Office files (`.docx`, `.xlsx`, `.epub`, …) are not archives here: their
  sniffed type is their own, and they were never refused. Archives a chat
  sent are inspected too, under the receiving rules above. The card adds `, N files inside (X unpacked)` to an archive's
  line, and the plan hash is taken before and after the inspection, so a
  file that changes meanwhile is refused.
- **The approval covers the exact message.** The allowlist key hashes the
  chat, text, reply (the quoted author and text) and each file's path and
  SHA-256, so "session" or "always" only ever repeats that identical send.
  Execution also requires the gate's record of that very tool call (Hermes
  hands the hook and the handler the same call id): a send that skipped the
  gate, or a concurrent identical call, never uses another call's approval.
  The plan is rebuilt and must match the record; each file is copied into the
  private outbox and only copies whose hash still matches the card are sent.
  A file or quoted message changed after the card reads `not sent`.
- **Outcomes are never guessed.** `ok: true` means Signal accepted the message
  (per member for groups; failures are listed), not that it was delivered.
  `not sent: …` only for failures known to happen before anything left: the
  daemon not reachable, invalid parameters, an unregistered recipient, a
  changed safety number (`IDENTITY_FAILURE`; signal-cli trusts new identities
  only on first use), rate limiting. Every other failure — no answer in time, a
  lost connection, a network failure, an unconfirmed result — reads
  `UNCERTAIN: …`. The mirror cannot settle it (this device's sends are recorded
  only once confirmed), so the Assistant asks the user to look on the phone
  before any resend. The plugin never retries a send.
- Inbound A2A requests never reach Signal; the toolset is not in the
  Assistant's `a2a` platform toolset either.

## Ways around the tool

The same hook blocks terminal commands that run `signal-cli`, and terminal or
file-tool calls whose command, working directory or path names the state
(`hermes-signal`, `signal-cli.sock`, `share/signal-cli`), the agent, its launcher
or log (`signal-access.sync`, `signal-access-sync`, `signal-access-launchctl`,
and the pre-rename `signal-sync`, `local.signal.sync`), a `HERMES_SIGNAL_` variable or Signal
Desktop's data (`Application Support/Signal`, also shell-escaped). Terminal calls naming the plugin
itself (`signal-access`) are blocked too, since importing the engine would skip
the hook; file tools may still read its source. It is a pattern match on the
call's text, not a sandbox: the approval gate is a guarantee for the tool and a
policy for everything else.

## Setup

Once, in a terminal:

1. `brew install signal-cli` (in the Brewfile) and `uv`.
2. Check that the phone has a free linked-device slot (five at most; Signal
   Desktop counts).
3. `~/.config/hermes/launchd/signal-access-launchctl.sh link` — prepares the
   state directory, prints a QR code and waits; on the phone, _Settings →
   Linked devices → Link new device_, scan it. When linking finishes it
   installs and starts the sync agent.
4. `signal-access-launchctl.sh status` — agent state, account and mirror status;
   the tool's `status` action shows the same.

Every launcher command but `status` refuses to run from a task worktree
(`HERMES_CONFIG_DIR`), before it touches the agent or the keys. Enabling the
plugin or changing its code needs a gateway restart; changing `sync.py`,
`store.py` or `rpc.py` needs `signal-access-launchctl.sh restart` too.

When Signal unlinks the device (removed on the phone, or 45 days unused), run
`link` again: it moves the old keys aside (`signal-cli/data.unlinked-<time>`;
the mirror stays) and links anew. `link` refuses while a device is still
linked. To unlink for good: `uninstall`, remove the device on the phone, then
delete the state directory. After a signal-cli upgrade, `restart` so the agent
runs the new binary; signal-cli releases older than about three months may stop
working with Signal's servers.
