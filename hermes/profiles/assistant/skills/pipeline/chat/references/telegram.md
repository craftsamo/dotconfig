# Telegram

The `telegram_*` tools are the only way to the user's Telegram account — never
the terminal, a Telegram client library, the state directory, the Keychain or
the Telegram apps' data. Load the skill for the work before the first call;
each owns its tools' mechanics:

| Work | Tools | Skill |
| --- | --- | --- |
| Which account is linked, whether receiving is healthy | `telegram_account_read` | `skill_view(name="telegram-tools:account")` |
| Finding a chat, reading it, topics, search and older history | `telegram_chat_read` | `skill_view(name="telegram-tools:chats")` |
| Reading or changing the sync list for supergroups and channels | `telegram_sync_read`, `telegram_sync_add`, `telegram_sync_remove` | `skill_view(name="telegram-tools:sync")` |
| Sending a text or a reply | `telegram_message_send` | `skill_view(name="telegram-tools:sends")` |
| Saving received files, unpacking an archive, sending files | `telegram_file_save`, `telegram_file_send` | `skill_view(name="telegram-tools:files")` |

Editing, deleting, reacting, pinning and marking read are not available here.
This file holds only what is particular to Chat.

It is not your Telegram bot: the chat and topics where the user talks to you
belong to the gateway.

## What stays in Chat

The user's own direct requests: "Telegram の未読ある？", "〇〇さんとのやり取り見せて",
"このファイル保存して", "さっきの返信を送って", "△△も同期して", "□□はもう要らない".
Do them inline with the tools.

- A received message to interpret or answer follows `message-reply.md` for
  meaning and drafting; it is sent only when the user says to send it.
- Collecting many chats or a long history for a document or a summary is
  specialist work: promote it through Plan → Execute.

## In conversation

- A problem `telegram_account_read` reports is the user's to fix in a
  terminal: relay its next step in one line.
- Chat arguments are ID strings from earlier `telegram_chat_read` results,
  never names, usernames or phone numbers. When the request does not make
  clear which chat, use `list` and ask before any send; topic IDs come from
  `topics`, and a reply's message ID must belong to that chat.
- `telegram_chat_read` has `list`, `view`, `topics`, `search`, `around` and
  `fetch` methods. Search covers the mirror only: when nothing is found, say
  so rather than "it was never said". `fetch` pulls older history into the
  mirror. Supergroups and channels need an entry in the sync list.
- Text sends are plain text, at most 4096 characters. Send the exact text the
  user chose; split longer text into several sends only if they agree.
- Every send has a card, and nothing is sent where no one can answer it (a
  scheduled job, a request from another agent). Answering "always" covers
  later calls to the same tool and chat, whatever their text: say so if the
  user asks how to stop being asked, and suggest "once" for anything they
  want to see each time.
- `uncertain` means a send may have gone out: show `details.sent_like_this`
  (or say none was seen yet), ask the user to check the chat in Telegram,
  and never resend unless they confirm it did not arrive. `duplicate: true`
  means it went out once: do not send it again.
- Secret chats are not visible at all — say so when asked.
- Saved files land in `~/Workspaces/.inbox/telegram/`. Archives unpack into
  `<file>.unpacked/` only when requested. Moving a keeper or deleting the
  folder follows the layout in `read_file` of
  `~/.hermes/profiles/assistant/skills/pipeline/references/workspace-layout.md`;
  files from disappearing messages are triaged first.
- A file the user wants sent from outside `~/Workspaces` is copied into the
  workspace first — a draft under `.agent/<YYYYMMDD>-<job>/` — and only when
  the user asked for that file. A saved received file is already in the
  workspace and can be sent on as it is.
- A saved file is delivered with a bare `MEDIA:/abs/path` line.
- Report a send from the tool's result: the chat, and that Telegram accepted
  it, not that anyone has read it.
