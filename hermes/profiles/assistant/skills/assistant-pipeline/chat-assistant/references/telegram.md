# Telegram

Load `skill_view(name="telegram-access:telegram-account")` before any work in the user's own
Telegram account: it owns the mechanics — the `telegram_account` tool only
(never the terminal, a Telegram client library, the state directory, the
Keychain or the Telegram apps' data), behaving like a quiet client, which
action to read with, disappearing and deleted messages, saving files, the
sync list, sends and their cards, and outcomes. This file holds only what is
particular to Chat.

It is not your Telegram bot: the chat and topics where the user talks to you
belong to the gateway.

## What stays in Chat

The user's own direct requests: "Telegram の未読ある？", "〇〇さんとのやり取り見せて",
"このファイル保存して", "さっきの返信を送って", "△△も同期して", "□□はもう要らない".
Do them inline with the tool.

- A received message to interpret or answer follows `message-reply.md` for
  meaning and drafting; it is sent only when the user says to send it.
- Collecting many chats or a long history for a document or a summary is
  specialist work: promote it through Plan → Execute.

## In conversation

- When the request does not make clear which chat, list the candidates
  from `chats` and ask before any send.
- `search` covers the mirror only: when nothing is found, say so rather than
  "it was never said".
- Secret chats are not visible at all — say so when asked.
- A saved file is delivered with a bare `MEDIA:/abs/path` line.
- Report a send from the tool's result: the chat, and that Telegram accepted
  it. For `UNCERTAIN`, say what the read-back showed and let the user decide.
