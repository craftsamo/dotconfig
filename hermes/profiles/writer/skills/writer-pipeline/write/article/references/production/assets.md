# Article Production Notes

Internal insertion markers are `[[image:id]]`, `[[embed:id]]` and
`[[table:id]]`, with a stable lowercase ASCII slug as the ID. They are
authoring instructions, never platform syntax or publishable body text.
Use them only when the task actually needs a placement requirement.

Keep the associated notes next to the draft as `<draft-stem>.production.md`.
Use the record keys `ID`, `Kind`, `Placement`, `Purpose`, `Source`,
`Requirements`, `State`; values may follow the artifact's language.
Record kind (photo/diagram/screenshot, embed or table), placement/purpose,
actual supplied path/URL/data or explicit missing status, requirements and
unresolved next action in State. Reference an existing matching
ID when intentionally reusing an asset; do not create conflicting records.

Example of an explicitly missing screenshot requirement:

```text
Body: [[image:save-location]]
ID: save-location
Kind: screenshot
Placement: after the paragraph explaining where to select the save location
Purpose: show where the user can confirm the save location
Source: not supplied
Requirements: actual application screen, without personal information
State: needs-assets; requester must arrange capture, not Writer
```

Under supplied-only, request a decision if a required asset is absent.
Under plan-missing, a text draft may carry markers and these notes; report
needs-assets rather than a publication-ready article. This permits planning,
not generation, capture, upload, spending or a new tool grant.

For supplied assets, use the destination-supported representation and real
paths/URLs. Alt text describes an inspected image or attributed supplied
description; it is not inferred from a planned image that does not exist.
Table data and embed targets need actual sources, not plausible filler.

Editor-only actions (for example applying a rich-text heading or inserting
media) also belong in these notes, outside the publishable body. Do not use
HTML comments to hide instructions: hiding/import behavior is not portable.
Resolve markers only after the corresponding asset/action is satisfied;
never delete one merely to produce a superficially clean final file.

QA: every marker has an unambiguous note, referenced sources match the
requested role, actual media is distinct from a style example, and unresolved
assets/editor steps are reported. Text acceptance does not verify the final
render. The producer/requester handles assembly and publication separately.

## Give the Asset a Reader Role

If an asset carries evidence or explains a difficult step, state the precise
reader-visible intended role before specifying production work. A caption
explains relevance; alt text conveys known image content; an instruction
such as "capture the settings panel" belongs only in Requirements or State.
Do not make all three repeat the same vague "help the reader understand."

Locally authored example (assume a supplied `settings.png` and description):
Map `[[image:save-location]]` to the existing `save-location` ID and that
supplied file only. Purpose: help readers locate the destination selector.
Requirements can distinguish intended caption "Choose the destination here"
from intended alt "Settings panel with a destination selector," attributed
to the supplied description until inspected, and production work "insert
after the destination paragraph." None claims the editor step occurred.
If the file was not supplied, keep Source: not supplied and State: needs-assets;
the proposed role is not evidence from which to invent visual details or a URL.
Reason: the mapping separates reader meaning, source evidence and assembly.

Retain: a stable ID reused where the same asset genuinely serves both passages.
Do not create a duplicate just to match section numbering, or delete a missing
marker to pass QA. A clear passage needs no decorative screenshot by default.

QA evidence: trace marker to ID, actual source or explicit missing status,
placement and the sentence it helps explain. Check caption and alt claims
against inspected content or attributed descriptions, not the requested image.
Quote any production instruction leaking into reader text and report unresolved
work without calling the planned caption or placement an observed render.

Local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
(concrete grounding) and [readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(reader purpose); asset fields, caption/alt distinctions and the example are local adaptations.
