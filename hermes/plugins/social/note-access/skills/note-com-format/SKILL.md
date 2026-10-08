---
name: note-com-format
description: "Use before a note draft body is shown to anyone for approval: checking with note's offline `check` that a Markdown body will be accepted, and what would be saved as typed."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [note, note-com, note_access, markdown, check, format]
---

# Checking a note body

`check` costs nothing and contacts nothing: it tells whether a Markdown body
would be accepted by note and what would be saved as typed. It needs no
session.

## Prepare the body

Bodies are Markdown in the tool's dialect, which its description lists. The
title is not part of the body: pass it as `title`, and drop a leading `# …`
line from a Writer file rather than sending it. Run `check` (`path` = the
draft file, or `body`; add `title` and `eyecatch` when known) before the body
is shown to anyone for approval:

- `errors` are refused by a save, each with its line. A markup-only fix (a
  heading level, a flattened list, an image moved to its own line) is
  yours when the words, URLs and qualifications stay; show the user the
  changed text. A fix that changes words goes back to whoever owns the words
  (Writer), not to you.
- `markers` (`[[image:…]]`, `[[embed:…]]`, `[[table:…]]`) are assets that do
  not exist yet. Never delete one to pass: ask whose job the asset is.
- `as_typed` lists Markdown note has no form for (italic, inline code, HTML,
  footnotes), saved with its marks. Keep an item only on purpose; otherwise
  change the markup, as above.
- Images are local JPEG, PNG, GIF or WebP files under ~/Workspaces, up to
  20 MB, at most 20 new per save; a relative path is read from ~/Workspaces,
  not from the draft's folder. A web address is never uploaded: save a wanted
  image locally first, and only with the user's OK about its rights.
- The cover (`eyecatch`) is up to 10 MB; note fits it to 1280:670, so tell
  the user when `cover.note` says it is another shape.
- `web_images` and `kept_blocks` are valid only in an update of the draft
  they were read from.
