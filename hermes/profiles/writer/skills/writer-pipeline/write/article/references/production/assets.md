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
