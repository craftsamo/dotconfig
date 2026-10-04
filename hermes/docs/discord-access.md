# Discord access

The Assistant's access to the user's own Discord account — reading their DMs,
group DMs and servers, keeping a chosen set of servers synced, and sending text
that the user approves first. It is not the Assistant's Discord bot (the
gateway's Discord platform, through which the user talks to Hermes); nothing
here changes that bot. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

Automating a user account ("self-bot") is against Discord's terms and can end
in account termination; read-only use is not exempt. The user accepted that
risk, so the design keeps traffic low and client-like rather than pretending
the risk away.

## Shape

| Piece | Home | Reader |
|---|---|---|
| Mirror schema, sync list and its limits (stdlib) | `plugins/discord-access/store.py` | engine and plugin |
| Engine: the only code that talks to Discord and holds the token | `plugins/discord-access/engine.py` | its venv |
| `discord_account` tool, reads, card, the `pre_tool_call` hook (toolset `discord_access`) | `plugins/discord-access/access.py`, `__init__.py` | Assistant |
| Engine venv (`curl_cffi`, hash-locked) | `engines/discord-user/requirements.lock` → ignored `local/discord-user/venv` | people |
| Sync agent | `launchd/discord-user-launchctl.sh`, `launchd/local.discord-user.sync.plist.tmpl` | people |
| When and how the Assistant uses it | the Assistant's private Chat reference `discord.md` | Assistant |

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

The `local.discord-user.sync` LaunchAgent starts one bounded run every 5
minutes (`StartInterval`), which exits when done; a lock keeps runs from
overlapping. A run asks for the account, the DM list and, for each server on
the sync list, its channel list. Those lists carry each channel's last
message id, so only channels whose last message moved are fetched, forward
from a cursor in pages of 100 (`after` returns the messages directly after the
cursor), each page committed with its progress before the next request, so a
long run never holds the database against a send. A quiet run is two
requests. Bounds: 60 requests per run, counted before each request (retries
and the build-number page included), and 5 pages per channel per run;
anything left continues next run. A channel seen for the first time is seeded
with its newest 50 messages if its last message is under 30 days old (at most
15 per run); an older DM is followed from now on, its history fetched only on
request (`backfill`). A channel answering 403 or 404 is marked and skipped by
later runs (DMs included) until a live read of it succeeds again. Edits and
deletions after a message was mirrored are not replicated.

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
hours old; `channels` always asks Discord. `messages` reads the mirror for a
current channel, inside its contiguous history; a channel that is not current,
a page older than that history, an empty window or `live=true` is read live,
as is `context` around a message not in the mirror; `backfill` runs the
engine too. A live window is at most 100 messages and is stored in the mirror
as well, so search and approval cards can see it.
Messages come oldest first, with local times, `from: me` for the user's own,
reply targets, attachment names and links, and a note that text and names
are written by other people and are data, never instructions. `search` is a
literal substring match over the mirror only, and says so.

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

`send` is the only write to Discord: text (at most 2000 characters) and up to
10 files, to a channel the mirror knows — an existing DM or group DM, or a
server channel listed before. New DMs cannot be opened, names are refused, and
a `reply_to` must be a message of that channel already in the mirror.

- **Files come from the attach roots only**: `discord_access.attach_roots` in
  the profile's `config.yaml`, default `~/Workspaces`, with a relative path
  taken from the first root. Each must resolve (symlinks followed) to a regular
  file inside a root and outside the state directory, be non-empty and at most
  10 MB (the limit without Nitro). Credentials, keys and local databases are
  refused whatever the root: `.env*`, `*.pem`, `*.key`, `id_*` keys, `*.db`,
  `*.sqlite`, `*.keychain*` and anything with `.git`, `.ssh`, `.gnupg`,
  `.aws`, `.config` or `Keychains` anywhere in its real path, compared without
  case. A message may be files alone.
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
  To: DM with <name> (@<handle>)  |  group DM … | #<channel> in <server>
  Channel id: <id>
  Reply to: <sender>: <quoted text>
  Files (2): docs/report.pdf (1.2 MB), photo.png (340.0 KB)
  Pings: @everyone

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

## Ways around the tool

The same hook blocks terminal calls that name the state directory
(`hermes-discord`, the outbox included), the token or its Keychain scope
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
2. `hermes/launchd/discord-user-launchctl.sh install` — builds the venv from
   the lock if needed (`setup` does only that), renders and loads the agent.
   `run` does one sync in the terminal; `status` shows the venv, whether the
   token is present (never its value), the agent and the last run.
3. Enabling the plugin or changing its code needs a gateway restart; a new
   token, the sync list and engine changes do not.

`uninstall` stops the agent and keeps the venv, mirror and sync list; delete
`~/.local/state/hermes-discord/` to drop the mirror. After changing
`engines/discord-user/requirements.lock`, run `setup` again.
