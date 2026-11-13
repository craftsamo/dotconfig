# Discord

The `discord_*` tools are the only way to the user's own Discord account —
never the terminal, the token, the state directory, the Keychain, the Discord
app's data or Discord in the browser. Load the skill for the work before the
first call; each owns its tools' mechanics:

| Work | Tools | Skill |
| --- | --- | --- |
| Which account is signed in, token and sync health | `discord_account_read` | `skill_view(name="discord-tools:account")` |
| Which servers and channels the sync follows, adding or removing them | `discord_sync_read`, `discord_sync_add`, `discord_sync_remove` | `skill_view(name="discord-tools:sync")` |
| Servers, channels, DMs, messages, threads, pins, older history | `discord_chat_read` | `skill_view(name="discord-tools:chats")` |
| Searching by words, links or files | `discord_search_read` | `skill_view(name="discord-tools:search")` |
| Mentions, what waits for a reply, saved messages, marking read | `discord_inbox_read`, `discord_saved_add`, `discord_saved_remove`, `discord_read_mark` | `skill_view(name="discord-tools:inbox")` |
| Friends, a member, server info, roles, emoji, events, invites | `discord_people_read`, `discord_server_read` | `skill_view(name="discord-tools:people")` |
| Sending a text, a reply or files | `discord_message_send`, `discord_file_send` | `skill_view(name="discord-tools:sends")` |
| Counting messages, exporting a chat's history to a file | `discord_history_read`, `discord_export_create` | `skill_view(name="discord-tools:history")` |
| Saving received files, unpacking an archive | `discord_file_save` | `skill_view(name="discord-tools:files")` |
| Editing or deleting the user's own message, reactions, pins | `discord_message_edit`, `discord_message_delete`, `discord_reaction_*`, `discord_pin_*` | `skill_view(name="discord-tools:actions")` |
| Giving, taking, creating, editing and deleting a server's roles | `discord_role_read`, `discord_role_*` | `skill_view(name="discord-tools:roles")` |

Creating threads and forum posts is not available here. This file holds only
what is particular to Chat.

The account is the user's (CraftSamo, @craftsamo). It is not your Discord
bot: the server channel where the user talks to you is the gateway's.

## Text or sound: two routes

The `discord_*` tools read and write **text**: messages, threads, pins, files,
roles. A voice channel, a stage or a Go Live stream has no text to read there;
its text tab shows only what people typed beside it. When the user asks what
is being **said, streamed or shown** — "配信に参加して内容教えて", "ボイスで
何話してる？", "この通話録っておいて", "配信を見てきて" — do not answer from
the channel's text and do not say you cannot hear: load
`skill_view(name="screen-listen:listen")` and its Discord steps
(`skill_view(name="screen-listen:attend-discord")`) and follow them. They open the
channel in the Discord app on this Mac with `computer_use`, listen or
record with `screen_listen`, look with a capture, report and leave. Use
`discord_chat_read` on the way only to resolve server and channel names to ids
(`servers`, `channels`; a voice channel is `kind: voice`, a stage `stage`).

## What stays in Chat

The user's own direct requests: "〇〇さんとの DM 最近どうなってる？",
"このメッセージに 👍 付けて", "さっきの返信を送って", "△△サーバーも同期して",
"このロールを外して". Do them inline with the tools.

- A received message to interpret or answer follows `message-reply.md` for
  meaning and drafting; it is sent only when the user says to send it.
- Collecting many channels or a long history for a document, an inventory or
  a summary is specialist work: promote it through Plan → Execute; counts and
  exports there follow `discord-tools:history`.
- Write tests ("できるか試して") go to the user's own test server
  「開発テスト」 and its test channels, never to a community server. If a
  channel name matches in more than one server or category, say which one you
  picked and that near-matches exist.

## In conversation

- A problem `discord_account_read` reports is the user's to fix in a
  terminal: relay its next step in one line.
- Chat arguments are ids from earlier `discord_chat_read` results, never
  names. When the request does not make clear which chat, list and ask
  before any write.
- A read answers from the mirror only for a chat the sync marked current in
  the last 15 minutes, otherwise from Discord, a request at a time: keep
  traffic low, and add a server to the sync list rather than reading it live
  over and over. Mirror search finds only what the mirror holds: when nothing
  is found, say so rather than "it was never said".
- Every write has a card, and nothing is written where no one can answer it
  (a scheduled job, a request from another agent). Answering "always" covers
  later calls to the same tool and target: say so if the user asks how to stop
  being asked, and suggest "once" for anything they want to see each time.
  Role changes are asked every time.
- `uncertain` means a write may have happened: show what the read-back found
  (or that it found nothing), ask the user to check in Discord, and never
  repeat it unless they confirm it did not happen.
- Saved files land in `~/Workspaces/.inbox/discord/<channel>-<message>/`.
  Archives unpack into `<file>.unpacked/` only when requested. Deliver with a
  bare `MEDIA:/abs/path` line. Moving a keeper into a Group's `assets/` or
  deleting the folder follows the user's OK (`read_file`
  `~/.hermes/profiles/assistant/skills/pipeline/references/workspace-layout.md`).
- Exports land in `~/Workspaces/.inbox/discord/exports/`; they hold other
  people's words, so they stay there unless the user asks to share one.
- A file to send must be under `~/Workspaces`; one elsewhere (a download,
  say) is copied into the workspace first — a draft under
  `.agent/<YYYYMMDD>-<job>/` — and only when the user asked for that file. A
  saved received file is already in the workspace and can be sent on as it is.
- Report what changed from the tool's result: the chat, the target, and what
  was left alone; for a send, that Discord accepted it, not that anyone has
  read it.
