# Analyzing Production Notes

Recognize `[[image:id]]`, `[[embed:id]]` and `[[table:id]]` as internal
requirements, not native platform syntax. IDs are lowercase ASCII slugs;
their records live in `<draft-stem>.production.md`.

Record keys are `ID`, `Kind`, `Placement`, `Purpose`, `Source`,
`Requirements`, `State`; values may follow the artifact's language.
Source names actual supplied media/data or explicit missing status. State
records what remains and who must act; it does not certify rendering.

Check ID-to-record agreement only when that question is in scope. Reuse of
one asset can be intentional, but conflicting records for one ID are ambiguous.
Missing records and absent images are missing evidence, not permission to
invent descriptions. Distinguish planned placement, supplied source and
observed rendering. A source-level resolution does not prove the editor step
or publication occurred. Do not edit the article, records or markers while
reporting these findings.

## Assess the Intended Reader Role

If asset meaning is in scope, connect each stable ID to the sentence or step
it is intended to explain. Distinguish reader-visible intended role, caption
and alt text from production instructions. A caption may establish relevance;
alt text describes known content. Neither a requested image nor a filename
is visual evidence, and assembly instructions do not belong in either field.

Locally authored example (hypothetical missing-source record):
Body quote: `[[image:save-location]]`. Record: ID `save-location`,
Source: not supplied, Purpose: show the destination selector.
Finding: the placeholder maps to an explicit missing asset, not an image
already inspected. Reader impact: the planned visual explanation cannot yet
help locate the selector. "Capture the settings panel" is a production
instruction, not usable alt text or a description of an existing screenshot.
If `settings.png` is actually supplied for this ID, trace only that supplied
asset; do not substitute a style reference, guessed URL or invented details.
Reason: source availability and intended contribution are separate questions.

Retain: intentional reuse of one stable ID and an accurate caption supported
by an inspected image or attributed description. Missing assets stay visible;
never recommend deleting a marker just to pass QA. An unrelated missing record
does not expand a bounded prose review into a production audit.

QA evidence: quote the marker, matching record, source status and surrounding
claim. Explain the impact of a missing or mismatched mapping, not a visual
verdict about unseen media. Keep article, notes and IDs unchanged, report no
replacement article, and distinguish proposed caption/alt content from observed
rendering. A supplied file alone does not certify completion of editor work.

Local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
(concrete grounding) and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(material gaps); ID mapping, caption/alt distinctions and the example are local adaptations.
