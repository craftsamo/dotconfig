---
name: substack-drafts
description: "Use to change the user's own Substack: create or update a draft, publish, schedule or unschedule it, or post a Note, each on an approval card."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [substack, substack_access, draft, publish, schedule, note]
---

# Writing to Substack

Task skills (a campaign, a series of posts) own the text and the timing. This
skill owns how it is written. Reading, status and the Contract of the tool are
in `substack-access:substack`; load it too.

Write only what the user asked for, to the draft they meant. Every write shows
a card on Telegram (or a CLI prompt) and runs only after the user approves it
there. The tool cannot delete a draft, edit a published post, reply to or read
Notes and comments, or change publication settings: say so and leave those to
the user.

## Write

1. Read first: `drafts` for the id, `draft` for the current body before you
   change it.
2. The card shows the facts and about the first 350 characters of the body
   (the rest is counted). For anything longer, show the full final text in
   chat and get the user's agreement first, then send exactly that text in one
   call.
3. Actions:
   - `create_draft` (`title`, `markdown`, optional `subtitle`, `audience` =
     `everyone` / `only_paid` / `founding` / `only_free`). Images are ordinary
     Markdown image tags whose target is an absolute file path under
     `~/Workspaces` (`~/` works too); they are uploaded from a copy frozen at
     the card.
   - `update_draft` (`draft` plus any of `title`, `subtitle`, `markdown`,
     `audience`). `markdown` replaces the whole body: start from the `draft`
     read and keep its `<!-- python-substack-… -->` markers, which preserve
     blocks Markdown cannot express. If the tool refuses because such blocks
     would be lost, ask the user before retrying with
     `replace_unsupported=true`.
   - `publish` (`draft`, `send_email`) — public at once and final. Ask
     whether to email subscribers; never assume. Run `prepublish` first when
     the draft is new to the user's eyes.
   - `schedule` (`draft`, `at` with a UTC offset such as
     `2026-10-06T09:00+09:00`, `send_email`); `unschedule` (`draft`).
   - `note` (`text`) — a public Note, visible at once.
4. Denied or timed out → nothing was changed; say so and never call the same
   write again unchanged. A card made for a draft that has since changed is
   refused at run time: read it again and ask anew.
5. `not done: …` → nothing was published, saved or posted (an "already done"
   list names earlier steps that did happen, such as the email setting before
   a schedule). Report the reason; call again only after fixing it, for a new
   card.
6. `UNCERTAIN: …` → it may have happened. Look with the action the message
   names (`drafts`, `draft`, `published`), tell the user what you see, and
   never repeat the write without the user's say-so. A Note cannot be read
   here: ask the user to look.

Writes need a person to approve each one: in cron, a single query or an
inbound A2A request the tool refuses them. Do not schedule a job that is meant
to write to Substack; schedule a reminder for the user instead.
