---
name: chat-assistant
description: "Chat: handle inline conversation, lookups, received messages (meaning and reply drafts), work reports and workspace tasks. Register recurring requests; promote specialist production to Plan and Execute, never dispatch inline."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["chat"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
When the kernel body is missing, load:

```text
skill_view(name="assistant-pipeline")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Chat mode — inline execution

Load for work you do yourself: no dispatch, no ack/notification
mechanics. Most of it ends in one turn; your own multi-turn work (a report,
registry or ledger upkeep, Admin maintenance) stays here across turns.

## What stays in Chat

- **Conversation / emotion / opinion** — no tools, maybe the memory tool.
- **Single quick lookup** (one URL / fact / file) — light tools, deliver
  in a minute or two.
- **Workspace data ops** via the workspace skills — `references/workspace-ops.md`.
- **A received message** to interpret or answer ("what does this mean?", help
  replying, "does this work?") — `references/message-reply.md`.
- **A work report** (週報, 月報, weekly/monthly report) or feedback for one —
  `references/work-report.md`.
- **Recurring request** ("every morning …") — register a cron job —
  `references/cron.md`.
- **Medium parallel lookups** for a waiting user — `references/lookups.md`
  (`delegate_task`).
- **The user's Google Sheets, Gmail, Drive and gcloud** (reading, counting
  and editing sheets, mail search and replies, Drive downloads and uploads,
  cloud resources) — only through `google_sheets`, `google_gmail`,
  `google_drive` and `gcloud`, never the terminal or editing in the browser;
  every change waits for approval on its card. Any sheet work loads
  `skill_view(name="google-access:google-sheets")` first — `references/google.md`.
- **The user's WhatsApp** (reading chats, saving a file someone sent,
  checking a number, counting chats or replies, sending a message or a
  workspace file) — only through the `whatsapp` tool, never the terminal or
  WhatsApp Web. Any WhatsApp work loads `skill_view(name="whatsapp-access:whatsapp")` first —
  `references/whatsapp.md`.
- **The user's Signal** (reading chats, saving a file someone sent, checking
  a number, sending a message or a workspace file) — only through the
  `signal` tool, never the terminal or Signal Desktop; every send waits for
  approval on its card. Any Signal work loads `skill_view(name="signal-access:signal")`
  first — `references/signal.md`.
- **The user's own Discord account** (their DMs and servers, threads, pins,
  mentions, friends, syncing a server, sending, reacting, pinning, editing or
  deleting their own message, managing a server's roles) — only through the
  `discord_account` tool, never the terminal or Discord in the browser. Any
  Discord account work loads `skill_view(name="discord-access:discord-account")` first —
  `references/discord.md`.
- **The user's own Telegram account** (their chats, groups and channels,
  syncing a supergroup or channel, sending a message or a workspace file — not
  this chat with you) — only through the `telegram_account` tool, never the
  terminal or a Telegram app. Any Telegram account work loads
  `skill_view(name="telegram-access:telegram-account")` first — `references/telegram.md`.
- **X (Twitter)** (the user's posts and mentions, a post or thread, a
  profile, a post's media, checking posts' real authors and counts) —
  read-only, only through the `x` tool, never the terminal or x.com in the
  browser, except saving a post draft or finishing an X Article draft the
  user asked for (saved draft only, never published). Any X work loads
  `skill_view(name="x-access:x-twitter")` first — `references/x.md`.
- **note (note.com)** (articles, creators, comments, the user's drafts and
  stats, checking a draft body's format, saving an agreed unpublished draft
  with images) — only through the `note` tool, never the terminal or the note
  editor in the browser; nothing publishes. Any note work loads
  `skill_view(name="note-access:note-com")` first — `references/note.md`.
- **The user's own Substack** (reading publications, their inbox, drafts and
  stats; drafting, publishing, scheduling, posting a Note) — only through the
  `substack` tool, never the terminal or substack.com in the browser; every
  write waits for approval on its card — `references/substack.md`.
- **YouTube** (a video, its comments or transcript, search, the user's
  channels' videos, analytics and settings, downloading a video; editing a
  video, thumbnails, replying to or moderating comments, uploading, captions,
  playlists, channel settings and watermark) — through the `youtube` tool,
  never the terminal or yt-dlp; every write waits for approval on its card.
  YouTube Studio in the browser only for channel settings the tool cannot
  change (name, handle, picture, banner, links, upload defaults), each after
  a `clarify` yes. Any YouTube work loads `skill_view(name="youtube-access:youtube")` first
  — `references/youtube.md`.
- **Blockchains and the user's web3 wallets** (a transaction, block,
  address, token, approval, balance, price, contract or program on an EVM
  chain or Solana; the user's accounts, a new Hermes wallet, sending a coin
  or token, revoking an approval) — only through the `evm` and `solana`
  tools, never the terminal, the Keychain, a block explorer or a browser
  wallet; a new wallet, a revoke, and a transfer to anyone but the user's own
  Hermes wallets, wait for approval on its card — `references/web3.md`.

## Leaves

| Leaf | When |
| --- | --- |
| `references/workspace-ops.md` | people / household-budget / projects ledger ops; the sensitive-data rule |
| `references/message-reply.md` | interpreting a received message and copy-ready reply drafts |
| `references/work-report.md` | building a periodic work report through the `work_report` tool |
| `references/cron.md` | registering or changing scheduled recurring jobs |
| `references/lookups.md` | in-turn parallel lookups via `delegate_task` |
| `references/google.md` | the user's Google account: Sheets (mechanics in the `google-access:google-sheets` skill), Gmail reads and approved sends, Drive downloads and approved uploads, gcloud reads and approved commands |
| `references/whatsapp.md` | the user's WhatsApp accounts in Chat: which account a request means, replies, files and the inbox folder (mechanics in the `whatsapp-access:whatsapp` skill) |
| `references/signal.md` | the user's Signal account in Chat (mechanics in the `signal-access:signal` skill): replies, files to send, the inbox folder |
| `references/discord.md` | the user's own Discord account in Chat (mechanics in the `discord-access:discord-account` skill): what stays inline, the test server, files and reports |
| `references/telegram.md` | the user's own Telegram account in Chat (mechanics in the `telegram-access:telegram-account` skill): what stays inline, choosing the chat, files and reports |
| `references/x.md` | reading X as the sub-account, verifying posts, downloading a post's media, and when an X Article draft may be finished in the browser |
| `references/note.md` | reading note.com and the user's drafts and stats, checking a body's format, and saving an approved unpublished draft |
| `references/substack.md` | reading Substack and the user's own publication, and approved drafts, releases and Notes |
| `references/youtube.md` | reading YouTube, transcripts and downloads, the user's channels' videos, analytics and settings; approved edits, replies, moderation, uploads, captions, playlist and channel changes; Studio-only channel settings |
| `references/web3.md` | EVM chains and Solana through the `evm` and `solana` tools: reading transactions, blocks, addresses, tokens, approvals, balances, gas and prices, analysing contracts and programs; the user's Hermes and watch-only wallets, quotes, approved transfers and their outcomes |

## Promotion

Promote by what the work is, not by how long it takes. The moment it becomes
specialist production — media or other creation, writing a crafted piece,
deep or sustained research, code changes — or needs rounds of taste feedback
on a produced artifact, stop and route through Plan → Execute (a resident
session). Starting inline and promoting is normal; doing a
specialist's job inline is not.

Your own work stays in Chat however many turns or tool calls it takes: the
workspace registry and ledgers, work reports, message replies, cron, and Admin
upkeep. Keep bulky reading out of your context: hand wide reading to
`delegate_task` (`references/lookups.md`) and keep only the summary.
