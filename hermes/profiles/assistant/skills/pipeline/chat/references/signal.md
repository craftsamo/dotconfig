# Signal

The `signal_*` tools are the only way to the user's Signal account — never
`signal-cli` or `signal-tools-cli` in the terminal, the
`~/.local/state/signal-tools` state or Signal Desktop's data. Load the skill
for the work before the first call; each owns its tools' mechanics:

| Work | Skill |
| --- | --- |
| Which account is linked, whether receiving is healthy | `skill_view(name="signal-tools:account")` |
| Finding a chat, reading it, searching what people wrote | `skill_view(name="signal-tools:chats")` |
| Finding a contact, checking whether a number is on Signal | `skill_view(name="signal-tools:contacts")` |
| Sending a text or a reply | `skill_view(name="signal-tools:sends")` |
| Saving files someone sent, unpacking an archive, sending files | `skill_view(name="signal-tools:files")` |

Editing, deleting and reacting are not available here. This file holds only
what is particular to Chat.

## What stays in Chat

The user's own direct requests: "Signal で何か来てる？", "山田さんとのやり取りを
要約して", "この写真を保存して", "この番号って Signal 使ってる？", "これを送って". Do
them inline with the tools.

- Interpreting a received message or drafting a reply → `message-reply.md`
  owns the meaning and the drafts. A draft is sent only when the user says to
  send it, with the exact text they picked.
- A reply that grows into a crafted piece, or an outbound batch → promote it
  through Plan → Execute; come back here to send.

## In conversation

- A problem `signal_account_read` reports is the user's to fix in a
  terminal: relay its next step in one line.
- Every send has a card, and nothing is sent where no one can answer it (a
  scheduled job, a request from another agent). Answering "always" covers
  later sends to the same chat, whatever their text: say so if the user asks
  how to stop being asked, and suggest "once" for anything they want to see
  each time.
- A send that fails as `stale` changed after the card was shown (the text, a
  file, the chat's members): show the user the new state and send again only
  if they still want it. `uncertain` means it may have gone out: ask the user
  to look on the phone before any resend.
- A file the user wants sent from outside `~/Workspaces` is copied into the
  workspace first — a draft under `.agent/<YYYYMMDD>-<job>/` — and only when
  the user asked for that file. A file saved from a message is already in the
  workspace and can be sent on as it is.
- Saved files land in `~/Workspaces/.inbox/signal/`. Moving a keeper into a
  Group's typed surface or a draft job, or deleting the folder, follows the
  layout in `read_file` of
  `~/.hermes/profiles/assistant/skills/pipeline/references/workspace-layout.md`;
  files from disappearing messages are triaged first.
- Report a send from the tool result, not from what was asked.
