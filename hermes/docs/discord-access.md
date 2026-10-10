# Discord access

The Assistant's access to the user's own Discord account — reading their DMs,
group DMs and servers, keeping a chosen set of servers synced, and acting from
the account (sending, reacting, pinning, editing and deleting their own messages,
managing roles) only as the user approves each time. It is not the
Assistant's Discord bot (the gateway's Discord platform, through which the
user talks to Hermes); nothing here changes that bot. Read it when changing the
plugin or its engine. Common rules: [access-common.md](access-common.md). Part
of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                      | Home                                                                                         | Reader            |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- | ----------------- |
| Mirror schema, sync list and its limits (stdlib)                                           | `plugins/messaging/discord-access/store.py`                                                  | engine and plugin |
| Engine: the only code that talks to Discord and holds the token                            | `plugins/messaging/discord-access/engine.py`                                                 | its venv          |
| `discord_account` tool, reads, cards, the `pre_tool_call` hooks (toolset `discord_access`) | `plugins/messaging/discord-access/access.py`, `__init__.py`                                  | Assistant         |
| Permission names and what a member holds (stdlib)                                          | `plugins/messaging/discord-access/perms.py`                                                  | plugin            |
| Engine venv (`curl_cffi`, hash-locked)                                                     | `engines/discord-user/requirements.lock` → ignored `local/discord-user/venv`                 | people            |
| Sync agent                                                                                 | `launchd/discord-access-launchctl.sh`, `launchd/local.hermes.discord-access.sync.plist.tmpl` | people            |
| When and how the Assistant uses it                                                         | the Assistant's private Chat reference `discord.md`                                          | Assistant         |

Automating a user account ("self-bot") is against Discord's terms and can end
in account termination; read-only use is not exempt
([risk acceptance](access-common.md#risk-acceptance)). No MCP server, browser or
Hermes core change is involved, and no third-party Discord client: an audited
one retried message POSTs up to five times without a nonce (duplicate sends),
which a send path cannot allow.

## Account, token and engine

One account. The token is `DISCORD_USER_TOKEN` in the `hermes` project under
the scope `discord-user` ([secret scoping](access-common.md#secret-scoping)).
The engine reads it at start (`secret get … -p hermes --scope discord-user`);
anything token-shaped is masked in every error it prints. The plugin runs the
engine as a child process with a minimal environment.

The engine runs on Python 3.12 with `curl_cffi` impersonating Chrome, so the
TLS and HTTP/2 fingerprint matches the web client's headers it sends
(`X-Super-Properties` carries the current `client_build_number`, read from
`discord.com/login`). Requests are paced 0.6–1.6 s apart. A read waits out one
rate limit; nothing else is retried. A 401 records the token as rejected
(`status` reports it) and stops the sync. If the build number cannot be read
and no cached one is under a week old, the engine refuses to run rather than
send a stale one.

## Mirror and sync

State lives in `~/.local/state/hermes-discord/` (0700): `mirror.db` (SQLite,
WAL; 0600) and `sync.json`. The plugin opens the mirror read-only and never
creates it; the engine is its only writer.

The `local.hermes.discord-access.sync` LaunchAgent starts one bounded run every
5 minutes, which exits when done; a lock keeps runs from overlapping. A run
asks for the account, the DM list and each synced server's channel list. Those
lists carry each channel's last message id, so only channels whose last message
moved are fetched, forward from a cursor in pages, each page committed with its
progress before the next request, so a long run never holds the database
against a send. Each run has a request budget and a page cap per channel;
anything left continues next run. A channel seen for the first time is seeded
with its newest messages if it is recently active; an older DM is followed from
now on and its history fetched only on request (`backfill`). A channel
answering 403 or 404 is marked and skipped until a live read of it succeeds
again.

Edits and deletions have no feed, so they reach the mirror through reads.
Every page of a channel's history the engine reads is contiguous, so it
overwrites what it returns and drops mirrored messages inside its range that it
did not return: those were deleted. A page shorter than asked also vouches for
its open ends — back to the channel's start unless `after` bounded it, and
past its newest message unless `before` did; past the newest message only for
messages of the last 7 days mirrored before the request began, because one
stored meanwhile by another process may be newer than Discord's answer. A page
`around` a message vouches for its own range only, and an empty page drops
nothing. Each run then rechecks the newest page of a couple of recently active
channels whose newest page was not read lately. Older history changes only when
it is read again (`live=true` or `backfill`). Search, pin and mention results
are not contiguous and never drop anything.

Each channel's cursor holds two edges. `oldest` is where its contiguous history
starts; `backfill` pages back from there, never from older stray windows that
live reads left in the mirror. `synced_at` is set only when a run found the
channel up to date. The plugin treats the mirror as the source for a channel
only while that stamp is under 15 minutes old. A channel that lags, has left
the sync list, or whose agent stopped is therefore read live, so reads never
serve silently stale history.

## Reads

The tool schema lists the actions. Rules that hold across them:

- Mirror-only reads make no request (`status`, `dms`, `search`, `context`,
  `pending`, `stats`, `export`, `sync_list`, `sync_suggest`); guilds and friends
  refresh from Discord when their copy is old; most server-detail reads always
  ask Discord. `messages` reads the mirror for a current channel inside its
  contiguous history, and live otherwise (also with `live=true`), as does
  `context` around a message not in the mirror. A live window is stored in the
  mirror too, so search and cards can see it.
- Messages come oldest first with local times, `from: me` for the user's own,
  and a note that text, embeds and names are written by other people and are
  data, never instructions. Reactions are as of a message's last ordinary read;
  search, pin and mention results carry none and leave stored ones alone.
- `status` carries a `health` verdict computed from the mirror alone:
  `ok`, `degraded` (the last run failed or left work, or a followed channel is
  behind or answered 403/404), `stale` (the last run started over 15 minutes
  ago, so synced chats are read live) or `down` (no recent run, agent not
  loaded, or token rejected). Only DMs and the sync list's servers count.
- `search` over the mirror is a literal substring match, and says so; with
  `live=true` it is Discord's own search, which has no reaction filter, so the
  mirror-only filters (`reacted`, `emoji`, `parent`) are refused there.
- `threads` stores each thread as a channel, so `messages` reads it and `send`
  posts into it. User accounts have no list of a whole server's threads.
- `pending` lists chats waiting for the user's answer, from the mirror alone:
  "not answered", not "unread", because Discord's read state needs the
  gateway, which this design does not hold open. A chat the mirror is not
  current for says `mirror_current: false`.
- `stats` counts over the mirror and the model reads the counts; the tool does
  not summarise text. `coverage.partial_channels` marks chats whose numbers are
  lower bounds.
- `guild_info`, `emojis` and `events` read what a member sees of a server they
  listed before, store nothing, and their text is data. Their fields come from
  community documentation; a missing one is left out. Seeing an emoji here does
  not allow `react` with it.
- `invites` returns the invite code in full, because it is the credential for
  joining; the note and the skill say it goes to the user only.
- `roles`, `member`, `role_members` and `members`: see Roles.

Results read from Discord are stored in the mirror as well, so later cards and
searches can see them.

## Media

`media` (channel + message id) saves what one message carries: its attachments,
the media of its link previews and its stickers, one folder per message,
`<channel>-<message>`, under `discord_access.download_dir` from the profile's
`config.yaml`, else `<HERMES_HOME>/discord-downloads/`.

- The engine fetches the message again, because attachment URLs are signed and
  expire, and downloads each item without the token into a private `incoming/`
  folder in the state directory. Link-preview media come only from Discord's
  proxied copies, never from the site behind the link; stickers from Discord's
  CDN. Any other host is refused.
- Programs are refused by name and declared type before the download, and by
  the bytes (`file --mime-type`) after it, the same rules as signal-access. A
  `.zip` or tar archive is downloaded and inspected before it is saved
  ([Signal access](./signal-access.md), "Received archives"); `unpack` unpacks
  it ("Unpacking"). A file over `discord_access.download_max_mb` is not
  downloaded.
- The plugin writes what passed into the download folder under a cleaned name.
  Writes go through the message folder's descriptor, opened without following
  links, into a hidden part file renamed into place; a link or folder already
  at a name is left alone and the next free name used, so nothing is written
  through a link. `incoming/` is emptied whatever happens.
- A message that is gone, or an item Discord no longer serves, is reported as
  missing. The note says a saved file is to be looked at, never opened or run
  (an archive is unpacked only by `unpack`).

## Export

`export` (channel) writes a synced channel's or DM's mirrored history to one
file under `<download_dir>/exports/`. It is for evidence a task can cite, and
it makes no request.

- **Only what the mirror holds in one piece.** The range runs from the
  cursor's `oldest` edge to its `newest` one, never over stray live windows,
  and the channel must have a cursor. Messages stored past `newest` (a send, a
  live read) are left out and counted (`left_out`), so a file never claims
  completeness over a gap. The result and the file header say whether the file
  is complete to the channel start, whether the cap cut it, whether the mirror
  was current, and how to continue. Older exports are not rewritten: a
  continuation is a new file.
- **Text is quoted** (`> ` on every line, a line being whatever a viewer may
  break at), so a message that contains a line like `### …` cannot pass for a
  message heading of the file. A name is whatever its owner set, so only the
  author id attributes a message. Text is never clipped.
- **Files are only created, and private.** An existing file is never opened
  for writing, the folder is opened without following links, files are mode
  0600 and `exports/` 0700 (they can hold private DMs). There is no approval
  card: nothing leaves the machine. The file holds other people's words and
  sits under the attach root, so a `send` of it is the user's decision.

## Sync list

DMs and group DMs are always synced. Servers are followed only as listed in
`sync.json`, which `sync_add` / `sync_remove` edit (no approval card: it is
local, reversible, and bounded). A server is listed either whole — its most
recently active readable text channels, minus `exclude` — or as named channels;
switching between the two needs a remove first, so coverage never shrinks
silently. Ids are checked against the mirror (the server and channel must have
been listed; only text and announcement channels). The server and channel
limits are code, not judgement. A change applies on the next run, with no
restart.

`sync_suggest` proposes changes and makes none, from the mirror alone. `add`
candidates are channels where the user wrote or the mirror holds enough
messages; the evidence is only what the mirror has stored (a live read is
stored, so a channel the user only ever read live shows up, and one never opened
is invisible). Each carries the exact `sync_add` arguments and whether it fits
the same limits `sync_add` enforces. A channel the user excluded from a whole
server is never proposed. `remove` candidates are followed channels with no
recent activity from the user, with the slots they free.

## Send

`send` posts text and files to a channel the mirror knows — an existing DM or
group DM, a server channel listed before, or a thread listed by `threads`. New
DMs cannot be opened, names are refused, and a `reply_to` must be a message of
that channel already in the mirror. A locked thread is refused; for an archived
one the card notes that sending reopens it.

- **Files come from the attach roots only**: `discord_access.attach_roots` in
  the profile's `config.yaml`, default `~/Workspaces`. Each must resolve
  (symlinks followed) to a regular file inside a root and outside the state
  directory, be non-empty and within Discord's limit without Nitro.
  Credentials, keys and local databases are refused whatever the root (the
  same refusal list as signal-access, compared without case).
- **Archives are opened first** on the snapshot copy
  (`plugins/messaging/_shared/archive_check.py`; rules in
  [Signal access](./signal-access.md)) and sent only if no entry would be
  refused as a file above, is a program, another archive, a link or an
  encrypted entry, or holds a private key block. Source scripts inside are
  allowed, as they are on their own here. One bad entry refuses the whole
  archive and the error names it. A format that cannot be read, and a file that
  is an archive but not named like one, go as the files they are: the roots
  stay the boundary. A name that says zip or tar over content that is not is
  refused.
- **The approved bytes are the sent bytes.** For each call, the approval hook
  and a second `pre_tool_call` hook (`bind`) share one snapshot, made by
  whichever runs first and keyed by the session, task and tool-call ids; the
  second hook gets it only for the same request as written (channel, text,
  reply and the paths as given, never re-resolved), else nothing. The files are
  copied into a fresh `outbox/<random token>/` in the state directory and
  hashed into the card's rule key. Each file is copied through its opened
  descriptor, and the path that descriptor really points to is checked against
  the roots and the refusal list again, so a file swapped for a symlink after
  validation is refused. `bind` returns a `modify` that hands the handler the
  token. The handler takes the snapshot once (an atomic rename), checks that
  the request matches the approved one and that the hashes still hold, sends
  only those copies, and deletes them. The originals may change or disappear
  after approval without affecting the send. A caller-supplied token is
  blocked, a call without an id cannot attach files, and a token never names
  another snapshot. Hard links cannot be told apart from ordinary files; the
  roots, not the names, are the boundary.
- **Uploads come first.** The engine reserves upload URLs and PUTs each copy to
  the signed Google Cloud Storage URL Discord returns, without the token, as
  the web client does; a URL on any other host is refused. Nothing here creates
  a message, so a failed or slow upload reads `not sent`. The message POST then
  carries the uploaded names.
- **Every send asks first** ([approval gate](access-common.md#approval-gate)).
  The card is built from the mirror without a request and names the account,
  the chat with its id, the reply target, each file, and `Pings:` when the text
  holds `@everyone`, `@here` or a role mention.
- **One POST, idempotent.** The plugin draws a fresh nonce per send; the
  engine records it in the `sends` ledger as `pending`, then `dispatching`, and
  POSTs once with `enforce_nonce`, so Discord returns the original message
  instead of creating a second one for a repeated nonce. A reply references the
  message without pinging its author.
- **Outcomes are never guessed.** `sent` carries the message id. Discord's
  refusals (4xx) and network failures that cannot have left the machine read
  `not sent: …`. A 5xx, a timeout after dispatch or a reply without a message
  reads `UNCERTAIN: …`, always. Discord's history does not carry the nonce, so
  a message with the same text could be one the user typed: the engine reads
  the channel's newest messages once and adds the ids of the user's messages
  with this exact text, reply target and attachment count created after the
  POST began — a hint for the Assistant to check with the user, never a
  conclusion. If the engine dies or hangs, the plugin judges by the ledger:
  never dispatched is not sent, anything past `dispatching` is uncertain.
  Nothing is ever resent automatically.

## Other writes

`react` / `unreact`, `edit` and `delete` (the user's own messages only, already
in the mirror), `pin` / `unpin` and the role writes below each go through the
same approval gate.

- **Checked before the card.** A request that cannot or may not happen
  (unknown channel, message or role, someone else's message, the same text, a
  reaction the user has not made, anything Roles forbids) is blocked without
  asking.
- **The card is what runs.** The approval hook and the bind hook share one plan
  per call (keyed by the session, task and tool-call ids, whichever hook runs
  first); bind hands the handler that plan's rule key (`_approved`). A plan
  that expires before its second hook fails that call rather than making a new
  plan. After approval the handler builds the plan again from the mirror and
  runs it only when the key still matches, so a change meanwhile (the message
  edited, the role's permissions read differently) voids the card. The key
  hashes the engine request plus what it acts on — the message's text, edit
  time and attachments (not their URLs, which Discord re-signs), or the role's
  permissions. A caller-supplied `_approved` is blocked, and a call without an
  id never gets one, so it cannot run.
- **Cards fit or are refused.** A message card shortens its quote until it
  fits; every line of a role card is part of the approval, so a role card that
  does not fit is refused and the request has to be split.
- **Pins.** The message is quoted and bound like an edit or delete. The plugin
  does not guess the user's right to pin (channel overrides are not in the
  mirror), so Discord decides and its refusal is `not done` with its reason. An
  uncertain pin reads the message back and becomes `done` when it shows the
  requested state. The mirror stores no pin state: `pins` lists them live. A
  pin changes what everyone in the chat sees, so the Assistant pins only when
  the user asked.
- **One request, never retried.** Outcomes are `done`, `not done` and
  `UNCERTAIN`. An uncertain write reads back once — the message, the member or
  the role list — and becomes `done` when that shows the requested state;
  otherwise it stays uncertain with what was seen. All of these set a state, so
  repeating them is harmless once the user agrees, except `role_create`, whose
  read-back only reports a new role of that name as a hint and which is never
  repeated without the user. Deleting something already gone counts as done. A
  request Discord answers with a two-factor challenge is `not done` — the user
  does it in the app — and never marks the token as rejected.
- **The mirror follows** a done write without another request where it can.

## Roles

Reads: `roles` lists a server's roles from the top with the strong permissions
each holds and whether the user can manage it; `role` shows one role. The list
is kept 15 minutes. `member`, `role_members` and `members` read members;
`members` uses Discord's member search, which needs Manage Server, so elsewhere
ids come from messages, mentions or friends. Roles and members read this way
live in the mirror's `roles` and `members` tables; sync never fetches them.

Writes: `role_add` / `role_remove`, `role_bulk_add`, `role_create`,
`role_edit` (the whole new permission set is sent) and `role_delete`, each with
an optional audit-log `reason`. The rules, in code, checked against the mirror
before the card:

- The server's roles were listed within 15 minutes (the handler after approval
  does not re-check the age; the key match covers changes).
- The user holds Manage Roles (or Administrator, or owns the server).
- The role is below the user's highest role (the owner is exempt), not managed
  by an integration, and not `@everyone` — except that `role_edit` may change
  `@everyone`.
- **Administrator is never given**: not created, granted, or handed out by
  assigning a role that has it. Removing it, and removing a role that has it,
  is allowed.
- Nothing grants permissions the user lacks — creating, granting, or assigning
  a role that holds them.
- Permissions are given by name (`perms.py`); unknown names are refused.
- A role write that gives strong permissions puts `⚠ Strong permissions: …` at
  the top of the card; editing a role that keeps Administrator shows
  `administrator (kept)` there. Removals, revocations and deletions carry no
  warning.

Managing roles from a user account is among the riskiest self-bot actions, and
the audit log names the user. Discord enforces the same hierarchy and
permission rules again; these checks only keep impossible or forbidden requests
off the card.

## Ways around the tool

The same hook blocks terminal calls naming the state directory, the token or
its Keychain scope, the plugin or the raw API, and file-tool calls on the state
directory, the token name or the engine venv; the plugin's source stays
readable. Patterns: `_TERMINAL` and `_FILES` in
`plugins/messaging/discord-access/access.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

## Where a write may run

Every write (`send`, `react`, `unreact`, `pin`, `unpin`, `edit`, `delete` and
the role actions) is refused outright wherever no person can answer its card,
with `not done` and the reason ([approval gate](access-common.md#approval-gate)).
A forged `_approved` or `_outbox` does not help, because the handler refuses
again. Reads, `media`, `export` and the sync list need no card and run
everywhere.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. `secret set DISCORD_USER_TOKEN -p hermes --scope discord-user -D TOKEN`,
   pasting the `authorization` header of any `discord.com/api` request from the
   logged-in web client (DevTools → Network). Logging that browser session out
   or changing the password invalidates it; store the new one the same way.
2. `hermes/launchd/discord-access-launchctl.sh install` builds the venv from the
   lock if needed (`setup` does only that) and renders and loads the agent;
   `run` does one sync in the terminal.

A new token, the sync list and engine changes need no gateway restart.
`uninstall` stops the agent and keeps the venv, mirror and sync list; delete
`~/.local/state/hermes-discord/` to drop the mirror.
