# Telegram and Signal sends without a card only inside a send mandate

Status: in force
Owner doc: docs/telegram-access.md and docs/signal-access.md "Send mandates"

## Decision

A text send runs without its approval card only when it fits one send mandate
the user approved on a card of its own. A mandate belongs to one service
(Telegram or Signal) and one signed-in account, and names:

- the chats it covers, one to five, each by its id with the name, kind and
  identity the card showed (a group or a person; never a broadcast channel); the
  identity is the handle the plugin's send card shows, and the account is named
  as that card names it;
- how many sends an hour it allows (1 to 30) and the longest text (at most
  1000 characters);
- a purpose in one line, and an end at most 30 days out.

A send fits only when it is plain text to one of those chats from that account,
within the length, with no file, no quoted message and no reply, and the hour's
count is not used up. Anything else asks on its card as before. A mandate is
never made by another mandate, and revoking one needs no card and ends it at
once.

The hook decides a send is covered and records which mandate; the handler
checks again at the write that the mandate is still in force, that the chat and
account are the same, that the text is within the bound, and counts the send
before it goes out. A send that no longer fits is refused with nothing sent.
Inside a mandate a send also runs where nobody can answer a card, such as a cron
job. A read, a send outside a mandate and a send that does not fit keep the
rules of the access doc.

Mandates are stored by the shared mandate store
(`plugins/_shared/mandate_store.py`) under the plugin's own state directory,
and the sends they cover are counted in a MAC'd ledger beside them, which opens
with a MAC'd row per mandate. A service that never made a mandate has no head,
and its sends do not read the Keychain.

## Why

- A report that goes to the same chat every morning needs no one to tap a card,
  but a prompt-injected agent must not be able to message anyone it likes: the
  chats, the count, the length and the end are the user's, read from a card.
- The chats are the bound that matters: text is chosen by the agent, so the
  harm of an injected instruction is limited to a few words to a few chats the
  user named, for a few days. A name is the other person's choice, so the card
  shows each chat's handle whole beside it, and only the name is ever shortened.
- Files, quotes and replies carry more than the user read on the card (a local
  file, a message from someone else), so they always ask.
- A broadcast channel reaches an audience the user cannot list on a card.
- Counting before the send, and also when it fails or is uncertain, keeps the
  hourly bound whatever happens to the request.
- A deleted, emptied or replaced ledger reads as used up, never as unused, so
  the MACs and the opening rows leave only removed use rows to the file guard
  and the 30-day ceiling.

## Do not

- Cover a file, a quote, a reply, a chat the card did not name, or another
  account, whatever the terms say.
- Let a mandate be made without its own card, from a cron job, a single query
  or an inbound request, or let one raise its own bounds.
- Decide what is in force from the history file: only the MAC'd head does.
- Count a send after it went out, or only when it succeeded.
- Read a missing, unreadable or linked ledger as zero uses, or follow a link to
  write to it.
- Clip a chat's identity on the card, or show a chat by its name alone.
- Keep the MAC key anywhere a profile receives, or open the state directory to
  file or terminal calls.
- Remove the 30-day ceiling: a forgotten mandate should lapse on its own.
