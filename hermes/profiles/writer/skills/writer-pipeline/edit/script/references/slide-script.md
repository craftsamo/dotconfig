# Editing slide scripts

Edit the named page IDs and narration/display fields. Keep existing page IDs
and notes that are outside scope. An approved reorder needs updated references
to pages without silently re-identifying the consumer's slide assets.

Keep on-screen claims and narration consistent, including numbers and caveats.
Do not hide a removed qualification in a note the audience will never hear or
see. Update required speech exports when the corresponding narration changes.

QA: compare visible/spoken fields and mappings with the original and supplied
slides. Notes remain non-verbatim. The edit does not rebuild the deck, update
audio, or establish that a previous presentation duration remains valid.

## Craft Decisions

Within the named narration field, replace a visual-only referent with the
supplied chart relationship if listeners otherwise cannot follow the point.
Name measure, comparison and scope without reading every label/number; keep
the key caveat audible rather than hiding it in a production note.
Leave effective visible messages and bridges intact. A no-op is valid when
speech already complements the slide; do not impose fixed counts or timing.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: fictional SL10, "Shorter waits in the sample"; chart shows
median wait at East branch only, April 8 minutes and May 5 minutes. Cause is
unknown. Only neutral narration may change to explain the chart without sight.
Visible text, ID, chart and notes are protected; no next slide is supplied.
Creative-fiction allowance: phrasing these sample data, not new findings.
Original narration: "As you can see, it fell. We do not know why."
Revised SL10 spoken payload:
```text
In this East branch sample, the median wait fell from eight minutes in April
to five in May. We do not know why.
```
Rationale: naming measure, values and months replaces the gesture-dependent
"it" while the source's cause caveat stays audible and unchanged.
Retain: the visible message orients the audience; do not rewrite protected text.
If speech already names the relationship, keep it rather than reciting it again.
Counterexample: removing "sample" or asserting a cause broadens the evidence;
adding a transition to a nonexistent next slide invents presentation structure.
QA: compare SL10 old/new speech against chart definitions and the cause caveat;
confirm visible fields, notes and IDs unchanged and required raw exports equal
the revised speech. Duration and rendered readability remain unverified;
wording edits do not refresh old audio or prove live presentation fit.

LOCAL adaptation; upstream has no specialized slide-script-edit guide. Use
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for selective changes and supplied voice,
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope, and
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing.
[W3C media guidance](https://www.w3.org/WAI/media/av/av-content/) supports integrating essential chart information in speech.
No mandatory scores, review loops, personal anecdotes or caption production is imported.
