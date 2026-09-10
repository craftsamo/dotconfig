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
