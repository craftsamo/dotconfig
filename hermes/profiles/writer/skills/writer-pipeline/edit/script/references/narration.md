# Editing narration

Keep the requested voice, meaning, qualifications and protected words while
changing only the authorized text. A plain speech file remains words only;
do not insert labels, Markdown fences or directions such as a pause annotation.
Put instructions outside the spoken payload in production notes.

Update required raw exports consistently with the master. Do not silently split
or reorder approved sections to fit a consumer limit. A changed line can
invalidate existing audio, subtitle or duration evidence even if it is shorter.

QA: compare the exact old/new words and all requested exports; untouched
sections remain intact. The revision requires renewed acceptance and production
approval, not a claim that the old audio/timing now matches the new text.

## Craft Decisions

Within authorized wording, name an object before a pronoun if the listener
would otherwise need a picture. Do not infer a referent absent from the source.
Split nested qualifications only when their attachment becomes clearer; retain
scope, exceptions and uncertainty beside the action they govern.
Keep effective rhythm and useful orientation. A no-op is valid when there is
no listener benefit within scope; shorter does not automatically mean clearer.

## Worked Example (Fictional, MATERIAL-COMPLETE)

Supplied material: fictional library narration N10; a blue return box accepts
books borrowed at this branch only, and insertion requires its lid to be open.
The calm, direct voice and branch restriction are protected. Only N10's wording
may change; no new sections, policies or media. No timing evidence is supplied.
Creative-fiction allowance: this approved scenario, not factual library advice.
Original N10: "When it is open, put books borrowed at this branch only here."
Revised N10, exact spoken payload:
```text
The blue return box is for books borrowed at this branch only.
When its lid is open, put those books in the box.
```
Rationale: the original opening lacks an audible referent; naming box and lid
resolves it while keeping eligibility separate from the insertion condition.
Retain: "at this branch only" remains exact. If the source already names the
box and lid clearly, retain that wording rather than applying this split again.
Counterexample: "Put any books in the box" drops both protected restrictions.
QA: compare N10 old/new referents and conditions, confirm untouched units and
required exports against the master, and keep production notes out of speech.
Duration and read-aloud performance remain unverified; textual clarity does
not prove the revised words fit old audio or authorize a new synthesis job.

LOCAL adaptation; upstream has no specialized narration-edit guide. Use
[revision-guide.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md) for selective changes and supplied voice,
[writing-constitution.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md) for evidential scope, and
[genre-notes.md](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md) for conditional pacing.
[W3C media guidance](https://www.w3.org/WAI/media/av/av-content/) supports naming visual referents;
[BBC radio drama](https://www.bbc.co.uk/writers/resources/tips-and-advice/writing-radio-drama) supports meaningful pauses, not blanket preamble removal.
No mandatory scores, review loops or personal anecdotes are imported.
