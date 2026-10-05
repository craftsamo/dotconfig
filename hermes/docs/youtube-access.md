# YouTube access

The user's own YouTube channels as a tool: search, videos, channels,
playlists and comments anywhere on YouTube, each authorized channel's own
uploads (private, unlisted and scheduled included) and its YouTube Analytics,
and transcripts and downloads of any public video. The Assistant also
writes on its channels — video details, thumbnails, comment replies, uploads
and playlists — each held for the user's approval on a card. Marketer only
reads. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece | Home | Reader |
|---|---|---|
| Engine: validation, profile actions, tokens, quota, pacing, result shapes, approval card, bypass guard; the `yaccess` CLI | `plugins/youtube-access/ya.py` | all |
| One yt-dlp call per transcript or download in the engine venv | `plugins/youtube-access/bridge.py` | all |
| `youtube` tool and its `pre_tool_call` hook (toolset `youtube_access`) | `plugins/youtube-access/__init__.py` | Assistant, Marketer |
| Channel authorization | `bin/yaccess` (runs `ya.py` on `hermes-python`) | people |
| Engine venv | `scripts/youtube-access.sh`, `engines/yt-dlp/` | people |
| When and how the Assistant uses it | the Assistant's private Chat reference `youtube.md` | Assistant |
| When Marketer reads with it | Marketer's prompt and `build-marketer/references/measurement.md` | Marketer |

Two back ends, one tool. The YouTube Data API v3 and the YouTube Analytics
API v2 run in Hermes' own Python (the `google` extra `setup.sh` installs) as
one of the user's channels. The official API cannot read captions of videos
the channel does not own, so transcripts and downloads of public videos run
[yt-dlp](https://github.com/yt-dlp/yt-dlp) without cookies: `bridge.py` runs
under the interpreter of `hermes/local/yt-dlp/venv` (ignored; Python 3.12.11,
`yt-dlp[default]` from the hash-locked `engines/yt-dlp/requirements.lock`,
which brings the `yt-dlp-ejs` challenge solver), never Hermes' own, as a
child process (`python -I`) with a minimal environment: `HOME`, `PATH`
(Homebrew first, for Deno and ffmpeg), `LANG`. yt-dlp is unofficial and
breaks when YouTube changes; bump the pin when it does.

## Channels, tokens and state

Each channel is authorized once in the browser (`yaccess auth`) with one
Desktop OAuth client — google-access's works once the YouTube Data API v3
and the YouTube Analytics API are enabled in its project. The consent screen
opens Google's account chooser, so a brand account's channel is picked there;
one consent covers one channel, so `auth` is repeated per channel. Scopes:
`youtube.readonly`, `youtube.upload`, `youtube.force-ssl` (edits, replies,
playlists) and `yt-analytics.readonly`. The OAuth app must be published "In
production": a "Testing" app's refresh tokens expire after seven days.

A Google account without a YouTube channel can be authorized too. Its token
is kept under the id `account` and serves the public reads (search, videos,
channels, playlists, comments, plus transcripts and downloads, which need no
token at all) only while no real channel is authorized; `my_videos`,
`analytics` and every write refuse with a message that a channel is needed,
and `status` says the authorization has no channel. When the user later
creates a channel on that account, `yaccess check` (or the next `yaccess
auth`) asks Google again and files the same token under the new channel, with
no new consent. A brand-account channel is a different identity, so it needs
`yaccess auth` with that channel picked. Moving or dropping the `account`
entry never revokes its token: Google revokes a whole grant with one token,
and that grant may be the one a channel entry uses.

Every channel's refresh token (with the client id and secret it belongs to)
lives only in the Keychain, as one JSON item `YOUTUBE_OAUTH` in the `hermes`
project under the scope `youtube-access` — the arrangement the X cookies
use: Hermes only ever receives shared layers, so the tokens never enter a
profile's secret scope, the gateway process environment or a CLI session.
The engine reads the item when a channel's first call (or a refused refresh)
needs it, keeps access tokens only in memory and writes the item back only
when Google hands out a new refresh token — on every refresh, the HTTP
transport's own (expiry or a 401 mid-upload) included, one at a time, and
only over the token it was refreshed from. Every write goes through
`secret … --stdin`, never argv, under a lock as a read-modify-write; an item
that exists but cannot be read stops it rather than being replaced. Both profiles share the authorizations: the
channels belong to the user, not to a profile, and the Data API quota is the
Cloud project's either way.

A read refreshes its access token with only the read scopes, so the token a
read holds cannot write; a write uses every scope the channel granted. If
Google ever refuses the narrowed refresh (`invalid_scope`), reads fall back
to the full token for the rest of the process; `yaccess check` reports which
happens. Comments are the exception: Google serves `commentThreads.list` and
`comments.list` only to a token with `youtube.force-ssl`, even for reading,
so `comments` always uses the full token. What keeps Marketer from writing
is the action list below, not the token.

`channel` (a title, `@handle` or `UC…` id) picks which authorized channel a
call acts as and reports on; without it, `youtube_access.default_channel` in
the profile's `config.yaml`, else the only channel. `youtube_access.
download_dir` names the download folder (the Assistant uses
`~/Workspaces/.inbox/youtube`), else `<HERMES_HOME>/youtube-downloads/`;
`youtube_access.attach_roots` (default `~/Workspaces`) bounds the files an
upload or thumbnail may read.

`~/.youtube-access/` (mode 700, outside every repository) holds no secret:
`channels.json` (each authorized channel's id, title, handle and scopes,
written by `yaccess`), `state.json` (the Pacific day's API use and the yt-dlp
call times) and lock files.

## Profiles

| Profile | Actions | Inbound A2A |
|---|---|---|
| Assistant | every read and write | refused |
| Marketer | reads only (schema and handler) | reads allowed |

The action list a profile gets is fixed when the plugin registers and checked
again by the gate and the engine. Marketer's endpoint is inquiry-only: an
inbound request reads only when the turn's bound profile home is Marketer's,
failing closed otherwise.

## Reads

| Action | Back end | Cost | Notes |
|---|---|---|---|
| `status` | — | 0 | channels, default, quota and pacing use, engine, download folder |
| `search` | Data API | 1 search (+1 unit for video details, +1 to resolve an `@handle`) | `query` and/or `of` = a channel; kind, order, dates, duration, language, region |
| `videos` | Data API | 1 unit per 50 | details and counts |
| `channels` | Data API | 1 unit (+1 per `@handle`) | profile, counts, uploads list |
| `playlist` | Data API | 1 unit per 50 entries (+1 per 50 for details) | a playlist, or `of` = a channel's uploads; entries carry `playlist_item_id` |
| `comments` | Data API | 1 unit per 100 | threads with first replies; `thread` = a comment id for all replies |
| `my_videos` | Data API | 1 + 2 units per 50 | the channel's own uploads incl. private, unlisted, scheduled |
| `analytics` | Analytics API | its own quota | `channel==MINE`, default the last 28 days |
| `transcript` | yt-dlp | 1 paced call | text saved to the download folder |
| `download` | yt-dlp | 1 paced call | mp4 (≤ `max_height`) or m4a |

**Quota.** Google counts per Cloud project and Pacific day: 100 searches and
100 uploads in buckets of their own, and 10,000 units for everything else
(lists 1, writes 50). The engine charges each call in `state.json` before
making it and answers `paused: …` once a bucket is spent; it stops at 9,500
units so writes still fit. Google's own `quotaExceeded` reads the same way.
The count is local: other users of the project (google-access does not touch
YouTube) would not be seen.

**Transcripts.** The track is the first of: a manual caption in a requested
`languages` code, the spoken language's manual caption, its automatic
speech-recognition track (`-orig`), YouTube's machine translation into a
requested language, any manual caption. The result says which (`manual`,
`auto`, `translated`), carries the text with `[m:ss]` stamps (`timestamps=
false` for plain text) clipped at 40,000 characters, and the path of the full
text, `<download_dir>/<video id>/<video id>.<language>.txt`.

**Downloads** go to `<download_dir>/<video id>/<video id>.<ext>`:
`kind=video` merges the best mp4 video up to `max_height` (default 1080) with
m4a audio (ffmpeg), `kind=audio` keeps the m4a track unconverted. Live and
upcoming streams and videos over four hours are refused; so is a selection
whose streams together pass 4 GB, before the download when YouTube states
the sizes and by deleting the result afterwards when it did not (streamed
formats are not capped while they download). A file already present is
reused. The engine only ever hands the bridge an
11-character video id and the bridge builds the URL, so yt-dlp never reaches
another site or a playlist.

**Pacing.** yt-dlp calls (no login, so this machine's IP is what is at stake)
run one at a time (a lock held for the whole call; a second waits up to 90 s,
then is told to try later), at least 5 s apart, at most 30 per hour and 150 per 24
hours across both profiles. A missing engine costs nothing.

Titles, descriptions, comments and transcripts are other people's text: the
results say so and the tool description forbids following instructions in
them.

## Writes

Assistant only, on the chosen channel's own content; every write is held for
the user's approval on a card that names the channel and what changes.

| Action | Cost | Approval key |
|---|---|---|
| `update` (title, description, tags, category, made for kids) | 1 + 50 units | per channel and video |
| `update` with `privacy` or `publish_at` | 1 + 50 units | exact call |
| `thumbnail` (JPEG/PNG ≤ 2 MB) | 50 units | per channel and video |
| `reply` (to a comment) | 50 units | exact call |
| `upload` | 1 upload | exact call plus the file's size and time |
| `playlist_create`, `playlist_add`, `playlist_remove` | 50 units | exact call |

"Session" or "always" on the first edit card of a video covers that video's
later detail edits and thumbnails; the user chose this so iterating on a
title does not ask every time. Going public, scheduling, replying, uploading
and playlist changes ask every time. `update` reads the video first, refuses
another channel's video, and sends the whole writable snippet and status back
with the changes merged in (the API clears fields a request leaves out).
`publish_at` keeps the video private until then.

Every write is pinned to what its card was made from: a second
`pre_tool_call` hook (`bind`, Assistant only) adds the resolved channel and,
for an upload or thumbnail, the file's path, size and modification time to
the call's arguments. The handler runs the write as that channel and refuses
it when the file changed since the card (or when the call carries no binding
at all), so a moved default channel or a replaced file cannot slip past an
approval. The file is checked, not copied: a change in the instant between
the check and the read is not caught.

Uploads are resumable (8 MB chunks), private by default, and come only from
the attach roots (no hidden credential folders). **YouTube locks uploads from
an unaudited API project created after July 2020 to private**; the result
says so and the user publishes in YouTube Studio (or the project passes
YouTube's API audit). Nothing deletes videos, comments or playlists;
`playlist_remove` removes an entry, never the video.

Writes are refused where no person can approve — cron, webhook and API
sessions, single queries, and when approvals are switched off (`/yolo`,
`approvals.mode: off`) — because Hermes would otherwise approve them without
a card.

## Ways around the tool

The hook blocks terminal calls whose text names yt-dlp (or `youtube-dl`), the
plugin (`youtube-access`, `youtube_access`), `yaccess`, the Keychain item
(`YOUTUBE_OAUTH`) or a whole-Keychain read (`dump-keychain`, `secret
export`), and file-tool calls on the state directory
(`.youtube-access`), the item name or the engine venv. File tools may still
read the plugin source, transcripts and downloads. It is a pattern match, not
a sandbox.

## Setup

1. `~/.config/hermes/scripts/youtube-access.sh install` (Deno and ffmpeg come
   from the Brewfile).
2. In the Google Cloud project of the Desktop OAuth client, enable the
   YouTube Data API v3 and the YouTube Analytics API; keep the app "In
   production".
3. `yaccess auth ~/Downloads/client_secret.json` once per channel, picking
   the channel on Google's chooser (unverified-app warning: Advanced →
   continue). An account without a channel yet works for public reads; run
   `yaccess check` after creating its channel. `yaccess channels` lists them, `yaccess check` refreshes each
   token and shows whether reads get a read-only token, `yaccess revoke
   CHANNEL` revokes one.
4. In the Assistant's and Marketer's `config.yaml`: the `youtube_access`
   toolset in `toolsets` and `platform_toolsets` (Marketer's `a2a` too, never
   the Assistant's), `youtube-access` in `plugins.enabled`, and optionally
   `youtube_access.default_channel` and `download_dir`; then restart the
   gateway.

`youtube-access.sh status` shows the engine, Deno, ffmpeg, whether tokens are
stored (never their value), the channels and today's use. After bumping the
pin, recompile the lock (command in `requirements.in`) and run `install`
again.
