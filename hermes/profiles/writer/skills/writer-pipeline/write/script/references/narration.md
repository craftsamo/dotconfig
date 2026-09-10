# Narration

Write for the intended listener using the supplied content and pronunciation
requirements. Plain narration can be a continuous spoken text; do not add a
scene table, stage directions or a CTA merely because it is a script.

For a consumer reading the whole file aloud, deliver words only: no title,
speaker label, fence or bracketed pause note. Keep pronunciation/delivery
instructions in separate production notes unless the producer explicitly
defines a supported non-spoken field. Do not invent SSML or voice IDs.

If several speakers or sections require separate files, agree on those units
and map exact text to each output. Use the actual consumer's limits; do not
silently split a long narration into extra synthesis jobs. A timing target may
guide writing but needs real performance evidence before claiming duration fit.

QA: spoken payload contains only intended words and matches the approved text;
notes are not input to speech. Text acceptance is not listening, synthesis,
pronunciation verification, voice likeness or an exact timing guarantee.

## Craft Decisions

If a pronoun needs a picture to identify its object, name that object before
using the pronoun. Order words by what the listener knows at that moment.
If nested qualifications delay the instruction, separate eligibility from
action while retaining every condition, exception and degree of certainty.
Keep a useful orientation or deliberate pause; brevity is not a preamble ban.
Put meaningful sound/silence intentions in notes, not in a words-only file.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: a fictional library tutorial for adult members; the blue
return box is for books borrowed at this branch only. Its lid must be open
before insertion. The approved action is to put eligible books in that box.
Voice is calm and direct; no image, audio or duration evidence is supplied.
Creative-fiction allowance: wording within this scenario, not new policies.
Draft, exact spoken payload:
```text
The blue return box is for books borrowed at this branch only.
When its lid is open, put those books in the box.
```
Rationale: naming the box establishes the referent for "its"; the branch
restriction remains attached to the books rather than becoming a general rule.
Retain: "at this branch only" is necessary repetition of scope, not clutter.
Counterexample: "Put them here" depends on an unseen gesture; "Return any
book" invents eligibility. Neither is a useful shortcut for this listener.
QA: quote the named object and both conditions against the supplied material;
compare the exact payload with the speech input and keep any notes separate.
This example has no notes to export. Duration and read-aloud performance are
unverified; textual referent tracing is craft evidence, not a listening test.

LOCAL adaptation; upstream has no specialized narration guide. Selectively use
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope,
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing, and
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for supplied voice and selective changes.
[W3C media guidance](https://www.w3.org/WAI/media/av/av-content/) supports naming visual referents;
[BBC radio drama](https://www.bbc.co.uk/writers/resources/tips-and-advice/writing-radio-drama) supports meaningful sound/silence, not a universal preamble ban.
These are craft sources, not mandatory scores, review loops or personal anecdotes.
