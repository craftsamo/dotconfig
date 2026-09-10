# Editing storyboard text

Identify the exact shots/fields the edit covers. Preserve stable IDs and the
approved spatial/action relationships outside that scope. Do not turn a
continuous passage into a cut sequence just to simplify the text.

Keep dialogue, narration and display text separate from framing, transition
and timing notes. A shot removed from the plan leaves a retired-ID record;
dependent references must be resolved without silent renumbering.

QA: the revised sequence is coherent and its exports match the master. Changed
text/direction does not update footage, transition timing or existing proof
frames; flag those downstream checks instead of claiming the video corrected.

## Craft Decisions

Check the edited unit's intended visual, speech and transition cause against
its stable ID and neighbors. Fix only the authorized field, not the shot design.
If a shortened line strands crucial information in visuals, restore it within
authorized speech or flag a change to the required descriptive plan for approval.
Keep meaningful sound/source and speaker identity in their approved roles.
A no-op is valid when the mapping already works; do not invent transitions,
renderer fields or caption files to make the plan appear production-complete.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: fictional S10 shows a hand pressing a switch; S20 shows its
lamp lighting. Narrator voice is neutral. S10's transition follows the switch's
effect to S20; S20 ends the sequence. Only S20 narration may change to name the
result for listeners without the image. All visual/transition fields are protected.
Creative-fiction allowance: these demo words, not additional device behavior.
Original S20 narration: "Now this happens."
Revised field:
```text
S20 | Narration: The lamp is now on.
```
Rationale: "lamp" and "on" make the result available in speech without adding
a camera move or rewriting S10. Existing causal transition and IDs remain intact.
Retain: the supplied transition already explains why S20 follows S10; leave it.
If the result is already conveyed in approved description, keep suitable silence
rather than forcing speech into every unit solely for symmetry.
Counterexample: "The lamp is safer now" adds an unsupported benefit, not clarity.
QA: compare the changed speech to S20's visual and S10's cause; quote retained
IDs and transition fields. Required exports follow only the revised exact words.
Duration, transition execution and production accessibility remain unverified;
textual mapping evidence does not update footage or an existing audio track.

LOCAL adaptation; upstream has no specialized storyboard-edit guide. Use
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for selective changes and supplied voice,
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope, and
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing.
[W3C media guidance](https://www.w3.org/WAI/media/av/) supports planning essential visual and meaningful-audio information.
No mandatory scores, review loops, personal anecdotes or production grants follow.
