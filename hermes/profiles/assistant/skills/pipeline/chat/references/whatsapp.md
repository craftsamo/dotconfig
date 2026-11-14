# WhatsApp

The `whatsapp_*` tools are the only way to the user's WhatsApp accounts —
never `wacli` or the package's CLI in the terminal, the state directory, the
`~/.wacli` store, WhatsApp Desktop's data or WhatsApp Web. Load the skill for
the work before the first call; each owns its tools' mechanics:

| Work | Tools | Skill |
| --- | --- | --- |
| Which accounts are paired, whether the sync service is healthy | `whatsapp_account_read` | `skill_view(name="whatsapp-tools:account")` |
| Finding a chat, reading it, searching, older history | `whatsapp_chat_read`, `whatsapp_history_backfill` | `skill_view(name="whatsapp-tools:chats")` |
| Counting chats or replies over a period | `whatsapp_chat_read` | `skill_view(name="whatsapp-tools:count-activity")` |
| Finding a contact, checking whether a number is on WhatsApp | `whatsapp_contact_read` | `skill_view(name="whatsapp-tools:contacts")` |
| Sending a text or a reply | `whatsapp_message_send` | `skill_view(name="whatsapp-tools:sends")` |
| Saving received files, unpacking an archive, sending files | `whatsapp_file_save`, `whatsapp_file_send` | `skill_view(name="whatsapp-tools:files")` |
| Marking read, archiving, muting, pinning, reacting, editing or deleting the user's own message | `whatsapp_chat_mark`, `_archive`, `_mute`, `_pin`, `whatsapp_message_react`, `_edit`, `_delete` | `skill_view(name="whatsapp-tools:actions")` |

Grants are not available here. This file holds only what is particular to
Chat.

## Which account

Load `skill_view(name="whatsapp-accounts")` before choosing an account: it
names each account, what it is for and any account-specific technic to load.
Unsure which one a request means → ask; never search every account to guess.

## What stays in Chat

The user's own direct requests: "WhatsApp で何か来てる？", "このお店とのやり取りを
要約して", "この写真を保存して", "この番号って WhatsApp 使ってる？", "これを送って",
"このチャット既読にして". Do them inline with the tools.

- Interpreting a received message or drafting a reply → `message-reply.md`
  owns the meaning and the drafts. A draft is sent only when the user says to
  send it, with the exact text they picked.
- A reply that grows into a crafted piece, or an outbound batch → promote it
  through Plan → Execute; come back here to send.

## In conversation

- A problem `whatsapp_account_read` reports is the user's to fix in a
  terminal: relay its next step in one line.
- Chat arguments are JIDs from earlier `whatsapp_chat_read` results (or the
  `chat` a number check gives), never names. When the request does not make
  clear which chat, list and ask before any write. Reads cover the mirror
  only: when nothing is found, say so rather than "it was never said".
- Every write has a card, and nothing is written where no one can answer it
  (a scheduled job, a request from another agent). There are no send
  mandates: a send that repeats every day still asks each time. Answering
  "always" covers later calls to the same tool and chat, whatever their
  text: say so if the user asks how to stop being asked, and suggest "once"
  for anything they want to see each time.
- Actions only on the user's word: marking a chat read tells no one unless
  they ask for read receipts too; deleting or editing is for the user's own
  message, and only the one they named.
- `uncertain` means a write may have happened: read the chat back, show what
  it found (or that it found nothing), ask the user to check on the phone,
  and never repeat it unless they confirm it did not happen.
- Saved files land in `~/Workspaces/.inbox/whatsapp/<account>/<chat>/<message>/`.
  Archives unpack into `<file>.unpacked/` only when requested. Deliver with a
  bare `MEDIA:/abs/path` line. Moving a keeper into a Group's typed surface or
  a draft job, or deleting the folder, follows the layout in `read_file` of
  `~/.hermes/profiles/assistant/skills/pipeline/references/workspace-layout.md`.
- A file the user wants sent from outside `~/Workspaces` is copied into the
  workspace first — a draft under `.agent/<YYYYMMDD>-<job>/` — and only when
  the user asked for that file. A saved received file is already in the
  workspace and can be sent on as it is.
- Report a write from the tool's result: the chat, and for a send that
  WhatsApp accepted it, not that anyone has read it.
