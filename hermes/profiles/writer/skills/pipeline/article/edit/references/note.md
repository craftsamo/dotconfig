# Editing note Drafts

A note draft's source is Markdown in the `note` tool's dialect (`##`/`###`
headings, flat lists, quotes, code blocks, bold, strike, links, alignment
arrows, images on their own line; the tool's description lists it). A draft
read from note marks embeds, files and sounds as `[label](note-block:…)`
lines: keep each where it is, since removing the line removes the block.
Keep its image lines with `https://assets.st-note.com/…` addresses as they
are too: an update keeps such an image only where the draft already has it.
Preserve existing editor intent when revising a source draft: link targets,
quote/code boundaries, headings, captions and alt text are distinct content,
not decorative punctuation to strip indiscriminately.

Italic, inline code, HTML and footnotes have no note form and are saved as
typed; tables, HTML comments and unresolved insertion markers are refused by
a save. Do not introduce any of them. One already in the source stays unless
the scope covers it, and is reported: an existing table needs the requester's
choice of a list or an image, not a silent conversion. Do not remove
meaningful emphasis or a data table merely to make the source look cleaner.

A request for a warmer voice does not authorize a new anecdote or personal
emotion. Keep actual experiences and the original level of certainty.

Documentary sources (checked 2026-09-08):
- https://www.help-note.com/hc/ja/articles/360012426133
- https://www.help-note.com/hc/ja/articles/4410617032217

## Preserve the Voice While Clarifying

If the requested wording pass covers a tangled recollection, clarify who
observed what without strengthening the interpretation. A structure edit may
give a supplied turning point more space and shorten routine transitions;
wording scope does not authorize moving sections or changing story pacing.
Use the known reader and voice, not a presumed preference for emotional prose.

Locally authored example (wording scope, unprotected narrative prose):
Before: "What I thought was that the shorter meeting perhaps helped."
After: "I thought the shorter meeting might have helped."
Reason: removing the empty framing makes the interpretation easier to follow
while preserving its epistemic strength. "The shorter meeting helped everyone"
would invent certainty and other people's experience. A warmer tone request
does not authorize that change or a new anecdote.

Retain: a meaningful pause, colloquial quotation or short transitional section
that carries the author's voice. Do not impose equal section lengths or
conclusion-first storytelling. In proofread scope, leave grammatical style
choices alone; with no qualifying errors, deliver a verified byte-identical
no-op, including line breaks. Protected text is not a polishing opportunity.
The output remains a source draft, not a saved or live note edit.

QA evidence: quote the original observation and qualifier beside the revision;
check that headings and the ending do not claim more than the source does.
For authorized pacing changes, explain the particular reader benefit and
verify chronology survived. Run the `note` tool's `check` on the revised file
(or say it was not available) and report errors, markers and `as_typed` items
with their lines; a no-op is checked too but never changed to pass. Separate
applied corrections, uncertainties and optional suggestions; keep editor work
outside reader-visible narrative.

Local adaptation of [natural-japanese v1.5.0 genre notes](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md)
(essay latitude) and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(retain voice, do not invent stance); note-specific handling and the example are local.
