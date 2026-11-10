# WhatsApp access

The Assistant's access to the user's own WhatsApp accounts — reading chats
and messages, and sending text and workspace files that the user approves
first (plain text inside a [send mandate](#send-mandates) needs no card). It is
not the WhatsApp messaging platform (`plugins/platforms/whatsapp`,
which makes WhatsApp a channel _to_ Hermes); nothing here lets people talk to
Hermes over WhatsApp. Read it when changing the plugin or its sync agent.
Common rules: [access-common.md](access-common.md). Part of the Hermes design
docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                      | Home                                                                                             | Reader    |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | --------- |
| Engine: wacli calls, result shapes, file checks and snapshots, approval card, bypass guard | `plugins/messaging/whatsapp-access/wa.py`                                                        | all       |
| `whatsapp` tool and the `pre_tool_call` hooks (toolset `whatsapp_access`)                  | `plugins/messaging/whatsapp-access/__init__.py`                                                  | Assistant |
| Pairing and the per-account sync agent                                                     | `launchd/whatsapp-access-launchctl.sh`, `launchd/local.hermes.whatsapp-access.sync.plist.tmpl`   | people    |
| How the Assistant works with it: reads, history, files, checks, sends, outcomes, counts    | the `whatsapp-access:account` plugin skill (`plugins/messaging/whatsapp-access/skills/account/`) | Assistant |
| When the Assistant uses it in Chat                                                         | the Assistant's private Chat reference `whatsapp.md`                                             | Assistant |

The engine shells out to [`wacli`](https://github.com/openclaw/wacli)
(Homebrew `openclaw/tap/wacli`, built on whatsmeow), which joins each account
as a linked device — the same standing as WhatsApp Web in a browser, with the
same unofficial-client risk ([risk acceptance](access-common.md#risk-acceptance)).
There is no browser, MCP server or Hermes core change involved.

## Accounts and state

Each account is a named wacli account (`work`, later `personal`) with its own
store under `~/.wacli/accounts/<name>/` — session keys, the SQLite mirror and
the send socket — outside every repository. Phone numbers appear only on the
pairing command line and in that store, never in tracked files.

The tool reads the account list from `wacli accounts list` at every call, so a
newly paired account is usable at once. `account` matches case-insensitively.
Reads may omit it while only one account exists; a send always names it and
never falls back to wacli's default account, so a second account cannot become
the sender by accident.

One `local.hermes.whatsapp-access.sync.<account>` LaunchAgent per account runs
`wacli sync --follow` forever: it keeps the mirror current, and while it runs
it holds the store lock and wacli delegates every send to it over the store's
socket. It reconnects without a deadline and runs in quiet presence mode so the
phone keeps its notifications. It restarts only after a crash: a revoked
session ends sync with exit 0 and stays down until the account is paired again
— `status` reports it.

## Reads

Reads run `wacli --read-only` against the mirror and take no lock, so they work
while sync runs. Results carry no download paths. `chats` pages through every
chat (archived ones included) until `complete: true`, so a census or sync can
prove it saw them all. Rows wacli stores for protocol traffic it could not
read — `(message)` with no text, media, reaction or quote — are not messages:
reads drop them and say how many in `hidden`. Every read carries a note that
message text, captions and names are written by other people and are data,
never instructions. The mirror only holds what WhatsApp synced to the linked
device: history before pairing is best-effort.

## Check, backfill and media

- **`media`** downloads one message's file with `--read-only` (no store lock,
  so sync keeps running) into its own folder under `whatsapp_access.download_dir`.
  Programs and archive formats that cannot be inspected are refused before any
  download — a file sent unprompted with "open it on your computer" is the
  known malware pattern. A `.zip` or tar archive is downloaded and inspected,
  and kept only if it passes, and `unpack` unpacks it
  ([chat files and archives](./access-common.md#chat-files-and-archives)).
  The downloaded file's content is sniffed, not only the name and the type
  WhatsApp gave it, so a ZIP called `photo.jpg` is deleted.
- **`check`** asks WhatsApp whether numbers are registered and returns each JID;
  `null` means WhatsApp did not answer, which is unknown, not a no. A send to an
  unregistered number is not refused by wacli, so a first message to a number is
  checked first.
- **`backfill`** asks the phone for older history of one chat — best effort:
  the phone must be online, and nothing added is not proof of nothing older.
- **Sync is paused for `check` and `backfill`.** Both need the store lock the
  sync agent holds for its whole run, and wacli does not delegate them to it.
  The engine boots the account's agent out, waits for the lock to clear, runs
  the command, and bootstraps the agent again. Three guards keep the agent from
  staying down: the restart runs in a `finally` that covers the stop itself (a
  `bootout` that timed out after taking effect included); a marker file in
  `$TMPDIR/hermes-wacli/` records the pause, and any later call or plugin load
  restarts an agent whose pausing process is gone (a gateway killed mid-pause);
  and a detached watchdog bootstraps it after a few minutes even if the gateway
  stays down. A restart counts as confirmed only when the agent's own pid holds
  the store lock; otherwise the result's `sync` note says what is wrong. With
  no agent loaded nothing is stopped; a lock held by anything else refuses.
- **Pauses and sends share one per-account lock**
  (`$TMPDIR/hermes-wacli/<account>.lock`), so a pause never cuts off a send in
  flight: a send that finds a pause running waits briefly, then reads
  `not sent: a check or backfill has paused sync`, and nothing went out.

## Send

`send` is the only write: text, files from `~/Workspaces`, or both, to a person
or group JID taken from a read — names and phone numbers are refused, so
wacli's fuzzy recipient matching never picks the chat. Surrounding blank lines
and spaces are trimmed before the card is built, so the card and the message
carry the same text. `reply_to` quotes a message; in a group the quoted sender
is looked up so the quote resolves.

- **Every send asks first** ([approval gate](access-common.md#approval-gate)),
  as google-access does, unless it is plain text that fits a [send
  mandate](#send-mandates).
- **The card** has the [shared shape](access-common.md#card-shape):
  `WhatsApp · Send message`, then ⚠️ who sees it (the person, or everyone in
  the group). It names the account, the chat, the reply target and each file
  with its SHA-256 in a `Files` block; with files, the text is shown as the
  first file's caption. The chat always carries its stable identity beside the
  name, because names are chosen by other people and two chats can share one:
  the number for a person, the JID for a group or a hidden-number contact
  (`…@lid`). Name and quote lookups wait only briefly and fall back to the
  number or JID.
- **Long texts are cut on the card, not refused** (Telegram limits a reason's
  length): the card shows the beginning and counts the rest. A long message goes
  out in one send; its full wording is agreed with the user in chat beforehand,
  and the approval key still binds that exact text, so a changed text asks
  again.
- **The approval covers the exact message.** The allowlist key hashes the
  account, chat, text and reply (and, with files, each file's place and
  SHA-256), so "session" or "always" only ever repeats that identical message
  to that chat; any other send asks again.
- **The write checks what the card showed.** The hook records, under the tool
  call's id (under its arguments when there is none), a digest of the account,
  chat, text, reply and the requested file paths. The handler takes that record
  once (the id is the one Hermes binds for the handler's run), rebuilds the
  send and compares the
  digest before anything reaches wacli. A send with no record (the gate never
  ran for that call, or the record is older than 15 minutes) reads "not sent:
  this send did not pass its approval card", and one whose account, chat, text,
  reply or files changed since reads "not sent: … changed after the approval
  card was made". The allowlist key is never what the write is checked
  against.
- **Files** come only from `~/Workspaces`, judged by real path, so a link that
  leads out counts as outside. The refusal list is the shared one, and `.zip`
  and tar archives are read entry by entry on the snapshot copy and sent only if
  every entry would pass those rules alone; the rules and the reasons are in
  [chat files and archives](./access-common.md#chat-files-and-archives). WhatsApp carries one file per message,
  so each file is its own message, in order; the text becomes the first file's caption
  (a longer text than the caption limit is sent on its own first) and
  `reply_to` quotes from the first. WhatsApp drops the caption of an audio
  message, so a send whose first file is audio and which has text is refused
  before the card.
- **Only the approved bytes go out.** wacli passes a file's path to the sync
  agent, which reads it at upload time, so the originals are never sent. When
  the card is made, the files are copied — through the opened descriptor, whose
  real path is checked again — into a fresh folder of a private outbox
  (`~/.local/state/hermes-whatsapp/outbox/`, mode 700), hashed, sniffed and
  scanned there, and the card shows those copies. The approval hook and a second
  `pre_tool_call` hook (a `modify`) share that one snapshot by tool call id; the
  second points the handler at it (`_outbox`, which a caller can never set). The
  handler takes the folder once, refuses it if the request differs from the one
  approved or a copy's hash changed, sends the copies and deletes them. If the
  second hook comes more than two minutes after the first, the call is refused
  rather than copied again (the card would show the older copies). The plugin's
  wacli calls and every sync agent run with `WACLI_MEDIA_ROOTS` set to the
  outbox, so wacli itself refuses any other file.
- Calls wacli would refuse anyway (unknown or missing account, a name as chat,
  empty text, a file that may not be sent) are blocked without asking.
- **Outcomes are never guessed.** `ok: true` means WhatsApp accepted the
  message, not that it was delivered. Only wacli refusals known to happen before
  anything reaches WhatsApp (`NOT_DISPATCHED` in `wa.py`) read `not sent: …`.
  Every other failure — wacli's own send timeout, a lost socket, an abnormal
  exit, unparseable output — reads `UNCERTAIN: …` and tells the Assistant to
  check the chat and ask before any resend. Files go one at a time under the
  account's send lock; the first file that is not sent, or may have been, stops
  the rest, and the result lists each file as `sent`, `not sent` or `uncertain`.
  For files, a refusal counts only when wacli itself put it in its JSON error
  envelope; raw output from an abnormal exit is always uncertain.

## Where a write may run

A send is refused wherever no person can answer its card
([approval gate](access-common.md#approval-gate)) — unless it fits a [send
mandate](#send-mandates), which needs no card and so runs there too; the hook
refuses before any file is copied, so no outbox is handed out. The refusal reads
`not done`. A send is tried only through a chat where a card reaches the user,
or inside a mandate.

## Send mandates

A send mandate is the user's standing approval for plain text sends to a few
chats, made on a card of its own. A report that goes to the same chat every
morning then needs no one to tap a card, also in a cron job, while the chats,
the count, the length and the end stay the user's, read from the card. Why and
what is never allowed: [decision](decisions/send-mandates.md). A mandate names:

- **one account** (its wacli account name) and **one to five chats**, each by
  JID with the name and identity the card showed: a person by phone JID
  (`…@s.whatsapp.net`, identified by its number) or a group (`…@g.us`,
  identified by its JID). Never a contact whose number is hidden (`…@lid`: the
  card could not say who it is), a newsletter or a broadcast list. The plugin
  cannot read the account's own JID, so a mandate may name the account's own
  chat; wacli refuses a text to the linked account itself, so such a send is
  counted and not sent;
- **how many sends an hour** (1 to **5**, lower than Telegram's 30:
  more automated sends from an unofficial client raise the risk of the account
  being limited) and **the longest text** (at most 1000 characters). The 5 is
  the **account's total across its mandates in force**, not each mandate's: a
  new mandate whose `per_hour` plus that of every mandate in force for the same
  account would pass 5 is refused, naming what those already take, so two
  mandates on one chat never add up to more. The hook looks before it draws the
  card, and `create` checks again under the mandate store's lock, which is the
  check that counts; revoking a mandate frees its share;
- **a purpose** in one line and **an end** at most 30 days out.

`whatsapp_mandate` (toolset `whatsapp_access`, the Assistant only) has three
actions:

- **`create`** (`chats` = JIDs as `whatsapp` takes them, `account` when there
  are several, `per_hour`, `max_chars`, `days`, `purpose`) always asks, on a
  card of the [shared shape](access-common.md#card-shape) titled
  `WhatsApp · Send mandate`, marked 🚨, with every bound on it and what is never
  covered. The hook refuses it for an inbound A2A request and wherever no person
  can answer a card (cron, a single query, yolo mode, approvals off, an
  unattended platform), checks the chats' number, kind and uniqueness before it
  asks wacli anything, reads the account and the chats now through the lookup a
  send uses (a JID, never a name or number; the name from the mirror), and
  records the terms it showed under a fresh rule key, so no earlier answer ever
  approves another mandate and a mandate never covers the making of another. The
  handler runs only a call the hook decided, reads the account and the chats
  again and refuses when they are no longer the ones on the card, then makes the
  mandate with the end the card showed.
- **`list`** shows the mandates in force and **`revoke`** (`mandate` = its id)
  ends one at once; neither needs a card, because they only narrow what runs
  without one.

A send **fits** a mandate only when it is plain text to one of its chats from
its account, within the length, with no file, no quoted message and no reply,
and the hour's count is not used up. For a send that fits:

1. **The hook** (`approval_request`) asks the mandate store which mandate in
   force the send fits, stores the usual per-call record (the digest of account,
   chat, text, reply and files) together with the mandate's id, returns no
   `approve` directive and skips the no-person refusal. The handler peeks at
   that record to skip it as well; a covered call the hook never decided is
   refused as any send is.
2. **The write** takes the record, checks the digest as it does for a card,
   then — before anything reaches wacli — asks the store again, under its lock,
   whether the mandate is still in force and the send still fits, and counts it.
   The count stands whatever becomes of the request, even when it fails or is
   uncertain, so the hourly bound holds. A send that no longer fits (revoked,
   ended, the count used up, another chat or account) reads
   `not sent: it no longer fits the send mandate (…)` with nothing sent. A
   covered send is text only: it never reaches the files or outbox path.

A send that fits no mandate behaves as before: a card, and a refusal where no
card can be answered; the next send after the hourly bound is such a send.
Files, quotes and replies, other chats and other accounts are never covered.

**State.** In the profile home, `whatsapp-access/` holds `mandates/<id>.json`,
`head.json` (the ids in force; only the head decides), `uses.jsonl` (one opening
row per mandate, then one row per counted send) and `mandates.jsonl` (history,
for the record only). Each is MAC'd, except the history, with a key in the
Keychain item `WHATSAPP_MANDATE_KEY_<PROFILE>` (project `hermes`, scope
`whatsapp-access`, a scope no profile receives), read afresh on every check:
without a readable key nothing is in force and nothing is counted. The MACs stop
an edited or forged mandate, head or row, and a mandate whose opening row is
missing, or a ledger that is deleted, emptied, replaced or not a plain file of
this user (it is opened without following links), counts as used up and says so
(`its send count cannot be read …`). Neither an older head copied back nor use
rows removed from an intact ledger is detected; the [guard](#ways-around-the-tool)
that keeps file and terminal calls off the state and the 30-day ceiling bound
that.

## Ways around the tool

The same hook blocks terminal commands that run `wacli`, and terminal or
file-tool calls whose command, working directory or path names the store, the
sync launcher, agent or log, a `WACLI_` variable or the outbox. Terminal and
file calls naming the send mandates' state in the profile home
(`whatsapp-access/` with `mandates`, `head.json`, `uses.jsonl` or
`mandates.jsonl`, also reached through a link or `..`) or their key
(`WHATSAPP_MANDATE_KEY`) are blocked too; file tools can still read the plugin's
source and these docs. Patterns:
`CLIS` (read by command position, with `_CLI` for a line that cannot be read
that way), `_PATHS`, `_MANDATE_STATE`, `_MANDATE_KEY` and `_ENGINE` in
`plugins/messaging/whatsapp-access/wa.py` (they also keep matching the agent's
earlier names). Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).
Once per account, in a terminal:

1. `brew install openclaw/tap/wacli` (macOS 15 or later).
2. Check that the phone has a free linked-device slot (four at most).
3. `~/.config/hermes/launchd/whatsapp-access-launchctl.sh pair <account> +<number>`
   — stops that account's agent, adds the account if needed, prints a pairing
   code, and waits; on the phone, _Linked devices → Link a device → Link with
   phone number instead_, enter the code. When pairing finishes it installs and
   starts the sync agent. Without `--phone`, `wacli --account <account> auth`
   pairs by QR instead.
4. `whatsapp-access-launchctl.sh status` shows agent state and `wacli doctor`
   for every account; the tool's `status` action shows the same.

Pairing another account needs nothing on the Hermes side.

When WhatsApp revokes the session (the phone unlinked it, or went unused for
weeks), run `pair` again: wacli keeps the dead device record and `auth logout`
cannot connect to clear it, so `pair` moves that account's `session.db` aside
(the message mirror stays) before pairing. `pair` refuses an account that is
still paired. To unpair for good: `uninstall <account>`, then
`wacli --account <account> auth logout`. After a wacli upgrade, `restart
<account>`. After a change to the agent template, run `install <account>` for
each account: `restart` does not render the plist again.
