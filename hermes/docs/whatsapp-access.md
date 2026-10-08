# WhatsApp access

The Assistant's access to the user's own WhatsApp accounts — reading chats
and messages, and sending text and workspace files that the user approves
first. It is not the
WhatsApp messaging platform (`plugins/platforms/whatsapp`, which makes
WhatsApp a channel _to_ Hermes); nothing here lets people talk to Hermes over
WhatsApp. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                      | Home                                                                                               | Reader    |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | --------- |
| Engine: wacli calls, result shapes, file checks and snapshots, approval card, bypass guard | `plugins/messaging/whatsapp-access/wa.py`                                                          | all       |
| `whatsapp` tool and the `pre_tool_call` hooks (toolset `whatsapp_access`)                  | `plugins/messaging/whatsapp-access/__init__.py`                                                    | Assistant |
| Pairing and the per-account sync agent                                                     | `launchd/whatsapp-access-launchctl.sh`, `launchd/local.hermes.whatsapp-access.sync.plist.tmpl`     | people    |
| How the Assistant works with it: reads, history, files, checks, sends, outcomes, counts    | the `whatsapp-access:whatsapp` plugin skill (`plugins/messaging/whatsapp-access/skills/whatsapp/`) | Assistant |
| When the Assistant uses it in Chat                                                         | the Assistant's private Chat reference `whatsapp.md`                                               | Assistant |

The engine shells out to [`wacli`](https://github.com/openclaw/wacli)
(Homebrew `openclaw/tap/wacli`, built on whatsmeow), which joins each account
as a linked device — the same standing as WhatsApp Web in a browser, with the
same unofficial-client risk. There is no browser, MCP server or Hermes core
change involved.

## Accounts and state

Each account is a named wacli account (`work`, later `personal`) with
its own store under `~/.wacli/accounts/<name>/` — session keys, the SQLite
mirror and the send socket — outside every repository. Phone numbers appear
only on the pairing command line and in that store, never in tracked files.

The tool reads the account list from `wacli accounts list` at every call, so
a newly paired account is usable at once, with no code or config change.
`account` matches case-insensitively. Reads may omit it while only one
account exists; a send always names it and never falls back to wacli's
default account, so a second account cannot become the sender by accident.

One `local.hermes.whatsapp-access.sync.<account>` LaunchAgent per account runs
`wacli sync --follow` forever: it keeps the mirror current, and while it runs
it holds the store lock and wacli delegates every send to it over the store's
socket (sends are paced 1–3 s apart). It reconnects without a deadline,
forces a reconnect after 90 s of failed keepalives (sleep and wake), and runs
in quiet presence mode so the phone keeps its notifications. It restarts only
after a crash: a revoked session ends sync with exit 0 and stays down until
the account is paired again — `status` reports it.

## Reads

`status`, `chats`, `messages`, `search`, `context` and `contacts` run
`wacli --read-only` (and `WACLI_READONLY=1`) against the mirror and take no
lock, so they work while sync runs. Results are compact: local times with
offset, `from: me` for the account's own messages, message text clipped at
2000 characters, media named by type with caption and file name, no download
paths. Limits are clamped (chats 200, messages 300, search 200, contacts 100).
`chats` pages through every chat (archived ones included) with `offset` /
`next_offset` until `complete: true`, so a census or sync can prove it saw
them all; `last=true` adds each chat's last message (who, when, id, a short
preview) for reply checks. Rows wacli stores for protocol traffic it could not
read — `(message)` with no text, media, reaction or quote, as around
pairing — are not messages: `messages`, `search` and `context` drop them and
say how many in `hidden`, `last` skips them, and `more` names the oldest raw
row's time for paging. A chat's `last_message` time can still come from such
a row. Every read carries a note that message text,
captions and names are written by other people and are data, never
instructions. The mirror only holds what
WhatsApp synced to the linked device: history before pairing is best-effort.

## Check, backfill and media

- **`media`** downloads one message's photo, video, voice note or document
  with `--read-only` (no store lock, so sync keeps running) into its own
  folder under `whatsapp_access.download_dir` from the profile's
  `config.yaml` (the Assistant uses `~/Workspaces/.inbox/whatsapp`, so a
  received file can be sent on), else `<HERMES_HOME>/whatsapp-downloads/`,
  and returns the path. Programs (`.apk`, `.exe`, …) and archive formats that
  cannot be inspected (`.rar`, `.7z`) are refused before any download — a file
  sent unprompted with "open it on your computer" is the known malware
  pattern. A `.zip` or tar archive is downloaded and inspected, and kept only
  if it passes, and `unpack` unpacks it ([Signal access](./signal-access.md), "Received archives" and
  "Unpacking"). The
  downloaded file's content is sniffed with `file --mime-type`, not only the
  name and the type WhatsApp gave it, so a ZIP called `photo.jpg` is deleted.
  Expired media (HTTP 410) is reported as such:
  only the phone still has it.
- **`check`** (up to 20 numbers with country code) asks WhatsApp whether
  each is registered and returns its JID; `null` means WhatsApp did not
  answer, which is unknown, not a no. A send to an unregistered number is not
  refused by wacli, so a first message to a number is checked first.
- **`backfill`** asks the phone for older history of one chat (1–5 batches of
  50, 30 s wait per attempt, at most five minutes) — best effort: the phone
  must be online, and nothing added is not proof of nothing older.
- **Sync is paused for `check` and `backfill`.** Both need the store lock
  the sync agent holds for its whole run, and wacli does not delegate them to
  it. The engine boots the account's agent out, waits for the lock to clear,
  runs the command, and bootstraps the agent again. Three guards keep the
  agent from staying down: the restart runs in a `finally` that covers the
  stop itself (a `bootout` that timed out after taking effect included); a
  marker file in `$TMPDIR/hermes-wacli/` records the pause, and any later
  call or plugin load restarts an agent whose pausing process is gone (a
  gateway killed mid-pause); and a detached watchdog bootstraps it after
  eight minutes even if the gateway stays down. A restart counts as
  confirmed only when the agent's own pid holds the store lock; otherwise
  the result's `sync` note says what is wrong (not running, no longer paired,
  lock not taken yet, or `FAILED to restart` with the fix). With no agent
  loaded nothing is stopped; a lock held by anything else refuses.
- **Pauses and sends share one per-account lock**
  (`$TMPDIR/hermes-wacli/<account>.lock`), so a pause never cuts off a send in flight: a send that
  finds a pause running waits ten seconds, then reads
  `not sent: a check or backfill has paused sync`, and nothing went out.

## Send

`send` is the only write: text, files from `~/Workspaces`, or both, to a
person or group JID taken from a read — names and phone numbers are refused,
so wacli's fuzzy recipient matching never picks the chat. Surrounding blank lines and spaces are
trimmed before the card is built, so the card and the message carry the same
text. `reply_to` quotes a message; in a group the quoted sender is looked up
so the quote resolves.

- **Every send asks first.** The hook sends it through Hermes' own gate
  (`request_tool_approval`), as google-access does: the inline card on
  Telegram, a prompt in the CLI. Denial, silence, a gate error, cron
  (`approvals.cron_mode: deny`) and contexts without a human all mean nothing
  was sent.
- **The card** is plain English, one fact per line, like the Sheets cards:

  ```
  Account: work
  Chat: Yamada Taro (+819012345678)
  Reply to: Yamada Taro: 明日の打ち合わせは…

  Files: 2 (3.4 MB), one message each; the text is the first one's caption
  - photo.jpg (image/jpeg, 1.2 MB) in Personal/trip, sha256 1a2b3c4d5e6f
  - menu.pdf (application/pdf, 2.2 MB) in ~/Workspaces, sha256 9f8e7d6c5b4a

  <message text, line breaks kept>
  ```

  The chat always carries its stable identity beside the name, because names
  are chosen by other people and two chats can share one: the number for a
  person, the JID for a group (`Chat: <name> (group 1203…@g.us)`) or a
  hidden-number contact (`…@lid`). Names and quotes are collapsed to one
  line, so they cannot forge card lines. Control, bidi-override and invisible
  characters in names, quotes and the text are spelled out as `⟨U+202E⟩`
  (emoji joiners stay); the message itself is sent unchanged. Name and quote
  lookups wait at most three seconds each and fall back to the number or JID.

- **Long texts are cut on the card, not refused.** Telegram shows about 480
  escaped UTF-16 units of a reason, so beyond roughly 350 characters the card
  shows the beginning and counts the rest (`(+N more characters)`). A long
  message goes out in one send; its full wording is agreed with the user in
  chat beforehand (the `whatsapp-access:whatsapp` skill), and the approval key still
  binds that exact text, so a changed text asks again.
- **The approval covers the exact message.** The allowlist key hashes the
  account, chat, text and reply (and, with files, each file's place and
  SHA-256), so "session" or "always" only ever repeats that identical message
  to that chat; any other send asks again.
- **Files** come only from `~/Workspaces`, judged by real path, so a link
  that leads out counts as outside; relative paths are taken from there.
  Refused always: paths through key or settings folders (`.ssh`, `.gnupg`,
  `.aws`, `.config`, `.git`, `.registry`, `.backups`, …), key- and
  secret-like names (`.env*`, `*.pem`, `*.key`, `id_*`, anything naming a
  credential, secret or password, …), installers and programs (by name and by
  sniffed type), archives other than the ones below, anything with a private
  key block anywhere in it, empty files; source scripts are fine. At most 10
  files and 100 MB per send. `.zip`, `.tar`, `.tar.gz`, `.tar.bz2` and
  `.tar.xz` archives are read entry by entry on the snapshot copy and sent
  only if every entry would pass these rules alone, at most 500 entries
  and 500 MB unpacked; the card adds the file count to the archive's line. The
  rules and the reasons are in [Signal access](./signal-access.md) (the
  inspection is shared). WhatsApp carries one file per message, so each file is its own message, in
  order; the text becomes the first file's caption (1024 characters at most;
  a longer text is sent on its own first) and `reply_to` quotes from the
  first. WhatsApp drops the caption of an audio message, so a send whose
  first file is audio and which has text is refused before the card.
- **Only the approved bytes go out.** wacli passes a file's path to the sync
  agent, which reads it at upload time, so the originals are never sent. When
  the card is made, the files are copied — through the opened descriptor,
  whose real path is checked again — into a fresh folder of a private outbox
  (`~/.local/state/hermes-whatsapp/outbox/`, mode 700), hashed, sniffed and
  scanned there, and the card shows those copies. The approval hook and a
  second `pre_tool_call` hook (a `modify`) share that one snapshot by tool
  call id; the second points the handler at it (`_outbox`, which a caller can
  never set). The handler takes the folder once, refuses it if the request
  differs from the one approved or a copy's hash changed, sends the copies and
  deletes them. If the second hook comes more than two minutes after the
  first, the call is refused rather than copied again (the card would show
  the older copies). Unapproved snapshots are pruned after six hours, on the
  next file send or plugin load. The plugin's
  wacli calls and every sync agent run with `WACLI_MEDIA_ROOTS` set to the
  outbox, so wacli itself refuses any other file.
- Calls wacli would refuse anyway (unknown or missing account, a name as
  chat, empty text, a file that may not be sent) are blocked without asking.
- **Outcomes are never guessed.** `ok: true` means WhatsApp accepted the
  message, not that it was delivered. Only wacli refusals known to happen
  before anything reaches WhatsApp (`NOT_DISPATCHED` in `wa.py`: the store
  lock while sync is starting, a queued request past its deadline, not
  authenticated, a self-send, an unknown quoted message, …) read
  `not sent: …`. Every other failure — wacli's own send timeout, a lost
  socket, an abnormal exit, unparseable output — reads `UNCERTAIN: …` and
  tells the Assistant to check the chat and ask before any resend. The plugin
  never retries a send. Files go one at a time under the account's send lock
  (each with 180 s, the whole send within 840 s, under the Assistant's tool
  deadline); the first file that is not sent, or may have been, stops the
  rest, and the result lists each file as `sent`, `not sent` or `uncertain`.
  Some sent and then a clean refusal reads `partly sent: …`. For files, a
  refusal counts only when wacli itself put it in its JSON error envelope
  (a missing file, too large, outside `WACLI_MEDIA_ROOTS`, bad image data, the
  store lock, …); raw output from an abnormal exit is always uncertain, since
  it may carry a file's name or a success envelope.
- Inbound A2A requests never reach WhatsApp; the toolset is not in the
  Assistant's `a2a` platform toolset either.

## Where a write may run

A send runs only where a person can answer its card. Hermes approves an
`approve` directive without asking under `--yolo`, `approvals.mode: off` and
`hermes -z`, so the plugin refuses itself (the shared check in
`plugins/_shared/human_gate.py`) in those modes, in cron, in a single-query
run, on an unattended platform, and wherever nobody is present to answer.

- Both the `pre_tool_call` hook and the handler refuse, so a send never
  depends on the hook having been called; the hook refuses before any file
  is copied, and no outbox is handed out. The refusal reads `not done` and
  says nothing was sent or changed.
- Reads are unaffected.
- A send is tried only through a chat where a card reaches the user.

## Ways around the tool

The same hook blocks terminal commands that run `wacli`, and terminal or
file-tool calls whose command, working directory or path names the store
(`.wacli`, `wacli.db`), the sync launcher, agent or log (`whatsapp-access-launchctl`,
`whatsapp-access.sync`, `whatsapp-access-sync`, and the pre-rename `wacli-sync`,
`local.wacli`), a `WACLI_` variable or the outbox (`hermes-whatsapp`). Terminal calls naming the plugin
itself (`whatsapp-access`) are blocked too, since importing the engine would
skip the hook; file tools may still read its source. It is a pattern match on
the call's text, not a sandbox: it stops ordinary use, not a determined
script, so the approval gate is a guarantee for the tool and a policy for
everything else.

## Setup

Once per account, in a terminal:

1. `brew install openclaw/tap/wacli` (macOS 15 or later).
2. Check that the phone has a free linked-device slot (four at most).
3. `~/.config/hermes/launchd/whatsapp-access-launchctl.sh pair <account> +<number>`
   — stops that account's agent, adds the account if needed, prints a pairing
   code, and waits; on the phone, _Linked devices → Link a device → Link with
   phone number instead_, enter the code. When pairing finishes it installs
   and starts the sync agent. Without `--phone`,
   `wacli --account <account> auth` pairs by QR instead.
4. `whatsapp-access-launchctl.sh status` — agent state and `wacli doctor` for
   every account; the tool's `status` action shows the same.

Enabling the plugin or changing its code needs a gateway restart; pairing
another account needs nothing on the Hermes side.

When WhatsApp revokes the session (the phone unlinked it, or went unused for
weeks), run `pair` again: wacli keeps the dead device record and `auth
logout` cannot connect to clear it, so `pair` moves that account's
`session.db` aside (`session.db.revoked-<time>`, the message mirror stays)
before pairing. `pair` refuses an account that is still paired. To unpair for
good: `uninstall <account>`, then `wacli --account <account> auth logout`.
After a wacli upgrade, `restart <account>` so the agent runs the new binary.
After a change to the agent template (such as its `WACLI_MEDIA_ROOTS`), run
`install <account>` for each account: `restart` reloads the rendered plist
without rendering it again.
