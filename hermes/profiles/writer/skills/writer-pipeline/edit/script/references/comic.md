# Editing comic scripts

Apply changes to the named page/panel IDs and fields. Preserve speaker identity,
lettering and action not included in the request. If removing a panel, retain
its retired ID in the structural record; do not compact or reuse panel IDs.

Re-read neighboring panels for continuity and references to removed material.
Keep artist directions separate from exact lettering. A shortening request
does not authorize a new joke, factual claim or character motivation.

QA: compare changed and untouched panels, protected text, attribution and
required limits. Rendered balloon fit and existing art compatibility remain
unverified without the corresponding evidence; this edit produces no new art.

## Craft Decisions

Within named fields, clarify the visible beat or speaker without altering the
supplied panel structure. A wording edit cannot add panels to stage extra actions.
If dialogue repeats the whole action, shorten only authorized repetition;
retain essential information in the visual/descriptive plan or required speech.
If shortening would erase character voice or required lettering, retain it or
report the scope conflict. A no-op is preferable to a new joke or motive.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: fictional panels P10 then P20. Jo hands Mina the key in P10;
Mina unlocks the door in P20. Jo is courteous, Mina terse. Only Jo's P10 dialogue
may be shortened; all IDs, actions, speakers and P20's "Thanks." are protected.
Creative-fiction allowance: wording of this handoff, no new props or backstory.
Original P10 dialogue: "Here is the key that I am handing to you."
Revised fields, with unchanged neighboring panel shown for context:
```text
P10 | Action: Jo hands Mina the key. | Speaker: Jo | Dialogue: Here you are.
P20 | Action: Mina unlocks the door. | Speaker: Mina | Dialogue: Thanks.
```
Rationale: P10's action already supplies the visible handoff; the shorter line
keeps Jo's courtesy without making dialogue recite the artist's instructions.
Retain: P20 stays byte-for-byte unchanged. If "key" must be spoken for an
approved accessible adaptation, retain that information instead of trimming it.
Counterexample: replacing the handoff with a thrown key changes action and
relationship, even if it seems more dramatic; that is outside this edit.
QA: compare P10's dialogue and all protected fields; trace the same key into
P20. No panels were added, removed or renumbered. Verify any actual lettering
limit with its method, not by assuming that fewer words guarantee balloon fit.
Textual beat inspectability is checked; rendered art compatibility is unverified.

LOCAL adaptation; upstream has no specialized comic-edit guide. Use
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for selective changes and supplied voice,
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope, and
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing.
Visual beat versus lettering is LOCAL craft, not permission to modify artwork.
No mandatory scores, review loops, fixed counts or personal anecdotes are imported.
