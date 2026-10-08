# Counting from WhatsApp

How to count chats, sends and replies over a period. The task skill says
what is counted and where it is reported; this file says how the count is
made so it holds up.

## Collect

1. **Every candidate chat.** `chats` paged with `offset` = `next_offset`
   until `complete: true` (archived chats are included). Keep every chat
   whose last activity could fall in or after the period. A page is a
   bounded window: a count is complete only when paging reached `complete`.
   If it cannot finish, report what was covered and call the count
   incomplete — never answer "none" from a partial list.
2. **Read each chat** with `messages` (`after` = the period start, paging
   with `before` while `more` is set). Do not count by list labels or
   `last_message` times: those can come from hidden protocol rows. Before
   calling a chat new, also read before the period start (`before` = the
   period start): whether anything earlier exists decides new vs existing.
3. **Checkpoint to a file.** Save each chat's rows (chat jid, message id,
   time, `from`, text or media) as JSON in the job's working folder as you
   read, so an interrupted pass resumes instead of restarting.

## Compute

- **In a saved script, never by hand or from recall.** Deduplicate by chat
  jid and message id, then classify from message times:
  - **new outbound** — the chat's first message falls in the period and is
    `from: me`, with nothing earlier in the chat;
  - **existing conversation** — earlier messages exist;
  - **inbound** — split into human and automatic by reading. Automatic is
    the boilerplate family (`(AUTO REPLY)`, "unavailable right now",
    "respond as soon", "Thank you for contacting", office hours, numbered
    service menus), including one that opens with a personal-looking
    greeting.
- **Direction before characterising.** An inbound message right after our
  outbound is a response; only a message with no earlier outbound in the
  chat is "they contacted us". Who owns the ball comes from the last
  message's direction.
- **A refusal is a reply.** A human "no" counts as a human reply, never as
  ignored or no-response. A one-word acknowledgement ("Ok") is a reply too.
- **Joining to another record** (a sheet, a list): join by a normalised
  phone number taken from an `@s.whatsapp.net` jid or a contact's `phone`.
  An `@lid` jid carries no number; such chats stay unmatched and are
  reported as their own line unless the task's own rules accept direct
  evidence of identity — never a fuzzy match by name.

## Report

- **State what the mirror cannot see.** History from before the account was
  paired is thin: `backfill` the chats that matter, and turn what stayed
  unreachable into an explicit bound ("max +N"), not a silent drop or a
  guess. This bound is a coverage limit, not a hand-count margin.
- **Who sent it.** On an account several people use, `from: me` is the
  account, not a person: attribute it to "our side" unless the task's own
  send record says who sent it.
- **A saved count is a snapshot.** Re-read any chat you are about to act on;
  a chat filed as automatic last week can hold today's human reply.
- Keep raw phone numbers and message bodies out of summaries; quote only
  where the wording is the evidence.
