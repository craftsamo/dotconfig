# Comic script

Use the released page/panel structure, cast and required lettering fields.
Each panel needs an addressable ID and the information its artist actually
needs: action and speakers, with exact dialogue/captions in separate fields.
Describe observable action rather than relying on prose that cannot be staged.

Keep character knowledge, props and spatial/story continuity consistent across
panels. Express only the approved story freedom; a knowledge comic's factual
claims still need sources. Do not force a fixed panel count, arc or final CTA.

Honor supplied balloon/lettering limits. Without rendered panels, text length
and descriptions do not prove balloon fit, visual readability or a successful
image-generation result. Do not generate character art or choose a renderer.

QA: IDs/order, speaker attribution and verbatim lettering match the brief;
action can be understood without confusing directions with printed text.
Actual visual fit and production results remain separately verifiable.

## Craft Decisions

Give each supplied panel an actionable visible beat: who does what with which
object. If several successive actions cannot share the requested panel, flag
the structural conflict instead of silently adding panels or shrinking text.
Let the visual field carry position/action and dialogue carry the speaker's
response; repeat visual information only when essential to comprehension.
If accessibility requires a descriptive plan, map essential visuals there;
do not make every character narrate every visible detail to the audience.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: approved panels P10 then P20, with action/speaker/dialogue
fields. Mina, terse, needs a key; Jo, courteous, hands Mina the key in P10.
Mina unlocks the door in P20. Approved lines: Jo offers the key politely;
Mina acknowledges it briefly. No other cast, props or facts are supplied.
Creative-fiction allowance: dialogue for these beats, not a new motive or event.
Draft in the supplied fields:
```text
P10 | Action: Jo hands Mina the key. | Speaker: Jo | Dialogue: Here you are.
P20 | Action: Mina unlocks the door. | Speaker: Mina | Dialogue: Thanks.
```
Rationale: the handoff motivates the next panel's unlock; each speaker has an
identifiable role without explaining the drawn action in full a second time.
Retain: Mina's brief acknowledgment fits the supplied voice; it needs no speech
about gratitude. The key must remain explicit in P10's action for the artist.
Counterexample: "Jo hands over hope" does not specify the drawable handoff;
inventing a lost-key backstory to explain it would exceed this fiction grant.
QA: trace P10's key to P20, quote each speaker's field and check panel order
against the supplied structure. Lettering fit remains unverified without art;
textual beat inspectability is not a rendered-panel or audience-response test.

LOCAL adaptation; upstream has no specialized comic guide. Selectively use
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope,
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing, and
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for supplied voice and selective changes.
The visible-beat/lettering distinction is LOCAL comic craft, not a renderer rule.
These sources do not impose scores, review loops, fixed counts or personal anecdotes.
