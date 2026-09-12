# Quality assurance — image-creator: mascot

Read [common quality assurance](../../SKILL.md) first.

`generate-mascot`'s own evidence is its `RESULT:` numbers plus round A's
`sheet.png` (candidate comparison) and `silhouette.png` (does each read as a
head/body/limb shape, not a blob) and round B's 25 % pack sheet (does every
pose still read at thumbnail size). Compare every item against the anchor's
named features, palette and proportions (identity) on those sheets, not only
a similar average colour. A silhouette that reads as a blob is named as
such, never smoothed over because the flat colours look fine.

`analyze-mascot`'s own evidence is its `MEASURE:`/`PALETTE:` numbers and
sheets, including `pack64.png` (the 64 px read): legibility there is a WARN
by default (mascots are normally shown large — card art, a video, a page
hero) and becomes a FAIL only when the form's `note` says the file is an
avatar — that exception belongs to analyze-mascot's `note` field, never
assumed on a generate call. `light.png`/`dark.png` also belong to
analyze-mascot, read when the character has a light outline or a dark
silhouette that could vanish on one background. Do not demand
analyze-mascot's evidence (64 px, palette distance, light/dark) as a
condition for a generate-mascot pass, and do not run a fresh check for it on
a generate call. No new measurement is taken here: each leaf's own numbers
and sheets are the evidence, never a fresh finish, crop or a reroll to
double-check a borderline call.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../../SKILL.md).
