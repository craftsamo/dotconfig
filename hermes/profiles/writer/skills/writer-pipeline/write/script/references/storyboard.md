# Storyboard text

Describe the requested shots/units with stable IDs and the producer's fields.
Separate visible action/framing, transition intentions and timing targets from
exact narration, dialogue and on-screen text. A supplied visual reference guides
only the agreed aspects; an unseen image cannot be described as inspected.

Track movement, objects and speaker/scene relationships across the sequence.
Do not force a shot count, cuts or camera moves where the request is continuous.
Mark timing as a target unless real evidence establishes it.

QA: unit order and required transitions are coherent, exact text is isolated,
and source/production requirements are explicit. A text storyboard is not drawn
frames, rendered footage or proof that a particular generation tool accepts a
multi-shot plan. Return unsupported production requirements to the requester.

## Craft Decisions

Map each stable unit ID to intended visual content, exact spoken content (or
explicit silence) and the reason the next unit follows. A transition should
preserve an object, reveal a consequence or make an approved change legible.
If crucial information is visual-only, place it in approved speech or the
required descriptive plan; identify meaningful sound and its source there too.
Use only supplied fields. Accessibility planning does not invent a renderer
contract or authorize caption files, recording or a new description track.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: a fictional demo uses S10 then S20, each with visual,
narration and transition fields. S10 shows a hand pressing a switch; S20 shows
the lamp that switch turns on. No other action or sound is specified. A neutral
narrator must convey that relationship without requiring the viewer to see it.
Creative-fiction allowance: wording for the supplied demo, no new device claims.
Draft in the supplied fields:
```text
S10 | Visual: A hand presses the switch. | Narration: This switch turns on the lamp.
S10 | Transition: Follow the switch's effect to the lamp in S20.
S20 | Visual: The lamp lights. | Narration: The lamp is now on. | Transition: End.
```
Rationale: S10 names the object and its function; S20 confirms the visible
result. The transition has a causal reason without specifying a cut or effect.
Retain: the repeated "lamp" prevents an unclear referent after the visual change.
Counterexample: narration "Now this happens" with the same visuals leaves the
essential result inaccessible; a decorative zoom does not repair that omission.
QA: trace switch/action/result across S10 and S20 and quote their speech fields;
compare all fields to the supplied plan. No sound was supplied, so none is added.
Duration, transition execution and accessibility of produced media remain
unverified; inspectable script relationships are not production measurements.

LOCAL adaptation; upstream has no specialized storyboard guide. Selectively use
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope,
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing, and
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for supplied voice and selective changes.
[W3C media guidance](https://www.w3.org/WAI/media/av/) supports early description and meaningful-audio planning.
No source adds mandatory scores, review loops, personal anecdotes or production grants.
