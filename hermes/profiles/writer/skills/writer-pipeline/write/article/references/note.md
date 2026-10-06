# note Articles

A note draft is saved from Markdown in the `note` tool's dialect, so the
source draft is written in it; the requester saves it, never Writer. The
tool's description lists the dialect, and its `check` action (`path` = the
draft file, or `body`) says whether a save would accept the format, without
contacting note or the user's account.

The title is not part of the body: name it separately (the requester passes
it as `title`). The body starts at its first `##` heading or paragraph, never
a `#` title line.

| Expression | Source handling |
| --- | --- |
| Headings | `##` and `###` only; a deeper level becomes `###` or bold text |
| Lists | Flat only; a nested point becomes its own item or a sentence |
| Images | A line of its own, `![caption](/absolute/path "alt text")`, from a supplied local file under ~/Workspaces; never a web address |
| Italic, inline code, HTML, footnotes | No note form: saved as typed. Use bold, plain words or a code block |
| Tables | No note form, and a table row is refused: a list, or a separate image-of-table asset job |
| Embeds, files, sounds, a paid line | The user adds them in the browser after the save: record them as editor operations |

Write image paths in full: a relative path is read from ~/Workspaces, not
from the draft's folder. Unresolved `[[image:id]]`, `[[embed:id]]` and
`[[table:id]]` markers keep the draft needs-assets and are refused by a save;
`check` lists them under `markers`. Never drop one to make the check pass.

Follow the requested voice rather than a stereotype of the platform. An
experience-led article requires real supplied experiences. Do not add a
personal anecdote, emotional confession or subscription appeal by default.

Sources:
- https://www.help-note.com/hc/ja/articles/360012426133
- https://www.help-note.com/hc/ja/articles/4410617032217

## Give the Story Appropriate Space

If the brief asks for an experience-led piece, let a supplied turning point
carry more detail than routine transitions. If it asks for an explanation,
make the reader's question easy to locate instead. The requested voice and
reader govern section pacing; note itself does not require intimacy.
Keep epistemic strength intact when making an opening or heading more direct.

Locally authored example (illustrative supplied-account scenario):
Account: "I moved the desk near the window. I felt less distracted that day.
I do not know whether the move helped."
Draft: "I moved the desk near the window. That day I felt less distracted,
though I do not know whether moving the desk made the difference."
Reason: the event and the participant's observation stay connected without
turning one day into proof. "A new desk position restored my focus" would
invent both certainty and a stronger personal story.

Retain: an intentional pause, modest heading or unresolved ending that fits
the supplied voice. Do not force a conclusion-first opening, confession or
equal paragraph lengths. An independent list can remain a list rather than
being expanded into a narrative the source does not contain.
This is a source draft; story polish does not show how the saved page reads.

QA evidence: quote the event, the attributed interpretation and the limiting
phrase, then check the title and section headings for a stronger assertion.
Explain why the longest section deserves that space for the stated reader.
Run `check` on the delivered file and report its result: `ready` with no
`markers`, or each error and marker with its line, and each `as_typed` item
either kept on purpose or rewritten in a note form. Without the `note` tool
in this run, say the format check was not run. Report needed editor
operations separately from reader-visible prose; a passed check is a format
verdict, not a page-render one.

Local adaptation of [natural-japanese v1.5.0 genre notes](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md)
(essay latitude) and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(selective depth, preserved author stance); note pacing and the example are locally authored.
