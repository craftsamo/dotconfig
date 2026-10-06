# Discord access

The Assistant's access to the user's own Discord account — reading their DMs,
group DMs and servers, keeping a chosen set of servers synced, and acting from
the account (sending, reacting, editing and deleting their own messages,
managing roles) only as the user approves each time. It is not the
Assistant's Discord bot (the gateway's Discord platform, through which the
user talks to Hermes); nothing here changes that bot. Part of the Hermes
design docs — index: [`PROFILES.md`](../PROFILES.md).

Automating a user account ("self-bot") is against Discord's terms and can end
in account termination; read-only use is not exempt. The user accepted that
risk, so the design keeps traffic low and client-like rather than pretending
the risk away.

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

No MCP server, browser or Hermes core change is involved, and no third-party
Discord client: an audited one retried message POSTs up to five times without
a nonce (duplicate sends), which a send path cannot allow.

## Account, token and engine

One account. The token lives only in the Keychain, as `DISCORD_USER_TOKEN` in
the `hermes` project under the scope `discord-user`. Hermes only ever receives
shared layers: `profile-secrets.sh` and the tool-mode `secret-shim` (which
launches `hermes`) both pin `--scope <project>`, so a repository scope never
follows the working directory in. The token therefore never enters any
profile's secret scope, the gateway process or a CLI session, and replacing it
needs no gateway restart. The engine reads it at start
(`secret get … -p hermes --scope discord-user`), and never writes, prints or
logs it; errors are
scrubbed of it, and anything token-shaped is masked in every error the engine
prints. The plugin runs the engine as a child process with
a minimal environment (none of the gateway's keys).

The engine runs on Python 3.12 with `curl_cffi` impersonating Chrome, so the
TLS and HTTP/2 fingerprint matches the headers it sends: the web client's
(`/api/v9`, raw `Authorization`, `X-Super-Properties` for Chrome on macOS with
the current `client_build_number` read from `discord.com/login` every 12
hours, locale from the account, timezone from the system, a launch identity
kept for 24 hours). Requests in one process are paced 0.6–1.6 s apart. A read
waits out one rate limit of up to 30 s; nothing else is retried. A 401 records
the token as rejected (`status` reports it) and stops the sync. If the build
number cannot be read and no cached one is under a week old, the engine
refuses to run rather than send a stale one.

## Mirror and sync

State lives outside every repository in `~/.local/state/hermes-discord/`
(0700): `mirror.db` (SQLite, WAL; 0600) and `sync.json`. The plugin opens the
mirror read-only and never creates it; the engine is its only writer.

The `local.hermes.discord-access.sync` LaunchAgent starts one bounded run every 5
minutes (`StartInterval`), which exits when done; a lock keeps runs from
overlapping. A run asks for the account, the DM list and, for each server on
the sync list, its channel list. Those lists carry each channel's last
message id, so only channels whose last message moved are fetched, forward
from a cursor in pages of 100 (`after` returns the messages directly after the
cursor), each page committed with its progress before the next request, so a
long run never holds the database against a send. A quiet run is two
requests, plus at most two rechecks (below). Bounds: 60 requests per run,
counted before each request (retries and the build-number page included),
and 5 pages per channel per run; anything left continues next run. A
channel seen for the first time is seeded with its newest 50 messages if its
last message is under 30 days old (at most 15 per run); an older DM is
followed from now on, its history fetched only on request (`backfill`). A
channel answering 403 or 404 is marked and skipped by later runs (DMs
included) until a live read of it succeeds again.

Edits and deletions have no feed, so they reach the mirror through reads.
Every page of a channel's history the engine reads (sync, live windows,
backfill, the message `media` or a write reads again) is contiguous, so it overwrites what
it returns and drops mirrored messages inside its range that it did not
return: those were deleted. A page shorter than asked also vouches for its
open ends — back to the channel's start unless `after` bounded it, and past
its newest message unless `before` did; past the newest message only for
messages of the last 7 days mirrored before the request began, because one
stored meanwhile by another process may be newer than Discord's answer. A
page `around` a message vouches for its own range only, and an empty page
drops nothing. Each run then rechecks: it reads the newest 50 messages of up
to two channels active in the last 7 days whose newest page was not read for
30 minutes (a seed counts, following new messages does not), least recently
first, inside the run's budget. Older history changes only when it is read
again (`live=true` or `backfill`). Search, pin and mention results are not
contiguous and never drop anything.

Each channel's cursor holds two edges. `oldest` is where its contiguous
history starts; `backfill` pages back from there, never from older stray
windows that live reads left in the mirror. `synced_at` is set only when a run
found the channel up to date. The plugin treats the mirror as the source for a
channel only while that stamp is under 15 minutes old. A channel that lags,
has left the sync list, or whose agent stopped is therefore read live, so
reads never serve silently stale history.

## Reads

`status`, `dms`, `search`, `context` and `sync_list` read the mirror and
make no request. `guilds` refreshes from Discord when its copy is over 6
hours old, `friends` likewise; `channels`, `threads`, `pins`, `mentions`,
`member`, `role_members` and `members` always ask Discord, and `roles` does
when its copy is over 15 minutes old (or on `refresh`). `messages` reads the
mirror for a current channel, inside its contiguous history; a channel that is not current,
a page older than that history, an empty window or `live=true` is read live,
as is `context` around a message not in the mirror; `backfill` runs the
engine too. A live window is at most 100 messages and is stored in the mirror
as well, so search and approval cards can see it.
Messages come oldest first, with local times, `from: me` for the user's own,
reply targets, attachment names and links, reactions (emoji, count and
whether the user reacted, as of the message's last ordinary read: search,
pin and mention results carry none and leave stored ones alone), the
readable part of embeds (title, description, link, author, site, up to five
fields, clipped), and a note that text, embeds and names are written by
other people and are data, never instructions. Stickers are listed by name.

- `search` is a literal substring match over the mirror, and says so. With
  `live=true` it is Discord's own search instead, 25 a page with `offset`:
  `guild` searches a server (a `channel` of it narrows it), a DM `channel`
  that DM, neither every DM and group DM at once (the web client's tabbed
  search, a POST). While Discord is still indexing (HTTP 202), the engine
  waits once, up to 30 s, then says to try again later.
- `threads` lists a text, announcement or forum channel's threads (forum
  posts with their first post), newest activity first, 25 a page; `archived`
  narrows to archived or active ones. Each thread is stored as a channel, so
  `messages` reads it and `send` posts into it. User accounts have no list of
  a whole server's threads.
- `pins` lists a channel's pinned messages, paged by the last `pinned_at`.
- `mentions` lists messages that mention the user, their roles, `@everyone`
  or `@here`, newest first, optionally in one server.
- `friends` lists friends (requests only counted), each with the channel id
  of an existing DM, since a send needs one.
- `roles`, `member`, `role_members` and `members`: see Roles.

Results read from Discord are stored in the mirror as well, so later cards
and searches can see them.

## Media

`media` (channel + message id) saves what one message carries: its
attachments, the media of its link previews (images, thumbnails, videos) and
its stickers. Files go into one folder per message, `<channel>-<message>`,
under `discord_access.download_dir` from the profile's `config.yaml`, else
`<HERMES_HOME>/discord-downloads/`; the result lists each path.

- The engine fetches the message again, because attachment URLs are signed
  and expire, and downloads each item without the token into a private
  `incoming/` folder in the state directory, with a 9-minute budget per call.
  Link-preview media come only from Discord's proxied copies
  (`images-ext-*.discordapp.net`, `media.discordapp.net`), never from the
  site behind the link; stickers from Discord's CDN (PNG, GIF or Lottie
  JSON). Any other host is refused.
- Archives and programs are refused by name and declared type before the
  download, and by the bytes (`file --mime-type`) after it, the same rules as
  signal-access. A file over `discord_access.download_max_mb` (default 100, at
  most 500) is not downloaded, and the size is reported where known.
- The plugin writes what passed into the download folder under a cleaned
  name (`a.txt`, `a-2.txt` for a repeat; a shortened name keeps its
  extension, and the final name is checked against the same rules). Writes
  go through the message folder's descriptor, opened without following links,
  into a hidden part file renamed into place; a link or folder already at a
  name is left alone and the next free name used, so nothing is written
  through a link. `incoming/` is emptied whatever happens; leftovers
  from a crash expire after a day. Saving the same message again overwrites
  its folder's files.
- A message that is gone, or an item Discord no longer serves, is reported as
  missing. The note says a saved file is to be looked at, never opened, run
  or unpacked.

## Sync list

DMs and group DMs are always synced. Servers are followed only as listed in
`sync.json`, which `sync_add` / `sync_remove` edit (no approval card: it is
local, reversible, and bounded). A server is listed either whole — its 10 most
recently active readable text channels, minus `exclude` — or as named
channels; switching between the two needs a remove first, so coverage never
shrinks silently. Ids are checked against the mirror (the server and channel
must have been listed; only text and announcement channels). The limits are
code, not judgement: at most 10 servers and 30 channels, a whole server
counting as 10. A change applies on the next run, with no restart.

## Send

`send` posts text (at most 2000 characters) and up to 10 files to a channel
the mirror knows — an existing DM or group DM, a server channel listed
before, or a thread listed by `threads`. New DMs cannot be opened, names are
refused, and a `reply_to` must be a message of that channel already in the
mirror. A locked thread is refused; for an archived one the card notes that
sending reopens it.

- **Files come from the attach roots only**: `discord_access.attach_roots` in
  the profile's `config.yaml`, default `~/Workspaces`, with a relative path
  taken from the first root. Each must resolve (symlinks followed) to a regular
  file inside a root and outside the state directory, be non-empty and at most
  10 MB (the limit without Nitro). Credentials, keys and local databases are
  refused whatever the root: `.env*`, `*.pem`, `*.key`, `id_*` keys, `*.db`,
  `*.sqlite`, `*.keychain*` and anything with `.git`, `.ssh`, `.gnupg`,
  `.aws`, `.config` or `Keychains` anywhere in its real path, compared without
  case. A message may be files alone.
- **Archives are opened first.** A `.zip`, `.tar`, `.tar.gz`/`.tgz`,
  `.tar.bz2` or `.tar.xz` is read entry by entry on the snapshot copy
  (`plugins/messaging/_shared/archive_check.py`; rules and limits in
  [Signal access](./signal-access.md)) and sent only if no entry would be
  refused as a file above, is a program (`.exe`, `.app`, `.jar`, … or an ELF,
  Mach-O or PE file), is another archive, a link or an encrypted entry, or
  holds a private key block. Source scripts inside are allowed, as they are
  on their own here. One bad entry refuses the whole archive and the error
  names it; the card adds the file count to the archive's line. An archive
  format that cannot be read (`.rar`, `.7z`, a bare `.gz`, …), and a file
  that is an archive but not named like one, are not opened and go as the
  files they are, as before: the roots stay the boundary. A name that says
  zip or tar over content that is not is refused.
- **The approved bytes are the sent bytes.** For each call, the approval hook
  and a second `pre_tool_call` hook (`bind`) share one snapshot, made by
  whichever runs first and keyed by the session, task and tool-call ids; the
  second hook gets it only for the same request as written (channel, text,
  reply and the paths as given, never re-resolved), else nothing. The
  files are copied into a fresh `outbox/<random token>/` in the state
  directory and hashed into the card's rule key. Each file is copied through
  its opened descriptor, and the path that descriptor really points to is
  checked against the roots and the refusal list again, so a file swapped for
  a symlink after validation is refused. `bind` returns a `modify` that hands
  the handler the token. The handler takes the snapshot once (an atomic
  rename), checks that the text, reply and requested paths match the approved
  request and that the hashes still hold, sends only those copies, and
  deletes them. The originals may change or disappear after approval without
  affecting the send. A caller-supplied token is blocked, a call without an
  id cannot attach files, a token never names another snapshot, and copies
  left by a denied card expire after a day. Hard links cannot be told apart
  from ordinary files; the roots, not the names, are the boundary.
- **Uploads come first.** The engine reserves upload URLs
  (`POST /channels/{id}/attachments`) and PUTs each copy to the signed Google
  Cloud Storage URL Discord returns, without the token, as the web client does;
  a URL on any other host is refused. Uploads share a 10-minute budget; the
  plugin waits 14 minutes for any send with files. Nothing here creates a message, so
  a failed or slow upload reads `not sent`. The message POST then carries the uploaded
  names.

- **Every send asks first.** The hook sends it through Hermes' approval gate,
  as whatsapp-access does. The card, built from the mirror without a request:

  ```
  Discord: <account name> (@<username>)
  To: DM with <name> (@<handle>)  |  group DM … | #<channel> in <server> | thread '<name>' in #<parent> in <server>
  Channel id: <id>
  Reply to: <sender>: <quoted text>
  Files (2): docs/report.pdf (1.2 MB), photo.png (340.0 KB)
  Pings: @everyone
  Note: the thread is archived; sending reopens it

  <message text>
  ```

  `Pings` appears only when the text holds `@everyone`, `@here` or a role
  mention. Names and quotes are collapsed to one line and hidden characters
  are spelled out; the text is cut on the card past about 350 characters and
  the rest counted. `Files` names each file by its path under its root, clipped
  to about 160 characters with the rest counted. The allowlist key hashes the
  channel, text, reply and file contents, so "session" or "always" only ever
  repeats that identical message.

- **One POST, idempotent.** The plugin draws a fresh nonce per send; the
  engine records it in the `sends` ledger as `pending`, then `dispatching`,
  and POSTs once with `enforce_nonce`, so Discord returns the original message
  instead of creating a second one for a repeated nonce. A reply references
  the message without pinging its author.
- **Outcomes are never guessed.** `sent` carries the message id. Discord's
  refusals (4xx: permissions, a captcha, a rate limit) and network failures
  that cannot have left the machine read `not sent: …`. A 5xx, a timeout after
  dispatch or a reply without a message is ambiguous and reads
  `UNCERTAIN: …`, always. Discord's history does not carry the nonce, so a
  message with the same text could be one the user typed. The engine reads
  the channel's newest 10 messages once and adds what it saw to the detail:
  the ids of the user's messages with this exact text, reply target and number
  of attachments, created after the POST began (2 s clock allowance). That is a hint for the
  Assistant to check with the user, never a conclusion. If the engine dies or
  hangs, the
  plugin judges by the ledger: never dispatched is not sent, anything past
  `dispatching` is uncertain. Nothing is ever resent automatically.
- Inbound A2A requests never reach the account; the toolset is not in the
  Assistant's `a2a` platform toolset either.

## Other writes

`react` / `unreact` (one Unicode emoji, or a custom emoji already on that
message), `edit` and `delete` (the user's own messages only, already in the
mirror) and the role writes below each go through the same approval gate.

- **Checked before the card.** A request that cannot or may not happen
  (unknown channel, message or role, someone else's message, the same text,
  a reaction the user has not made, anything Roles forbids) is blocked
  without asking.
- **The card is what runs.** The approval hook and the bind hook share one
  plan per call (keyed by the session, task and tool-call ids, whichever hook
  runs first); bind hands the handler that plan's rule key (`_approved`). A
  plan that expires (2 minutes) before its second hook fails that call rather
  than making a new plan. After approval the handler builds the plan again
  from the mirror and runs it only when the key still matches, so a change
  meanwhile (the message edited, the role's permissions read differently)
  voids the card. The key
  hashes the engine request plus what it acts on — the message's text, edit
  time and attachments (name, size and type; not their URLs, which Discord
  re-signs) for an edit or delete, the role's permissions for an
  assignment, edit or deletion — so "session" or "always" only repeats that
  identical request. A caller-supplied `_approved` is blocked, and a call
  without an id never gets one, so it cannot run.
- **Cards fit or are refused.** A message card shortens its quote until it
  fits (an edit keeps room for the new text, cut and counted past about 350
  characters as a send's is); every line of a role card is part of the
  approval, so a role card that does not fit is refused and the request has
  to be split.
- **Cards:** `In:` the chat, `Message:` its sender and text with
  `React with:` / `Remove my reaction:`; `Edit my message` with `Before:`, `Pings:`
  and the new text; `Delete my message:` with "This cannot be undone."
- **One request, never retried.** Outcomes are `done`, `not done` (Discord
  refused, or it cannot have left the machine) and `UNCERTAIN` (a 5xx, or a
  failure after dispatch). An uncertain write reads back once — the message,
  the member or the role list — and becomes `done` when that shows the
  requested state; otherwise it stays uncertain with what was seen. All of
  these set a state, so repeating them is harmless once the user agrees,
  except `role_create`, whose read-back only reports a new role of that name
  as a hint and which is never repeated without the user. Deleting a message
  or role that is already gone (codes 10008, 10011) counts as done. If the
  typed reaction-removal route is unknown (404, code 0), the legacy route,
  which sets the same state, is tried once. A request Discord answers with a
  two-factor challenge (401, code 60003) is `not done` — the user does it in
  the app — and never marks the token as rejected.
- **The mirror follows** a done write without another request where it can
  (the user's reaction counted, the edited text stored, the message or role
  dropped, the member's roles updated).

## Roles

Reads: `roles` lists a server's roles from the top (position, member count,
colour, the strong permissions each holds, whether the user can manage it)
and the user's own roles and permissions; `role` shows one role with all its
permissions. It costs three requests (roles, member counts, the user's own
member; plus the server list once to learn whether the user owns it) and is
kept 15 minutes. `member` reads one member's name and roles; `role_members`
up to 100 member ids of a role (Discord lists no more); `members` finds
members by name through Discord's member search, which needs the Manage
Server permission — elsewhere ids come from messages, mentions or friends.
Roles and members read this way live in the mirror's `roles` and `members`
tables; sync never fetches them.

Writes: `role_add` / `role_remove` (one member), `role_bulk_add` (up to 30
members, reporting who got the role), `role_create`, `role_edit` (name,
colour, hoist, mentionable, `grant` / `revoke` permission names; the whole new
permission set is sent) and `role_delete`, each with an optional `reason`
sent as the audit-log reason. The rules, in code, checked against the mirror
before the card:

- The server's roles were listed within 15 minutes (the handler after
  approval does not re-check the age; the key match covers changes).
- The user holds Manage Roles (or Administrator, or owns the server), from
  `@everyone` (whose id is the server's), their roles and ownership.
- The role is below the user's highest role (the owner is exempt), not
  managed by an integration, and not `@everyone` — except that `role_edit`
  may change `@everyone`.
- **Administrator is never given**: not created, granted, or handed out by
  assigning a role that has it. Removing it, and removing a role that has it,
  is allowed.
- Nothing grants permissions the user lacks — creating, granting, or
  assigning a role that holds them.
- Permissions are given by name (`perms.py`); unknown names are refused.
- A role write that gives strong permissions (ban, kick, manage server,
  roles, channels, webhooks, messages, nicknames, expressions, events or
  threads, timeouts, `@everyone` mentions, the audit log, pins) — creating a
  role with them, granting them, or assigning a role that holds them — puts
  `⚠ Strong permissions: …` at the top of the card; editing a role that
  keeps Administrator shows `administrator (kept)` there. Removals,
  revocations and deletions carry no warning.

```
⚠ Strong permissions: manage_messages
Discord: <account name> (@<username>)
Server: <server>
Action: add role @<role> to <name> (@<username>)
Role id: <id>
User id: <id>
Reason (audit log): <reason>
```

Managing roles from a user account is among the riskiest self-bot actions,
and the audit log names the user. Discord enforces the same hierarchy and
permission rules again; these checks only keep impossible or forbidden
requests off the card.

## Ways around the tool

The same hook blocks terminal calls that name the state directory
(`hermes-discord`, the outbox and `incoming/` included), the token or its Keychain scope
(`DISCORD_USER_TOKEN`, `discord-user`), the plugin (`discord-access`) or the raw API
(`discord.com/api`), and file-tool calls on the state directory, the token
name or the engine venv; the plugin's source stays readable. It is a pattern
match on the call's text, not a sandbox: the approval gate is a guarantee for
the tool and a policy for everything else.

## Setup

Once, in a terminal:

1. `secret set DISCORD_USER_TOKEN -p hermes --scope discord-user -D TOKEN`, pasting the
   `authorization` header of any `discord.com/api` request from the logged-in
   web client (DevTools → Network). Logging that browser session out or
   changing the password invalidates it; store the new one the same way.
2. `hermes/launchd/discord-access-launchctl.sh install` — builds the venv from
   the lock if needed (`setup` does only that), renders and loads the agent.
   `run` does one sync in the terminal; `status` shows the venv, whether the
   token is present (never its value), the agent and the last run.
3. Enabling the plugin or changing its code needs a gateway restart; a new
   token, the sync list and engine changes do not.

`uninstall` stops the agent and keeps the venv, mirror and sync list; delete
`~/.local/state/hermes-discord/` to drop the mirror. After changing
`engines/discord-user/requirements.lock`, run `setup` again.
