# WhatsApp

Load `skill_view(name="whatsapp")` before any WhatsApp work: it owns the
mechanics — the `whatsapp` tool only (never `wacli` in the terminal, the
`~/.wacli` store or WhatsApp Web), choosing the account, finding and reading
a chat, older history, files someone sent, checking a number, counting, sends
and their approval card, and what each outcome means. This file holds only
what is particular to Chat.

## Which account

Load `skill_view(name="whatsapp-accounts")` before choosing an account: it
names each account, what it is for and any account-specific technic to load.
Unsure which one a request means → ask; never search every account to guess.

## What stays in Chat

The user's own direct requests: "WhatsApp で何か来てる？", "このお店とのやり取りを
要約して", "この写真を保存して", "この番号って WhatsApp 使ってる？", "これを送って".
Do them inline with the tool.

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
- Files `media` saves land in `~/Workspaces/.inbox/whatsapp/`. Moving a
  keeper into a Group's typed surface or a draft job, or deleting the folder,
  follows `~/Workspaces/AGENTS.md`.
- Report a send from the tool result, not from what was asked.
