# Editing Production Notes

`[[image:id]]`, `[[embed:id]]` and `[[table:id]]` are internal insertion
requirements. IDs are stable lowercase ASCII slugs, not generated URLs.
The companion path is `<draft-stem>.production.md`.

Record keys are `ID`, `Kind`, `Placement`, `Purpose`, `Source`,
`Requirements`, `State`; values may follow the artifact's language.
Kind identifies the media/table; Source is an actual supplied path/URL/data
or explicit missing status. State includes the open next action and owner.

For a changed placement, preserve the ID and update Placement. For a supplied
replacement, retain the purpose and protected requirements unless the change
request modifies them. Do not rename record fields to make the prose smoother.
An existing nonstandard note may be retained if its mapping is unambiguous;
ask when a required field or source cannot be recovered rather than guessing.

One ID has one unambiguous record. Intentional reuse points to the same
record; conflicting duplicate records must be resolved before the edit is
complete. A removed requirement needs explicit authorization and a reported
ID disposition. Resolve a marker only when its asset/action is satisfied,
never merely to hide needs-assets or needs-editor. Resolving a source-level
reference does not prove a rendered preview or publication.

## Keep Meaning Attached to the Asset

If an authorized section move changes where an asset helps the reader,
update Placement while preserving its stable ID and source. Separate the
reader-visible intended role, caption and alt text from production instructions.
A clearer caption may explain relevance; it must not describe unseen details
or turn an intended illustration into proof of the adjacent claim.

Locally authored example (authorized move, supplied `settings.png`):
Keep `[[image:save-location]]` mapped to ID `save-location` and the supplied
file; change Placement from "after Setup" to "after Choose a destination."
Retain the intended caption "Destination selector" and alt text grounded in
the supplied description. Record "move the image in the editor" as production
work, not as caption text or an action already completed.
If the source file is absent, retain Source: not supplied and State: needs-assets;
do not replace the marker with a plausible upload URL or delete it to pass QA.
Reason: the reader role follows the section without losing asset identity.

Retain: an unambiguous existing mapping and useful caption. A typo fix elsewhere
does not authorize changing asset records, caption wording or layout. Missing
notes block only a change that requires interpreting them, not unrelated edits.
Protected markers stay unchanged; a no-op must not manufacture note updates.

QA evidence: compare before/after placement and marker-to-record mapping,
quote the request authorizing the move, and identify the supplied source or
explicit missing state. Check any caption/alt changes against inspected content
or attributed descriptions. Report unresolved assembly separately from the
source edit, leaving unrelated records untouched and never implying a preview.

Local adaptation of [natural-japanese v1.5.0 revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(selective revision, material gaps) and [readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(reader purpose); asset mapping, caption/alt boundaries and the example are local adaptations.
