# Signal

Load `skill_view(name="signal-access:signal")` before any Signal work: it owns the
mechanics — the `signal` tool only (never `signal-cli` in the terminal, the
`~/.local/state/hermes-signal` state or Signal Desktop's data), finding and
reading a chat, mentions, disappearing and deleted messages, files someone
sent, checking a number, sends and their approval card, and what each outcome
means. This file holds only what is particular to Chat.

## What stays in Chat

The user's own direct requests: "Signal で何か来てる？", "山田さんとのやり取りを
要約して", "この写真を保存して", "この番号って Signal 使ってる？", "これを送って". Do
them inline with the tool.

- Interpreting a received message or drafting a reply → `message-reply.md`
  owns the meaning and the drafts. A draft is sent only when the user says to
  send it, with the exact text they picked.
- A reply that grows into a crafted piece, or an outbound batch → promote it
  through Plan → Execute; come back here to send.

## In conversation

- A problem `status` reports is the user's to fix in a terminal: relay its
  `action_needed` line in one line.
- A file the user wants sent from outside `~/Workspaces` is copied into the
  workspace first — a draft under `.agent/<YYYYMMDD>-<job>/` — and only when
  the user asked for that file. A file saved by `media` is already in the
  workspace and can be sent on as it is.
- Files `media` saves land in `~/Workspaces/.inbox/signal/`. Moving a keeper
  into a Group's typed surface or a draft job, or deleting the folder, follows
  `~/Workspaces/AGENTS.md`; files from disappearing messages are triaged
  first.
- Report a send from the tool result, not from what was asked.
