---
name: note-com-drafts
description: "Use to save an agreed, unpublished draft to the user's note account, with images, or to update one: previewing the save card, writing, and reading the result."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [note, note-com, note_access, draft, save]
---

# Saving a note draft

Task skills (an article, a marketing job) own the text, the images and the
draft. This skill owns how it is saved. Reading the user's drafts is in
`note-access:note-com`, and checking a body's format in
`note-access:note-com-format`; load both before saving.

## Contract

- **Only the tool, never the browser.** Save with `note`: no typing into
  editor.note.com, and no pasting a draft into the browser to get around a
  refusal.
- **Drafts only.** The tool saves unpublished drafts of the user's main
  account. It cannot publish, delete, like, follow or comment, and cannot add
  a new embed, file, sound, stock chart or paid line. Those stay the user's,
  in the browser: say so.
- **Words are Writer's.** Crafting an article goes through Writer; deciding
  what to post and reading the numbers is Marketer's advice. Your part is
  putting agreed text into note.

## Actions

| Need | Action | Requests |
| --- | --- | --- |
| The card a save would show, without saving | `create_draft` / `update_draft` with `preview=true` | 1 |
| Saving | `create_draft` / `update_draft` | 3 + 2 per new image, +1 for a cover |

## Save

1. **Agree the exact content.** The approval card shows only the draft, the
   title, the images and the start of the text. Show the user the full
   Markdown, or point to the file it came from, and get their OK first.
2. **An update replaces the whole title and body.** Read the draft with
   `draft`, edit that Markdown and send all of it back with `base` set to the
   read's `saved` time; a draft saved since is refused, so read it again and
   redo the edit. Keep every `[…](note-block:…)` line where it is: it is an
   embed, file or sound, and dropping the line removes it. `updatable: false`
   (published, scheduled, a paid area, or too long to read whole) means the
   user edits that draft in the browser.
3. **Preview, then save.** `preview=true` runs every check of the save and
   returns its card without saving. Then the same call without `preview`; its
   card is the user's remote-save consent.
4. **Read the result.**
   - A denial or timeout on the card means nothing was saved. Never retry a
     denied save unchanged.
   - `not saved` means no draft changed. `changed after the approval card` or
     `changed while the images were uploading` means the draft, an image or
     the stored login changed meanwhile: read the draft again, then ask again.
   - `stopped part way` lists what was done: tell the user exactly that.
   - `UNCERTAIN` means read the draft before anything else; never create a
     second draft to recover.
   - On success give the user the `edit_url`. `verified: false` means the
     read-back differed: ask them to look before any further save.

A save in a run nobody can answer (a resident session, cron, a single query)
is refused by the tool; such a run hands the exact save back to its caller
instead. Where no one can answer a card the tool refuses the save and says
why: ask the user to request it in a chat, and do not look for another route.
