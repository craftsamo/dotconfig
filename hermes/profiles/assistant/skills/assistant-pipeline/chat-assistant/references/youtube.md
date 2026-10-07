# YouTube

Load `skill_view(name="youtube")` before any YouTube work: it owns the
mechanics — the `youtube` tool only (never the terminal, yt-dlp or the
upstream `youtube-content` helper), the daily budget, which action to read
with, writes and their approvals, recovery, and YouTube Studio in the
browser for the channel settings the API cannot change. This file holds only
what is particular to Chat.

## What stays in Chat

The user's own direct requests: "この動画の字幕を要約して", "先週の再生数は？",
"このタイトルに変えて", "チャンネルの説明を英語でも出して", "このコメントを非表示に",
"ハンドルを変えたい". Do them inline with the tool (or Studio, per the technic).

Channel strategy, what to make next, or why a video did (not) travel →
Marketer (`specialist_call(target="marketer", ...)`), which reads the same
channels and analytics. Producing a video, thumbnail or caption file is
creation: promote it through Plan → Execute, then come back here to upload
or set it.

## In conversation

- Several channels and the request does not say which: ask before any write.
- Long text (a description, keywords, a translation): show the final text in
  chat and get the user's agreement first; the card cuts it.
- A Studio change: one `clarify` per setting, before → after in full.
- Report what changed from the tool result (or the page read back), not
  from what was sent.

Writes need the user present: in cron, a single query or an inbound A2A
request the tool refuses them. Do not schedule a job that is meant to write
to YouTube or change Studio settings; schedule a reminder for the user
instead.
