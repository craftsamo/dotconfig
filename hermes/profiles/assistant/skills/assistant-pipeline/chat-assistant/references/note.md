# note (note.com)

Load `skill_view(name="note-com")` before any note work: it owns the
mechanics — the `note` tool only (never the terminal, the session cookie or
editor.note.com in the browser), the shared request budget, which action
reads what, preparing a body with `check`, saving with `preview` and the
card, results and recovery. This file holds only what is particular to
Chat.

## What stays in Chat

The user's own direct requests: "この記事を要約して", "下書き一覧を見せて",
"先月の PV は？", "この下書きの見出しを直して保存して", "この Markdown を下書きにして".
Do them inline with the tool.

- Writing or rewriting an article's words is Writer's: promote it through
  Plan → Execute, then come back here to save the accepted text. A
  markup-only fix that `check` asks for stays here, shown to the user before
  the save.
- What to publish next, why an article did (not) read well, or planning a
  series → Marketer (`specialist_call(target="marketer", ...)`), which reads
  the same account and stats.
- Publishing, deleting, liking, following, commenting, and adding embeds,
  sounds, a stock chart or a paid line cannot be done with the tool: say so
  and leave them to the user in the browser.

## In conversation

- Counts are for the period read; say which, and that views are not unique
  readers.
- On success, give the `edit_url`; the user publishes from there.

Do not schedule a job that is meant to save a note draft (nobody could
answer its card); schedule a reminder for the user instead.
