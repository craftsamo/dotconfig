---
name: youtube-manage
description: "Use for any change to the user's YouTube channels: editing a video, thumbnails, captions, comments (reply, moderate), playlists, uploads, channel settings and watermark, or starting a channel."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [youtube, youtube-studio, upload, captions, comments, playlist, channel-settings]
---

# Changing YouTube through the `youtube` tool

Task skills (a channel strategy, a launch, a report) own what goes on
YouTube. This skill owns how it gets there. When a task skill names a
channel, a title or a schedule, follow it; the mechanics below still apply.
Reading, the budget and the channel choice are in `youtube-access:youtube`;
load it too.

## Contract

- **Only the tool.** Change YouTube with `youtube`, never `yaccess` or the
  API with curl in the terminal.
- **One exception: YouTube Studio in the browser**, only for channel settings
  the API cannot change (name, handle, picture, banner, links, contact email,
  home-tab layout, upload defaults), one setting per `clarify` yes. Procedure:
  `references/studio.md`. Anything the tool can do goes through the tool.
- **Writes wait for approval.** Every write shows a card naming the channel
  and the change. A denial or a timeout means it did not happen; never repeat
  a denied call unchanged. In cron, a single query or an inbound A2A request
  the tool refuses writes: schedule a reminder for the user instead.
- **Name the channel.** With several channels and no `channel` named, ask —
  never guess with a write.
- **Cost.** Writes cost 50 units of the day's budget, a caption upload
  400-450.

## Write

1. **Read first.** `videos` / `my_videos` for a video's current title,
   description, tags and language; `my_channel` for the channel's settings;
   `comments` for comment ids; `playlist` for `playlist_item_id`s;
   `captions` for a track id.
2. **Agree on long text first.** The card cuts long values. For a
   description, keywords or a translation, show the full final text in chat,
   get the user's agreement, then send exactly that text.
3. **Send only what changes.** Fields left out stay as they are; the tool
   reads the current values and merges. `tags`, `keywords` and `description`
   replace the whole value.
4. **One call per intent.** A video's detail edits fit one `update`; the
   channel's settings fit one `channel_update`.

### Actions

- `update` — `video` plus any of `title`, `description`, `tags`,
  `category_id`, `default_language`, `localizations`, `made_for_kids`,
  `license` (`youtube` | `creativeCommon`), `embeddable`, `public_stats`,
  `synthetic_media` (the altered or synthetic content disclosure), `privacy`,
  `publish_at` (ISO 8601 with an offset, e.g. `2026-10-06T18:00+09:00`; the
  video stays private until then).
- `thumbnail` — `video`, `path` = a JPEG/PNG of at most 2 MB.
- `upload` — `path`, `title` and the `update` fields except
  `localizations`. YouTube keeps these uploads private (the API project is
  not audited): tell the user to publish it in YouTube Studio.
- `caption_upload` — `video`, `path` = an `.srt`/`.vtt`/`.sbv`/`.ttml`/
  `.dfxp`/`.scc` file with timings; `language` and optional `name` add a
  track, `caption` = a track id replaces that track's file; `draft: true`
  hides it. Costs 400-450 units: only for a file the user means to publish.
- `reply` — `comment`, `text`: public, as the channel, visible at once.
- `moderate` — `comment` = one id or up to 50, `moderation` `publish` |
  `hold` | `reject`; `ban_author` only with reject and only when the user
  says so. A rejected comment and its replies stay hidden for good.
- `playlist_create`, `playlist_add` (optional `position`), `playlist_update`
  (`title`, `description`, `privacy`), `playlist_move` (`item`, `position`
  from 0), `playlist_remove` (the entry, never the video).
- `channel_update` — any of `description` (at most 1000), `keywords` (an
  array), `country`, `default_language`, `trailer` (a public or unlisted own
  video shown to visitors who are not subscribed; `""` removes it),
  `localizations`, `made_for_kids` (the whole channel). Each change reaches
  the whole channel.
- `watermark` — `path` = a JPEG/PNG, shown in the upper right of every video;
  `display` `entire` | `end` (last 15 s) | `from` with `start_s`.
  `watermark_remove` takes it off.

`localizations` = `{"en": {"title": …, "description": …}}`, merged into the
existing ones; `null` for a language removes it; a new language needs a
title. The video or channel needs a `default_language` first: when `videos`
or `my_channel` shows none, send it in the same call.

Nothing here deletes a video, comment, playlist or caption track; say so and
leave deletion to the user in Studio.

### When a write goes wrong

- An error result means it did not happen: report the reason, fix it, and
  call again for a new card.
- `partly done: …` from `channel_update`: some parts changed and some did
  not. Read `my_channel`, report both, and resend only what is missing.
- A call that broke off with no result (a timeout during an upload or a
  caption upload): look first (`my_videos`, `captions`) and never upload
  again without the user's say-so.
- An API error on the whole-channel `made_for_kids` (Google's documentation
  is unclear whether the API accepts it): stop and leave that setting to the
  user in Studio (Settings → Channel → Advanced settings).

## Approvals

Detail edits to one video (`update` without `privacy` or `publish_at`, and
`thumbnail`) share one approval per video: after "session" or "always" on
its first card, later edits to that video run without a card — still make
only the changes the user asked for. Going public, scheduling, uploads,
captions, replies, moderation, playlist, channel and watermark changes ask
every time.

## Starting a channel

When the user is starting a channel or choosing its name and handle, follow
`references/channel-setup.md` for the mechanics; strategy (what the channel
is for, how many channels) belongs to the task skill or Marketer.
