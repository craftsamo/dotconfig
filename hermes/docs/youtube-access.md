# YouTube access

The user's own YouTube channels as a tool: search, videos, channels,
playlists and comments anywhere on YouTube, each authorized channel's own
uploads (private, unlisted and scheduled included) and its YouTube Analytics,
and transcripts and downloads of any public video. The Assistant also writes on
its channels — video details and settings, thumbnails, comment replies and
moderation, uploads, captions, playlists, the channel's settings and watermark —
each held for the user's approval on a card. Marketer only reads. Channel
settings the API does not reach go through YouTube Studio in the Assistant's
browser ([below](#studio-settings)). Read it when changing the plugin, its
quota accounting or its write path. Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                     | Home                                                                                                                                         | Reader                        |
| ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Engine: validation, profile actions, tokens, quota, pacing, result shapes, approval card, bypass guard; the `yaccess` CLI | `plugins/social/youtube-access/ya.py`                                                                                                        | all                           |
| One yt-dlp call per transcript or download in the engine venv                                                             | `plugins/social/youtube-access/bridge.py`                                                                                                    | all                           |
| `youtube` tool and its `pre_tool_call` hook (toolset `youtube_access`)                                                    | `plugins/social/youtube-access/__init__.py`                                                                                                  | Assistant, Marketer           |
| Channel authorization                                                                                                     | `bin/yaccess` (runs `ya.py` on `hermes-python`)                                                                                              | people                        |
| Engine venv                                                                                                               | `scripts/youtube-access.sh`, `engines/yt-dlp/`                                                                                               | people                        |
| How a profile reads YouTube: budget, read actions, recovery                                                               | the `youtube-access:youtube` plugin skill (`plugins/social/youtube-access/skills/youtube/`)                                                  | Assistant, Marketer, Searcher |
| How the Assistant changes it: write actions, approvals, recovery, Studio settings, starting a channel                     | the `youtube-access:youtube-manage` plugin skill (`plugins/social/youtube-access/skills/youtube-manage/`); registered for the Assistant only | Assistant                     |
| When the Assistant uses it in Chat                                                                                        | the Assistant's private Chat reference `youtube.md`                                                                                          | Assistant                     |
| When Marketer reads with it                                                                                               | Marketer's prompt and `analyze-marketer/references/measurement.md`                                                                           | Marketer                      |

Two back ends, one tool. The YouTube Data API v3 and the YouTube Analytics API
v2 run in Hermes' own Python (the `google` extra) as one of the user's
channels. The official API cannot read captions of videos the channel does not
own, so transcripts and downloads of public videos run
[yt-dlp](https://github.com/yt-dlp/yt-dlp) without cookies: `bridge.py` runs
under the hash-locked `hermes/local/yt-dlp/venv`, never Hermes' own, as a child
process with a minimal environment ([bridge process](access-common.md#state-directory-and-bridge-process)).
yt-dlp is unofficial and breaks when YouTube changes; bump the pin when it does.

## Channels, tokens and state

Each channel is authorized once in the browser (`yaccess auth`) with one Desktop
OAuth client — google-access's works once the YouTube Data API v3 and the
YouTube Analytics API are enabled in its project. One consent covers one
channel, so `auth` is repeated per channel (a brand account's channel is picked
on Google's chooser). The OAuth app must be published "In production": a
"Testing" app's refresh tokens expire after seven days.

A Google account without a YouTube channel can be authorized too. Its token is
kept under the id `account` and serves the public reads only while no real
channel is authorized; `my_videos`, `analytics` and every write refuse with a
message that a channel is needed. When the user later creates a channel on that
account, `yaccess check` (or the next `yaccess auth`) files the same token under
the new channel, with no new consent. Moving or dropping the `account` entry
never revokes its token: Google revokes a whole grant with one token, and that
grant may be the one a channel entry uses.

Every channel's refresh token (with the client id and secret it belongs to)
lives only in the Keychain, as one JSON item `YOUTUBE_OAUTH` in the `hermes`
project under the scope `youtube-access`
([secret scoping](access-common.md#secret-scoping)). The engine keeps access
tokens only in memory and writes the item back only when Google hands out a new
refresh token, one at a time and only over the token it was refreshed from.
Every write goes through `secret … --stdin`, never argv, under a lock as a
read-modify-write; an item that exists but cannot be read stops it rather than
being replaced. Both profiles share the authorizations: the channels belong to
the user, not to a profile, and the Data API quota is the Cloud project's either
way.

A read refreshes its access token with only the read scopes, so the token a read
holds cannot write; a write uses every scope the channel granted. Comments and
captions are the exception: Google serves those lists only to a token with
`youtube.force-ssl`, even for reading, so they always use the full token. What
keeps Marketer from writing is the action list below, not the token.

`channel` (a title, `@handle` or `UC…` id) picks which authorized channel a call
acts as; without it, `youtube_access.default_channel` in the profile's
`config.yaml`, else the only channel. `youtube_access.download_dir` and
`youtube_access.attach_roots` (bounds the files an upload or thumbnail may read)
come from the same place.

`~/.youtube-access/` (mode 700, outside every repository) holds no secret:
`channels.json` (written by `yaccess`), `state.json` (the Pacific day's API use
and the yt-dlp call times) and lock files.

## Profiles

| Profile   | Actions                         | Inbound A2A   |
| --------- | ------------------------------- | ------------- |
| Assistant | every read and write            | refused       |
| Marketer  | reads only (schema and handler) | reads allowed |
| Searcher  | public reads only               | refused       |

The action list a profile gets is fixed when the plugin registers and checked
again by the gate and the engine ([profile gating](access-common.md#profile-gating)).
Searcher gets `status`, `search`, `videos`, `channels`, `playlist`, `comments`
and `transcript`: nothing on the user's own channels (`my_videos`, `analytics`,
`my_channel`, `captions`), no `download` (it writes media files) and no channel
selector. Its searches count against the daily search bucket all profiles share.

## Reads

The tool schema lists the read actions. The Data API ones cost quota units, the
Analytics API has its own quota, and `transcript` and `download` run yt-dlp.

**Quota.** Google counts per Cloud project and Pacific day: searches and uploads
in buckets of their own, and a shared unit budget for everything else. The
engine charges each call in `state.json` before making it and answers
`paused: …` once a bucket is spent; it stops short of the unit budget so writes
still fit. The count is local: other users of the project would not be seen.

**Transcripts.** The track chosen is reported as `manual`, `auto` or
`translated`; the full text is written under `<download_dir>/<video id>/`.

**Downloads.** Live and upcoming streams, very long videos and over-size
selections are refused. The engine only ever hands the bridge an 11-character
video id and the bridge builds the URL, so yt-dlp never reaches another site or
a playlist.

**Pacing.** yt-dlp calls (no login, so this machine's IP is what is at stake)
run one at a time, with caps shared by both profiles.

Titles, descriptions, comments and transcripts are other people's text: the
results say so and the tool description forbids following instructions in them.

## Writes

Assistant only, on the chosen channel's own content; every write is held for the
user's approval on a card that names the channel and what changes
([approval gate](access-common.md#approval-gate)). Approval keys differ by how
far a grant may reach:

| Action                                                                      | Approval key                             |
| --------------------------------------------------------------------------- | ---------------------------------------- |
| `update` (details and settings), `thumbnail`                                | per channel and video                    |
| `update` with `privacy` or `publish_at`                                     | exact call                               |
| `reply`, `moderate`, playlist actions, `channel_update`, `watermark_remove` | exact call                               |
| `upload`, `caption_upload`, `watermark`                                     | exact call plus the file's size and time |

"Session" or "always" on the first edit card of a video covers that video's
later detail edits and thumbnails; the user chose this so iterating on a title
does not ask every time. Going public, scheduling, replying, moderating,
uploading, captions, playlist and channel changes ask every time: they are
rarer, public at once, or reach every video. `update`, `playlist_update` and
`channel_update` read the resource first, refuse another channel's, and send
each part they touch back whole with the changes merged in (the API clears
fields a request leaves out, and refuses a changed channel title).
`localizations` merge per language (`null` removes one).

The channel API takes one part per request, so `channel_update` prepares every
part before the first and then sends them in order; when a later part fails, the
result says which already changed. Google documents
`status.selfDeclaredMadeForKids` as writable while listing only the other parts
for `channels.update`, so the whole-channel kids flag may come back as an API
error. Banners are not here: `brandingSettings.image` stopped working, so the
banner is a Studio setting. Caption files must carry their own timings.

Every write is pinned to what its card was made from: a second `pre_tool_call`
hook (`bind`, Assistant only) adds the resolved channel and, for an upload or
thumbnail, the file's path, size and modification time to the call's arguments.
The handler runs the write as that channel and refuses it when the file changed
since the card (or when the call carries no binding at all), so a moved default
channel or a replaced file cannot slip past an approval. The file is checked,
not copied: a change in the instant between the check and the read is not
caught.

Uploads are private by default and come only from the attach roots.
**YouTube locks uploads from an unaudited API project created after July 2020
to private**; the result says so and the user publishes in YouTube Studio (or
the project passes YouTube's API audit). Nothing deletes videos, comments,
playlists or caption tracks; `moderate` with `reject` hides a comment for good.

Writes are refused where no person can approve
([approval gate](access-common.md#approval-gate)) — Hermes would otherwise
approve them without a card.

## Studio settings

The API cannot change the channel's name, handle, profile picture, banner,
links, contact email, home-tab layout or upload defaults. For those the
Assistant uses YouTube Studio in its own browser (Brave profile pinned in its
config, signed in by the user; [ops/browser.md](ops/browser.md)): it
reads the current value, asks the user with `clarify` showing before and after,
saves only on a yes, and reads the page again to confirm. There is no approval
card on this path — `clarify` is the confirmation — so it runs only in a
conversation with the user, never in cron, a single query or an A2A request.
Account-level and destructive Studio settings (permissions, monetization,
channel deletion or transfer) stay with the user. The procedure lives in the
`youtube-access:youtube-manage` skill's `references/studio.md`; when a Studio
page does not match it, the Assistant stops and hands the change to the user.

## Ways around the tool

Patterns: `_TERMINAL` in `plugins/social/youtube-access/ya.py`; file tools may
still read the plugin source, transcripts and downloads. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. `~/.config/hermes/scripts/youtube-access.sh install` (Deno and ffmpeg come
   from the Brewfile).
2. In the Google Cloud project of the Desktop OAuth client, enable the YouTube
   Data API v3 and the YouTube Analytics API; keep the app "In production".
3. `yaccess auth ~/Downloads/client_secret.json` once per channel (unverified-app
   warning: Advanced → continue). `yaccess channels`, `check` and
   `revoke CHANNEL` manage them.
4. In the Assistant's and Marketer's `config.yaml`: the `youtube_access` toolset
   in `toolsets` and `platform_toolsets` (Marketer's `a2a` too, never the
   Assistant's), `youtube-access` in `plugins.enabled`, and optionally
   `youtube_access.default_channel` and `download_dir`; then restart the
   gateway.
