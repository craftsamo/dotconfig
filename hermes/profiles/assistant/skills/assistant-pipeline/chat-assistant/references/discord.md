# Discord

Load `skill_view(name="discord-access:discord-account")` before any work in the user's own
Discord account: it owns the mechanics — the `discord_account` tool only
(never the terminal, the token, the mirror files or Discord in the browser),
low traffic, which action to read with, the sync list, files, collecting
history, writes and their cards, outcomes, and roles. This file holds only
what is particular to Chat.

The account is the user's (CraftSamo, @craftsamo). It is not your Discord
bot: the server channel where the user talks to you is the gateway's.

## What stays in Chat

The user's own direct requests: "〇〇さんとの DM 最近どうなってる？",
"このメッセージに 👍 付けて", "さっきの返信を送って", "△△サーバーも同期して",
"このロールを外して". Do them inline with the tool.

- A received message to interpret or answer follows `message-reply.md` for
  meaning and drafting; it is sent only when the user says to send it.
- Collecting many channels or a long history for a document, an inventory or
  a summary is specialist work: promote it through Plan → Execute; the
  skill's collection procedure applies there.
- Write tests ("できるか試して") go to the user's own test server
  「開発テスト」 and its test channels, never to a community server. If a
  channel name matches in more than one server or category, say which one you
  picked and that near-matches exist.

## In conversation

- Files from a message land in `~/Workspaces/.inbox/discord/<channel>-<message>/`.
  Deliver with a bare `MEDIA:/abs/path` line. Moving a keeper into a Group's
  `assets/` or deleting the folder follows the user's OK
  (`~/Workspaces/AGENTS.md`).
- A file to attach must be under `~/Workspaces`; one elsewhere (a download,
  say) is the user's to move there first, or to send from the app.
- Report what changed from the tool's result: the chat, the target, and what
  was left alone. For an `UNCERTAIN` result, say what the read-back showed and
  let the user decide.
