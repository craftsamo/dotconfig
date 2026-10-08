# Collecting Discord history as evidence

For a document, an inventory or a summary that will cite what was said: the
history goes to files once, verbatim, and every later claim is checked
against those files. Read-only: a collection job never sends, reacts or
changes the sync list.

## Before reading

1. **Agree the scope with the user.** Which servers and channels, which
   period, and what stays out. Official, guide, rules, roles and announcement
   channels are usually in; staff-only rooms, individual support rooms and
   casual chat are usually out, or capped (explanatory and staff posts only,
   with a stated cap and the skipped count).
2. **Resolve the ids.** `guilds`, `channels` with `guild`, `threads` for forum
   posts. Note each channel's `last_message` and whether it is `synced`.
3. **Pick a cap per channel** (messages, or a date) and say it.

## Reading

- **One reader, one channel at a time.** Collect in this session or in one
  background worker, never in parallel subagents: the tool paces requests
  only inside one call, so parallel readers multiply the traffic the user's
  account carries.
- **Forward from a point:** `messages` with `after` = the last id read,
  `limit` 50-100. **Backwards:** `before` = the oldest id held. Lower `limit`
  (25-40) for channels with long posts when a result is refused as too long.
- **Synced channels:** `backfill` (`pages` 1-5 of 100) stores older history
  in the mirror; then read it with `messages` and `before`. Unsynced channels
  are read live, at most 100 a call.
- **Write each page to disk as it comes**, so an interruption loses nothing,
  and keep a progress file (channel, oldest and newest id and date reached,
  count). Report progress from that file, not from memory.
- The channel start is reached when a backwards page returns no `more`.
  Record "complete to channel start" in the file header; otherwise record
  the resume id.
- A page that keeps failing around one message: lower `limit` to page
  around it, read that message with `context`, and note the workaround in
  the file header and beside the message.

## Raw files

One file per channel in the job's draft directory, e.g.
`<Group>/.agent/<YYYYMMDD>-<job>/raw/<channel_id>.md`:

- A header: server, channel, channel id, message count, date range read, cap
  and skipped count, known gaps.
- Per message, oldest first: `### <ISO time with offset> | <author> | id <message id>`,
  the permalink `https://discord.com/channels/<guild>/<channel>/<message>`,
  then the full text. No summarising at this stage: the permalinks are what
  later claims are checked against.
- Older history added later goes into a new file
  (`<channel_id>-before-<YYYYMMDD>.md`); never rewrite an existing export.
- Bot posts rebuilt from a fixed template (lottery results and the like) are
  not verbatim: the header says so, and they are never quoted as verbatim.
- Facts the chat lacks (prices, terms) often sit on the product's public
  page: save it as `raw/web-<site>-<page>.md` with the URL, the fetch date and
  what the page does not say, and cite it with that date.

## Coverage

Record gaps while collecting, in `raw/_notes.json`: per channel the range
actually read, sampled-only channels, embeds, polls, PDFs or images not
captured, threads not opened. They become "not obtained / unconfirmed" lines
in the document, so they cannot be reconstructed afterwards.

## Checks before use

- After joining older history: message count equals the header count, no
  duplicate ids, and the newest id of the older file is directly followed by
  the oldest id of the existing one.
- Every message id a draft cites must exist in `raw/`; spot-check the
  load-bearing claims (amounts, dates, thresholds) against the cited block.
- A figure found only in a member's quote of an announcement is "quoted in a
  member post, primary unconfirmed" until the primary channel's history
  shows it. Two conflicting announcements are shown side by side with dates.
- Dates are post dates, not event dates. Never derive a channel's or
  server's creation date from its id; the earliest message retrieved is
  "earliest retrieved", not the founding.
- A writer's or worker's report of what it read is not coverage evidence;
  the files and `_notes.json` are.

Times in raw files carry their offset; say which time zone a summary uses.
